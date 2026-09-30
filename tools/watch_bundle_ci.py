"""Wait for exact bundle CI and carry complete evidence in execution.log.

GitHub outcome and local commit success remain separate. No test bodies run here.
"""
import argparse
import json
from pathlib import Path
import sys

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
    print(f"\033[{color}mLOCAL APPLY: SUCCESS | CI: {terminal_ci_status(summary['ci_status'])}\033[0m", flush=True)
    # Exit 0 describes a completed observation. ci_status carries the CI result.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
