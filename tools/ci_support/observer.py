"""Observe a fixed commit/run/attempt without controlling Git or test scheduling."""
from datetime import datetime, timezone
from hashlib import sha256
import time
from .contract import (Request, REPOSITORY, WORKFLOW, PYTHONS,
                       CIObservationError, json_bytes, exact_run, verdict, error_record)
from .transport import GhClient, find_run, checked_jobs
from .evidence import capture_attempt_files


def observe_ci(request, *, client=None, progress=None, sleeper=None, discovery_polls=60,
               poll_seconds=5, pinned_run_id=None, pinned_attempt=None):
    """Wait for an exact manual run or recover an explicitly pinned historical attempt.

    Normal observation detects a changing latest attempt. Explicit recovery uses
    the historical attempt endpoint throughout, never a newer successful rerun.
    A transport outage preserves already observed failures and tries to salvage
    logs/reports, but it cannot establish a final successful CI result.
    """
    if type(request) is not Request or type(discovery_polls) is not int or discovery_polls < 1:
        raise CIObservationError('invalid_observation_request')
    pinned = pinned_run_id is not None or pinned_attempt is not None
    if pinned and any(type(value) is not int or value < 1 for value in (pinned_run_id, pinned_attempt)):
        raise CIObservationError('invalid_run_pin')
    client = GhClient() if client is None else client
    progress = (lambda event: None) if progress is None else progress
    sleeper = time.sleep if sleeper is None else sleeper
    files, jobs = {}, []
    capture_started = False
    run_verified = False
    summary = {'format_version': 1, 'local_apply': 'not_observed', 'ci_status': 'unavailable',
        'repository': REPOSITORY, 'workflow_path': WORKFLOW, 'branch': 'dev',
        'commit_sha': request.commit, 'bundle_number': request.bundle, 'expected_mode': request.mode,
        'trigger_event': request.event, 'workflow_commit_sha': request.run_commit,
        'source_sha256': request.source_sha256, 'python_matrix': list(PYTHONS),
        'run_id': pinned_run_id, 'run_attempt': pinned_attempt, 'pinned_attempt': pinned,
        'run_binding_confirmed': False, 'github_conclusion': None, 'observed_failures': [],
        'logs_captured': False, 'job_logs_captured': [], 'capture_complete': False,
        'evidence_complete': False, 'test_evidence_verified': False,
        'started_at': datetime.now(timezone.utc).isoformat(), 'errors': []}

    def retry(call):
        for count in range(3):
            try:
                return call()
            except CIObservationError as error:
                if count == 2:
                    raise
                event = error_record('retry', error)
                event['attempt'] = count + 1
                progress(event)
                sleeper(poll_seconds)

    try:
        if pinned:
            run_id, attempt = pinned_run_id, pinned_attempt
        else:
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
        run_path = f'repos/{REPOSITORY}/actions/runs/{run_id}'
        if pinned:
            run_path += f'/attempts/{attempt}'
        while True:
            run = exact_run(retry(lambda: client.document(run_path)), request,
                            run_id=run_id, attempt=attempt)
            run_verified = True
            summary['run_binding_confirmed'] = True
            summary['github_conclusion'] = run.get('conclusion')
            # Save the latest verified run even if the following jobs call fails.
            files['run.json'] = json_bytes(run)
            jobs = retry(lambda: checked_jobs(client, request, run_id, attempt))
            files['jobs.json'] = json_bytes(jobs)
            summary['observed_failures'] = [
                {'job_id': j['id'], 'name': j['name'], 'conclusion': j.get('conclusion')}
                for j in jobs if j.get('conclusion') in (
                    'failure', 'timed_out', 'cancelled', 'startup_failure', 'action_required', 'stale')]
            progress({'phase': 'running', 'run_id': run_id, 'attempt': attempt, 'status': run['status'],
                'jobs': [{'name': j['name'], 'status': j.get('status'), 'conclusion': j.get('conclusion'),
                         'steps': j['steps']} for j in jobs]})
            if run['status'] == 'completed':
                break
            sleeper(poll_seconds)
        summary['ci_status'] = verdict(run, jobs, request)
        capture_started = True
        capture_attempt_files(client, request, run_id, attempt, jobs, files, summary, retry=retry)
        # A dispatch can select a different test SHA. A green workflow alone
        # cannot prove that the requested revision was tested in both modes.
        if (request.event == 'workflow_dispatch' and summary['ci_status'] == 'success'
                and not summary['test_evidence_verified']):
            summary['ci_status'] = 'incomplete'
            summary['errors'].append({'phase': 'binding',
                'reason': 'manual_test_binding_or_full_evidence_unverified'})
        # Normal observation still rejects a changing latest attempt. Explicit
        # recovery rechecks the pinned historical attempt, not that latest run.
        last = exact_run(retry(lambda: client.document(run_path)), request,
                         run_id=run_id, attempt=attempt)
        if last['status'] != 'completed' or last.get('conclusion') != run.get('conclusion'):
            raise CIObservationError('run_changed_during_capture')
    except KeyboardInterrupt:
        summary['ci_status'] = 'observation_interrupted'
        summary['evidence_complete'] = False
        summary['test_evidence_verified'] = False
        summary['errors'].append({'phase': 'observation', 'reason': 'keyboard_interrupt'})
    except (CIObservationError, OSError) as error:
        summary['ci_status'] = 'unavailable'
        summary['errors'].append(error_record('observation', error))
        transport_failure = (isinstance(error, OSError)
            or str(error).startswith('gh_api_exit_')
            or str(error) == 'gh_unavailable_or_api_timeout')
        # Never salvage through an integrity mismatch, retry an already failed
        # capture, cancel CI, or silently discard a completed failed job.
        if run_verified and not capture_started and transport_failure:
            progress({'phase': 'partial_capture', 'run_id': run_id, 'attempt': attempt})
            try:
                capture_attempt_files(client, request, run_id, attempt, jobs, files, summary, retry=retry)
            except KeyboardInterrupt:
                summary['ci_status'] = 'observation_interrupted'
                summary['errors'].append({'phase': 'partial_capture', 'reason': 'keyboard_interrupt'})
            except (CIObservationError, OSError) as capture_error:
                summary['errors'].append(error_record('partial_capture', capture_error))
        summary['evidence_complete'] = False
        summary['test_evidence_verified'] = False
    summary['ended_at'] = datetime.now(timezone.utc).isoformat()
    summary['files'] = {name: {'size': len(raw), 'sha256': sha256(raw).hexdigest()} for name, raw in files.items()}
    files['summary.json'] = json_bytes(summary)
    return summary, files
