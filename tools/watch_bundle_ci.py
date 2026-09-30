"""Observe an explicitly started full CI run; never trigger tests or assert an apply.

Manual runs default to both modes. Historical push recovery requires explicit mode.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))

from ci_support.contract import (Request, CIObservationError, REPOSITORY, WORKFLOW,
                                 PYTHONS, MAX_BYTES, PREFIX, json_bytes, decode_json, exact_run, verdict)
from ci_support.transport import GhClient, records, find_run, checked_jobs
from ci_support.evidence import (inspect_report_archive, collect_artifacts, pack_evidence,
                                 emit_evidence, recover_evidence)
from ci_support.observer import observe_ci
from ci_support.runners import terminal_ci_status

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


def parse_recovery_binding(value):
    """Use the earlier Result's exact source/run/attempt, not current source bytes."""
    fields = {'repository', 'branch', 'workflow_path', 'commit_sha', 'bundle_number',
              'run_id', 'run_attempt', 'source_sha256', 'trigger_event', 'expected_mode',
              'workflow_commit_sha'}
    if (type(value) is not dict or set(value) != fields
            or value['repository'] != REPOSITORY or value['branch'] != 'dev'
            or value['workflow_path'] != WORKFLOW or value['source_sha256'] is None
            or any(type(value[key]) is not int or value[key] < 1 for key in ('run_id', 'run_attempt'))):
        raise CIObservationError('invalid_prior_ci_binding')
    request = Request(value['commit_sha'], value['bundle_number'], value['source_sha256'],
                      event=value['trigger_event'], expected_mode=value['expected_mode'],
                      workflow_commit=value['workflow_commit_sha'])
    return request, value['run_id'], value['run_attempt']


def attach_prior_evidence(summary, files, prior_summary, prior_files):
    """Keep independent run evidence in one existing Result transport frame."""
    summary['prior_ci'] = {key: prior_summary.get(key) for key in (
        'repository', 'branch', 'workflow_path', 'commit_sha', 'bundle_number', 'source_sha256',
        'trigger_event', 'expected_mode', 'workflow_commit_sha',
        'run_id', 'run_attempt', 'run_binding_confirmed', 'github_conclusion', 'ci_status',
        'started_at', 'ended_at', 'evidence_complete', 'test_evidence_verified',
        'observed_failures', 'errors')}
    summary['prior_ci']['evidence_file'] = None
    raw = pack_evidence(prior_files)
    files['prior-ci-evidence.zip'] = raw
    summary['prior_ci']['evidence_file'] = 'prior-ci-evidence.zip'
    summary['files'] = {name: {'size': len(value), 'sha256': sha256(value).hexdigest()}
                       for name, value in files.items() if name != 'summary.json'}
    files['summary.json'] = json_bytes(summary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--bundle', type=int)
    parser.add_argument('--event', choices=('workflow_dispatch', 'push'), default='workflow_dispatch')
    parser.add_argument('--mode', choices=('both', 'parallel'), default='both')
    parser.add_argument('--workflow-commit', help='Dispatch revision when testing an older exact commit')
    parser.add_argument('--run-id', type=int)
    parser.add_argument('--attempt', type=int)
    parser.add_argument('--source-sha256', help='Explicit source identity from the bound Result')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--push-failed', action='store_true')
    parser.add_argument('--recover-prior', type=Path,
                        help='Closed JSON binding from an earlier Result; read-only exact-attempt recovery')
    args = parser.parse_args(argv)
    if (args.run_id is None) != (args.attempt is None) or any(
            value is not None and value < 1 for value in (args.run_id, args.attempt)):
        parser.error('--run-id and --attempt must be supplied together as positive integers')
    try:
        source = args.source_sha256
        if source is None:
            # Never bind a historical SHA to whatever happens to be checked out.
            head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, check=True).stdout.decode().strip()
            if head != args.commit:
                raise CIObservationError('source_checkout_mismatch_use_bound_source_sha256')
            from verification_support.identity import source_identity
            source = source_identity(ROOT)
        request = Request(args.commit, args.bundle, source, event=args.event,
                          expected_mode=args.mode, workflow_commit=args.workflow_commit)
    except (CIObservationError, OSError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    previous_binding = None
    prior = None
    if args.recover_prior is not None:
        try:
            raw_binding = args.recover_prior.read_bytes()
            if len(raw_binding) > 16 * 1024:
                raise CIObservationError('oversized_prior_ci_binding')
            previous, run_id, attempt = parse_recovery_binding(decode_json(raw_binding))
        except (CIObservationError, OSError) as error:
            parser.error(str(error))
        previous_binding = previous, run_id, attempt
    if args.push_failed:
        summary = {'format_version': 1, 'local_apply': 'not_observed', 'ci_status': 'not_published',
                   'commit_sha': request.commit, 'bundle_number': request.bundle,
                   'repository': REPOSITORY, 'expected_mode': request.mode, 'evidence_complete': False,
                   'trigger_event': request.event, 'workflow_commit_sha': request.run_commit}
        files = {'summary.json': json_bytes(summary)}
    else:
        summary, files = observe_ci(request, progress=show_progress,
                                    pinned_run_id=args.run_id, pinned_attempt=args.attempt)
    if previous_binding is not None:
        if summary['ci_status'] == 'observation_interrupted':
            summary['prior_recovery_skipped'] = 'observation_interrupted'
            files['summary.json'] = json_bytes(summary)
        else:
            previous, run_id, attempt = previous_binding
            print(f'CI recovery: bundle {previous.bundle}, run {run_id}, attempt {attempt}', flush=True)
            prior = observe_ci(previous, progress=show_progress,
                               pinned_run_id=run_id, pinned_attempt=attempt)
    try:
        if prior is not None:
            attach_prior_evidence(summary, files, *prior)
        raw = pack_evidence(files)
    except CIObservationError:
        summary.update(evidence_complete=False, test_evidence_verified=False,
                       logs_captured=False, capture_complete=False, job_logs_captured=[])
        summary['transport_dropped_files'] = sorted(name for name in files if name != 'summary.json')
        summary['files'] = {}
        if 'prior_ci' in summary:
            summary['prior_ci']['evidence_file'] = None
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
    print(f"\033[{color}mLOCAL APPLY: NOT OBSERVED | CI: {terminal_ci_status(summary['ci_status'])}\033[0m", flush=True)
    # Exit 0 describes a completed observation. ci_status carries the CI result.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
