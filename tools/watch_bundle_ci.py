"""Observe this bundle's exact GitHub run; preserve evidence through execution.log.

This is a development tool, not a Core network capability. Only gh GET requests
are used. CI failures never undo committed local work. No test suite runs here.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))

REPOSITORY = 'cdoehn/specroad'
WORKFLOW = '.github/workflows/behavior.yml'
PYTHONS = ('3.10', '3.11', '3.12', '3.13', '3.14')
MAX_BYTES = 64 * 1024 * 1024  # Evidence capture bound, never a test timeout.
PREFIX = 'SPECRoad-CI-EVIDENCE-V1 '


class CIObservationError(ValueError):
    """Unavailable/mismatched external observation, not a local apply failure."""


@dataclass(frozen=True)
class Request:
    commit: str
    bundle: int
    source_sha256: str | None = None

    def __post_init__(self):
        if type(self.commit) is not str or re.fullmatch('[0-9a-f]{40}', self.commit) is None:
            raise CIObservationError('full_commit_required')
        if type(self.bundle) is not int or self.bundle < 1:
            raise CIObservationError('positive_bundle_required')
        if self.source_sha256 is not None and (type(self.source_sha256) is not str or re.fullmatch('[0-9a-f]{64}', self.source_sha256) is None):
            raise CIObservationError('invalid_source_binding')

    @property
    def mode(self):
        return 'both' if self.bundle % 5 == 0 else 'parallel'


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False) + '\n').encode()


def decode_json(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise CIObservationError('duplicate_api_json_key')
            result[k] = v
        return result
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError, RecursionError) as error:
        raise CIObservationError('invalid_api_json') from error


class GhClient:
    """Read-only fixed-host transport; credentials remain inside gh."""

    def __init__(self, runner=None):
        self.runner = subprocess.run if runner is None else runner

    def get(self, endpoint):
        if not endpoint.startswith('repos/' + REPOSITORY + '/actions/') or '\n' in endpoint:
            raise CIObservationError('unexpected_api_endpoint')
        env = dict(os.environ)
        env.pop('GH_DEBUG', None)
        env.update(GH_HOST='github.com', GH_PROMPT_DISABLED='1', GH_PAGER='cat', PAGER='cat')
        try:
            result = self.runner(['gh', 'api', '--hostname', 'github.com', '--method', 'GET', endpoint],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env, check=False, timeout=90)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise CIObservationError('gh_unavailable_or_api_timeout') from error
        if result.returncode:
            # Do not copy credential diagnostics or arbitrary environment text.
            raise CIObservationError('gh_api_exit_' + str(result.returncode))
        if len(result.stdout) > MAX_BYTES:
            raise CIObservationError('evidence_capture_limit')
        return result.stdout

    def document(self, endpoint):
        return decode_json(self.get(endpoint))


def exact_run(run, request, *, run_id=None, attempt=None):
    if type(run) is not dict:
        raise CIObservationError('invalid_run_document')
    if (run.get('head_sha') != request.commit or run.get('head_branch') != 'dev'
            or run.get('event') != 'push' or run.get('path') != WORKFLOW
            or type(run.get('repository')) is not dict
            or type(run['repository'].get('full_name')) is not str
            or run['repository']['full_name'].lower() != REPOSITORY):
        raise CIObservationError('run_binding_mismatch')
    for key in ('id', 'run_attempt'):
        if type(run.get(key)) is not int or run[key] < 1:
            raise CIObservationError('invalid_run_identity')
    if (run_id is not None and run['id'] != run_id) or (attempt is not None and run['run_attempt'] != attempt):
        raise CIObservationError('run_attempt_changed')
    if run.get('status') not in ('queued', 'in_progress', 'completed', 'waiting', 'pending', 'requested'):
        raise CIObservationError('unknown_run_status')
    return run


def records(client, path, field):
    """Read the complete paginated collection; inconsistent pages are errors."""
    result = []
    total = None
    page = 1
    seen = set()
    while True:
        sep = '&' if '?' in path else '?'
        data = client.document(path + sep + 'per_page=100&page=' + str(page))
        if type(data) is not dict or type(data.get('total_count')) is not int or data['total_count'] < 0:
            raise CIObservationError('invalid_collection_count')
        if total is None:
            total = data['total_count']
        if data['total_count'] != total or total > 10000 or type(data.get(field)) is not list:
            raise CIObservationError('changing_or_oversized_collection')
        for item in data[field]:
            if type(item) is not dict or type(item.get('id')) is not int or item['id'] < 1 or item['id'] in seen:
                raise CIObservationError('invalid_or_duplicate_collection_identity')
            seen.add(item['id']); result.append(item)
        if len(result) == total:
            return result
        if len(result) > total or not data[field]:
            raise CIObservationError('incomplete_collection')
        page += 1


def find_run(client, request):
    runs = records(client, 'repos/' + REPOSITORY + '/actions/workflows/behavior.yml/runs'
        + '?branch=dev&event=push&head_sha=' + request.commit, 'workflow_runs')
    candidates = []
    for run in runs:
        # API filtering is checked, not trusted to select an unrelated run.
        exact_run(run, request)
        candidates.append(run)
    if len(candidates) > 1:
        raise CIObservationError('ambiguous_push_runs')
    return candidates[0] if candidates else None


def checked_jobs(client, request, run_id, attempt):
    jobs = records(client, f'repos/{REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}/jobs', 'jobs')
    for job in jobs:
        if job.get('run_id') != run_id or job.get('head_sha') != request.commit:
            raise CIObservationError('job_binding_mismatch')
        if job.get('run_attempt', attempt) != attempt:
            raise CIObservationError('job_attempt_mismatch')
        if (type(job.get('steps')) is not list or type(job.get('name')) is not str
                or any(type(step) is not dict for step in job['steps'])):
            raise CIObservationError('invalid_job_document')
    return jobs


def verdict(run, jobs, request):
    """A green selection-only/skipped workflow is not a full matrix pass."""
    if run['status'] != 'completed':
        return 'pending'
    conclusion = run.get('conclusion')
    if conclusion in ('failure', 'timed_out', 'cancelled', 'startup_failure', 'action_required', 'stale'):
        return 'cancelled' if conclusion == 'cancelled' else 'failed'
    if conclusion != 'success':
        return 'incomplete'
    expected = {'CPython ' + version + ' / ' + request.mode for version in PYTHONS}
    matrix = [job for job in jobs if job['name'] in expected]
    if len(matrix) != len(expected) or {job['name'] for job in matrix} != expected:
        return 'incomplete'
    step_name = ('Full parallel regression' if request.mode == 'parallel'
                 else 'Full parallel and serial regression with evidence comparison')
    for job in matrix:
        steps = [step for step in job['steps'] if step.get('name') == step_name]
        if (job.get('status') != 'completed' or job.get('conclusion') != 'success'
                or len(steps) != 1 or steps[0].get('status') != 'completed'
                or steps[0].get('conclusion') != 'success'):
            return 'incomplete'
    if any(job.get('status') != 'completed' or job.get('conclusion') != 'success' for job in jobs):
        return 'incomplete'
    return 'success'


def inspect_report_archive(raw, request, version):
    """Validate passing framework reports, preserving all original archive bytes."""
    from compare_test_runs import _signature, compare_reports
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        members = archive.infolist()
        if len(members) > 100 or sum(i.file_size for i in members) > MAX_BYTES:
            raise CIObservationError('oversized_report_archive')
        reports = {}
        for name in ('parallel-evidence.json', 'serial-evidence.json', 'summary.json'):
            matches = [i for i in members if i.filename.rsplit('/', 1)[-1] == name and not i.is_dir()]
            if len(matches) > 1:
                raise CIObservationError('ambiguous_report_member')
            if matches:
                reports[name] = decode_json(archive.read(matches[0]))
    required = ['parallel-evidence.json'] + (['serial-evidence.json'] if request.mode == 'both' else [])
    if not all(name in reports for name in required):
        raise CIObservationError('missing_test_evidence')
    for name in required:
        report = reports[name]
        _signature(report)  # Existing completeness contract; no second scheduler/oracle.
        if (request.source_sha256 is not None and report.get('tool_build_sha256') != request.source_sha256):
            raise CIObservationError('test_source_binding_mismatch')
        runtime = report.get('runtime', {})
        execution = report.get('execution', {})
        if (type(runtime) is not dict or runtime.get('implementation') != 'cpython'
                or type(runtime.get('python')) is not str or not runtime['python'].startswith(version + '.')
                or type(execution) is not dict or execution.get('workers') != (0 if name.startswith('serial') else 4)):
            raise CIObservationError('test_runtime_or_mode_mismatch')
    comparison = None
    if request.mode == 'both':
        comparison = compare_reports([reports[name] for name in required])
        stored = reports.get('summary.json', {})
        if (type(stored) is not dict or stored.get('suite_passed') is not True
                or stored.get('exit_code') != 0 or stored.get('errors') != []
                or stored.get('comparison') != comparison):
            raise CIObservationError('missing_or_inconsistent_comparison')
    return {'python': version, 'mode': request.mode, 'tests_run': reports[required[0]]['tests_run'],
            'source_bound': request.source_sha256 is not None, 'comparison': comparison}


def collect_artifacts(client, request, run_id, attempt, files):
    """Names include attempt: no reuse of an older run's successful evidence."""
    artifacts = records(client, f'repos/{REPOSITORY}/actions/runs/{run_id}/artifacts', 'artifacts')
    files['artifact-index.json'] = json_bytes(artifacts)
    reports, errors = [], []
    for version in PYTHONS:
        name = f'behavior-{version}-{request.commit}-attempt-{attempt}'
        matches = [a for a in artifacts if a.get('name') == name]
        try:
            if len(matches) != 1 or matches[0].get('expired') is not False:
                raise CIObservationError('missing_ambiguous_or_expired_artifact')
            artifact = matches[0]
            binding = artifact.get('workflow_run', {})
            if (type(binding) is not dict or binding.get('id') != run_id
                    or binding.get('head_sha') != request.commit or binding.get('head_branch') != 'dev'):
                raise CIObservationError('artifact_binding_mismatch')
            raw = client.get(f"repos/{REPOSITORY}/actions/artifacts/{artifact['id']}/zip")
            expected = artifact.get('digest')
            if expected is not None and expected != 'sha256:' + sha256(raw).hexdigest():
                raise CIObservationError('artifact_digest_mismatch')
            if sum(map(len, files.values())) + len(raw) > MAX_BYTES // 2:
                raise CIObservationError('total_evidence_limit')
            # Preserve a failed/partial report as well, before attempting a pass proof.
            files['reports-' + version + '.zip'] = raw
            reports.append(inspect_report_archive(raw, request, version))
        except (CIObservationError, OSError, ValueError, zipfile.BadZipFile, RuntimeError, TypeError, KeyError) as error:
            errors.append({'phase': 'artifact', 'python': version, 'reason': type(error).__name__ + ': ' + str(error)[:160]})
    return reports, errors


def observe_ci(request, *, client=None, progress=None, sleeper=None, discovery_polls=60, poll_seconds=5):
    """Wait for a pinned push run; operational lookup limits do not cancel CI.

    Running CI has no additional local test timeout. On an API failure after
    retries, return an unavailable observation, never success. No reruns/pushes.
    """
    if type(request) is not Request or type(discovery_polls) is not int or discovery_polls < 1:
        raise CIObservationError('invalid_observation_request')
    client = GhClient() if client is None else client
    progress = (lambda event: None) if progress is None else progress
    sleeper = time.sleep if sleeper is None else sleeper
    files = {}
    summary = {'format_version': 1, 'local_apply': 'success', 'ci_status': 'unavailable',
        'repository': REPOSITORY, 'workflow_path': WORKFLOW, 'branch': 'dev',
        'commit_sha': request.commit, 'bundle_number': request.bundle, 'expected_mode': request.mode,
        'run_id': None, 'run_attempt': None, 'github_conclusion': None,
        'logs_captured': False, 'evidence_complete': False, 'test_evidence_verified': False,
        'started_at': datetime.now(timezone.utc).isoformat(), 'errors': []}
    def retry(call):
        for count in range(3):
            try:
                return call()
            except CIObservationError:
                if count == 2:
                    raise
                progress({'phase': 'retry', 'attempt': count + 1})
                sleeper(poll_seconds)
    try:
        run = None
        for _ in range(discovery_polls):
            run = retry(lambda: find_run(client, request))
            if run is not None:
                break
            progress({'phase': 'discovery', 'commit': request.commit})
            sleeper(poll_seconds)
        if run is None:
            raise CIObservationError('matching_run_not_visible')
        run_id, attempt = run['id'], run['run_attempt']
        summary.update(run_id=run_id, run_attempt=attempt,
                       run_url=f'https://github.com/{REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}')
        while True:
            run = exact_run(retry(lambda: client.document(f'repos/{REPOSITORY}/actions/runs/{run_id}')),
                            request, run_id=run_id, attempt=attempt)
            jobs = retry(lambda: checked_jobs(client, request, run_id, attempt))
            files['run.json'], files['jobs.json'] = json_bytes(run), json_bytes(jobs)
            progress({'phase': 'running', 'run_id': run_id, 'attempt': attempt, 'status': run['status'],
                'jobs': [{'name': j['name'], 'status': j.get('status'), 'conclusion': j.get('conclusion'),
                    'steps': j['steps']} for j in jobs]})
            if run['status'] == 'completed':
                break
            sleeper(poll_seconds)
        summary['ci_status'] = verdict(run, jobs, request)
        summary['github_conclusion'] = run.get('conclusion')
        try:
            raw = retry(lambda: client.get(f'repos/{REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}/logs'))
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                if (not archive.infolist() or sum(i.file_size for i in archive.infolist()) > MAX_BYTES
                        or archive.testzip() is not None):
                    raise CIObservationError('invalid_or_oversized_log_archive')
            files['logs.zip'] = raw
            summary['logs_captured'] = True
        except (CIObservationError, OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
            summary['errors'].append({'phase': 'logs', 'reason': str(error)[:200]})
        reports, artifact_errors = collect_artifacts(client, request, run_id, attempt, files)
        summary['test_reports'] = reports
        summary['errors'].extend(artifact_errors)
        summary['test_evidence_verified'] = (len(reports) == len(PYTHONS) and request.source_sha256 is not None)
        summary['evidence_complete'] = summary['logs_captured'] and len(reports) == len(PYTHONS)
        # A rerun during capture must not mix attempts or turn earlier evidence green.
        last = exact_run(retry(lambda: client.document(f'repos/{REPOSITORY}/actions/runs/{run_id}')),
                         request, run_id=run_id, attempt=attempt)
        if last['status'] != 'completed' or last.get('conclusion') != run.get('conclusion'):
            raise CIObservationError('run_changed_during_capture')
    except KeyboardInterrupt:
        summary['ci_status'] = 'observation_interrupted'
        summary['errors'].append({'phase': 'observation', 'reason': 'keyboard_interrupt'})
    except (CIObservationError, OSError) as error:
        summary['ci_status'] = 'unavailable'
        summary['evidence_complete'] = False
        summary['test_evidence_verified'] = False
        summary['errors'].append({'phase': 'observation', 'reason': str(error)[:200]})
    summary['ended_at'] = datetime.now(timezone.utc).isoformat()
    summary['files'] = {name: {'size': len(raw), 'sha256': sha256(raw).hexdigest()} for name, raw in files.items()}
    files['summary.json'] = json_bytes(summary)
    return summary, files


def pack_evidence(files):
    """Opaque GitHub archives are never extracted or executed here."""
    if sum(map(len, files.values())) > MAX_BYTES:
        raise CIObservationError('total_evidence_limit')
    out = BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            if type(name) is not str or re.fullmatch(r'[a-zA-Z0-9_.-]+', name) is None or name in ('.', '..'):
                raise CIObservationError('unsafe_evidence_name')
            info = zipfile.ZipInfo(name); info.external_attr = 0o100600 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    return out.getvalue()


def emit_evidence(raw, stream):
    """Checked transport inside PatchHarbor's existing captured output channel."""
    h = sha256(raw).hexdigest()
    chunk_size = 3072
    chunks = (len(raw) + chunk_size - 1) // chunk_size
    stream.write(PREFIX + json.dumps({'kind': 'begin', 'sha256': h, 'bytes': len(raw), 'chunks': chunks}) + '\n')
    for index in range(chunks):
        stream.write(PREFIX + json.dumps({'kind': 'chunk', 'sha256': h, 'index': index,
            'data': base64.b64encode(raw[index * chunk_size:(index + 1) * chunk_size]).decode('ascii')}) + '\n')
    stream.write(PREFIX + json.dumps({'kind': 'end', 'sha256': h}) + '\n')
    stream.flush()


def recover_evidence(log):
    """Recover exactly one completed, byte-verified archive from execution.log."""
    records_ = [decode_json(line[len(PREFIX):].encode()) for line in log.splitlines() if line.startswith(PREFIX)]
    if not records_ or records_[0].get('kind') != 'begin' or records_[-1].get('kind') != 'end':
        raise CIObservationError('incomplete_evidence_transport')
    header = records_[0]
    if type(header.get('bytes')) is not int or not 0 < header['bytes'] <= MAX_BYTES:
        raise CIObservationError('invalid_evidence_size')
    if type(header.get('chunks')) is not int or len(records_) != header['chunks'] + 2:
        raise CIObservationError('evidence_chunk_count')
    result = bytearray()
    for index, record in enumerate(records_[1:-1]):
        if record.get('kind') != 'chunk' or type(record.get('index')) is not int or record.get('index') != index or record.get('sha256') != header.get('sha256'):
            raise CIObservationError('evidence_chunk_binding')
        try:
            result.extend(base64.b64decode(record['data'], validate=True))
        except (ValueError, KeyError, TypeError) as error:
            raise CIObservationError('evidence_chunk_encoding') from error
        if len(result) > header['bytes']:
            raise CIObservationError('evidence_overflow')
    raw = bytes(result)
    if len(raw) != header['bytes'] or sha256(raw).hexdigest() != header.get('sha256') or records_[-1].get('sha256') != header['sha256']:
        raise CIObservationError('evidence_integrity')
    return raw


def show_progress(event):
    if event['phase'] == 'running':
        print(f"\033[36mCI #{event['run_id']} · attempt {event['attempt']} · {event['status']}\033[0m", flush=True)
        for job in event['jobs']:
            state = job['conclusion'] or job['status']
            color = '32' if state == 'success' else '31' if state in ('failure', 'cancelled') else '33'
            active = ', '.join(s['name'] for s in job['steps'] if s.get('status') == 'in_progress')
            print(f"  \033[{color}m{job['name']}: {state}\033[0m {active}", flush=True)
    else:
        print('CI: ' + event['phase'] + ' …', flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--bundle', type=int, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--push-failed', action='store_true')
    args = parser.parse_args(argv)
    from verification_support.identity import source_identity
    request = Request(args.commit, args.bundle, source_identity(Path(__file__).resolve().parents[1]))
    if args.push_failed:
        summary = {'format_version': 1, 'local_apply': 'success', 'ci_status': 'not_published',
                   'commit_sha': request.commit, 'bundle_number': request.bundle,
                   'repository': REPOSITORY, 'expected_mode': request.mode, 'evidence_complete': False}
        files = {'summary.json': json_bytes(summary)}
    else:
        summary, files = observe_ci(request, progress=show_progress)
    try:
        raw = pack_evidence(files)
    except CIObservationError:
        summary['evidence_complete'] = False
        summary['errors'] = [*summary.get('errors', []), {'phase': 'transport', 'reason': 'capture_limit'}]
        # Do not lose the actual CI outcome just because full logs are too large.
        raw = pack_evidence({'summary.json': json_bytes(summary)})
    # This optional convenience copy is not the Result transport. The captured
    # output below is sufficient even when ignored build files are not bundled.
    try:
        args.output_dir.mkdir(parents=False, exist_ok=False)
        with (args.output_dir / 'ci-evidence.zip').open('xb') as stream:
            stream.write(raw)
        with (args.output_dir / 'ci-summary.json').open('xb') as stream:
            stream.write(json_bytes(summary))
    except OSError:
        print('CI: convenience copy unavailable; preserving evidence in execution.log', flush=True)
    print('CI-EVIDENCE: transmitting compressed archive to Result execution.log', flush=True)
    emit_evidence(raw, sys.stdout)
    print('CI-SUMMARY: ' + json_bytes(summary).decode().strip(), flush=True)
    color = '32' if summary['ci_status'] == 'success' else '31' if summary['ci_status'] == 'failed' else '33'
    print(f"\033[{color}mLOCAL APPLY: SUCCESS | CI: {summary['ci_status'].upper()}\033[0m", flush=True)
    # Exit 0 describes a completed observation. ci_status carries the CI result.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
