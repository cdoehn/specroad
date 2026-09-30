"""CI request, bounded evidence encoding and strict API JSON primitives."""
from __future__ import annotations
from dataclasses import dataclass
import json
import re

REPOSITORY = 'cdoehn/specroad'
WORKFLOW = '.github/workflows/behavior.yml'
PYTHONS = ('3.10', '3.11', '3.12', '3.13', '3.14')
MAX_BYTES = 64 * 1024 * 1024
PREFIX = 'SPECRoad-CI-EVIDENCE-V1 '

class CIObservationError(ValueError):
    """Unavailable/mismatched external observation, not a local apply failure."""

    def __init__(self, reason, *, http_status=None, returncode=None):
        super().__init__(reason)
        # Only numeric transport metadata is retained, never raw gh diagnostics.
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        self.returncode = returncode if type(returncode) is int else None


def error_record(phase, error):
    record = {'phase': phase, 'reason': str(error)[:200]}
    if isinstance(error, CIObservationError):
        for key in ('http_status', 'returncode'):
            if getattr(error, key) is not None:
                record[key] = getattr(error, key)
    return record


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


