"""CI archives and checksummed transport in the existing execution log."""
import base64
from hashlib import sha256
from io import BytesIO
import json
import re
import zipfile
from .contract import (REPOSITORY, PYTHONS, MAX_BYTES, PREFIX, CIObservationError, json_bytes, decode_json, error_record)
from .transport import records

def inspect_report_archive(raw, request, version, *, run_id=None, attempt=None):
    """Validate passing framework reports, preserving all original archive bytes."""
    from compare_test_runs import _signature, compare_reports
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        members = archive.infolist()
        if len(members) > 100 or sum(i.file_size for i in members) > MAX_BYTES:
            raise CIObservationError('oversized_report_archive')
        reports = {}
        for name in ('parallel-evidence.json', 'serial-evidence.json', 'summary.json', 'run-context.json',
                     'ci-plan.json', 'shard-receipts.json'):
            matches = [i for i in members if i.filename.rsplit('/', 1)[-1] == name and not i.is_dir()]
            if len(matches) > 1:
                raise CIObservationError('ambiguous_report_member')
            if matches:
                reports[name] = decode_json(archive.read(matches[0]))
    context = reports.get('run-context.json')
    if request.event == 'workflow_dispatch':
        if (type(context) is not dict or context.get('format_version') != 1
                or context.get('repository') != REPOSITORY or context.get('branch') != 'dev'
                or context.get('event') != request.event or context.get('mode') != request.mode
                or context.get('test_commit_sha') != request.commit
                or context.get('workflow_commit_sha') != request.run_commit
                or context.get('python') != version
                or any(type(context.get(k)) is not int or context[k] < 1 for k in ('run_id', 'run_attempt'))
                or (run_id is not None and context['run_id'] != run_id)
                or (attempt is not None and context['run_attempt'] != attempt)):
            raise CIObservationError('manual_test_context_mismatch')
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
        if ('ci_packages' in report or 'ci_shards' in execution
                or 'ci-plan.json' in reports or 'shard-receipts.json' in reports):
            from verification_support.ci_packages import verify_aggregate
            try:
                plan = reports['ci-plan.json']
                verify_aggregate(plan, reports['shard-receipts.json'], report)
                if plan['context'] != context or execution.get('distribution') != 'worksteal':
                    raise ValueError('Wrong aggregate execution context')
            except (KeyError, TypeError, ValueError) as error:
                raise CIObservationError('invalid_package_aggregate') from error
    comparison = None
    if request.mode == 'both':
        comparison = compare_reports([reports[name] for name in required])
        stored = reports.get('summary.json', {})
        if (type(stored) is not dict or stored.get('suite_passed') is not True
                or stored.get('exit_code') != 0 or stored.get('errors') != []
                or stored.get('comparison') != comparison):
            raise CIObservationError('missing_or_inconsistent_comparison')
    return {'python': version, 'mode': request.mode, 'tests_run': reports[required[0]]['tests_run'],
            'source_bound': request.source_sha256 is not None, 'comparison': comparison,
            'run_context': context}


def collect_artifacts(client, request, run_id, attempt, files, *, retry=None):
    """Names include attempt: no reuse of an older run's successful evidence."""
    # Retry only GET/collection transport; never retry away an integrity failure.
    retry = (lambda call: call()) if retry is None else retry
    artifacts = retry(lambda: records(client,
        f'repos/{REPOSITORY}/actions/runs/{run_id}/artifacts', 'artifacts'))
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
                    or binding.get('head_sha') != request.run_commit or binding.get('head_branch') != 'dev'):
                raise CIObservationError('artifact_binding_mismatch')
            raw = retry(lambda: client.get(
                f"repos/{REPOSITORY}/actions/artifacts/{artifact['id']}/zip"))
            expected = artifact.get('digest')
            if expected is not None and expected != 'sha256:' + sha256(raw).hexdigest():
                raise CIObservationError('artifact_digest_mismatch')
            if sum(map(len, files.values())) + len(raw) > MAX_BYTES // 2:
                raise CIObservationError('total_evidence_limit')
            # Preserve a failed/partial report as well, before attempting a pass proof.
            files['reports-' + version + '.zip'] = raw
            reports.append(inspect_report_archive(raw, request, version, run_id=run_id, attempt=attempt))
        except (CIObservationError, OSError, ValueError, zipfile.BadZipFile, RuntimeError, TypeError, KeyError) as error:
            errors.append({'phase': 'artifact', 'python': version, 'reason': type(error).__name__ + ': ' + str(error)[:160]})
    return reports, errors


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


def capture_attempt_files(client, request, run_id, attempt, jobs, files, summary, *, retry):
    """Preserve exact-attempt archives; a failed report is evidence, not a pass.

    When a complete run archive is unavailable, already confirmed completed job
    IDs can still provide useful logs. These are explicitly partial, never an
    invented complete archive. No user files or archive members are extracted.
    """
    try:
        raw = retry(lambda: client.get(
            f'repos/{REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}/logs'))
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            if (not archive.infolist() or sum(i.file_size for i in archive.infolist()) > MAX_BYTES
                    or archive.testzip() is not None):
                raise CIObservationError('invalid_or_oversized_log_archive')
        if sum(map(len, files.values())) + len(raw) > MAX_BYTES // 2:
            raise CIObservationError('total_evidence_limit')
        files['logs.zip'] = raw
        summary['logs_captured'] = True
    except (CIObservationError, OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
        summary['errors'].append(error_record('logs', error))
        for job in jobs:
            if job.get('status') != 'completed':
                continue
            job_id = job['id']  # Already checked by checked_jobs/records.
            try:
                raw = retry(lambda: client.get(
                    f'repos/{REPOSITORY}/actions/jobs/{job_id}/logs'))
                if not raw or sum(map(len, files.values())) + len(raw) > MAX_BYTES // 2:
                    raise CIObservationError('empty_or_oversized_job_log')
                files[f'job-{job_id}-attempt-{attempt}.log'] = raw
                summary['job_logs_captured'].append(job_id)
            except (CIObservationError, OSError) as job_error:
                item = error_record('job_logs', job_error)
                item['job_id'] = job_id
                summary['errors'].append(item)
    reports, artifact_errors = collect_artifacts(client, request, run_id, attempt, files, retry=retry)
    summary['test_reports'] = reports
    summary['errors'].extend(artifact_errors)
    summary['test_evidence_verified'] = len(reports) == len(PYTHONS) and request.source_sha256 is not None
    summary['evidence_complete'] = summary['logs_captured'] and len(reports) == len(PYTHONS)
    summary['capture_complete'] = summary['logs_captured'] and all(
        'reports-' + version + '.zip' in files for version in PYTHONS)
