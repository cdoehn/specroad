"""Fixed-host gh GET requests and complete exact-run collections."""
import os
import re
import subprocess
from .contract import (REPOSITORY, MAX_BYTES, CIObservationError, decode_json, exact_run)

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
            status = re.search(rb'\(HTTP ([1-5][0-9]{2})\)', result.stderr)
            raise CIObservationError('gh_api_exit_' + str(result.returncode),
                http_status=None if status is None else int(status.group(1)),
                returncode=result.returncode)
        if len(result.stdout) > MAX_BYTES:
            raise CIObservationError('evidence_capture_limit')
        return result.stdout

    def document(self, endpoint):
        return decode_json(self.get(endpoint))


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


