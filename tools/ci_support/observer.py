"""Observe a fixed commit/run/attempt without controlling Git or test scheduling."""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import time
import zipfile
from .contract import (Request, REPOSITORY, WORKFLOW, PYTHONS, MAX_BYTES,
                       CIObservationError, json_bytes, exact_run, verdict)
from .transport import GhClient, find_run, checked_jobs
from .evidence import collect_artifacts

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
        reports, artifact_errors = collect_artifacts(client, request, run_id, attempt, files, retry=retry)
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


