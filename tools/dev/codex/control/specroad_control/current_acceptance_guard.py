"""Passive current-state and original-attempt guards, independent of the CLI."""
from hashlib import sha256

from .current_acceptance_history import active
from .current_acceptance_proof import checked, fail, stable
from .job_contract import scope
from .local import read_private


def blocked_evidence(engine, doc):
    from .blocked_authorization_proof import evidence
    return evidence(engine, doc)  # Preserve the path in the immutable original request.

def guard_inputs(engine, ledger, doc):
    if (scope(engine.config) != doc['scope']
            or sha256(read_private(engine.paths.config)).hexdigest() != doc['config_sha256']):
        fail('Configuration changed after explicit acceptance.')
    if doc['mode'] == 'same_blocked' and blocked_evidence(engine, doc) != doc['evidence']:
        fail('Original blocked completion changed.')
    if doc['mode'] == 'same_ready':
        directory = engine.paths.state / 'jobs' / doc['target']['sha256']
        completed = active(ledger, doc['target']['sha256']) is not None
        if directory.is_symlink():
            fail('The original attempt directory changed.')
        if directory.exists():
            for path in directory.rglob('*'):
                if path.is_symlink() or (path.is_file()
                        and not (completed and path.relative_to(directory).parts[0] == 'accepted')):
                    fail('An original attempt appeared for the unissued Result.')

def verify(engine, ledger, doc, *, unused=True):
    guard_inputs(engine, ledger, doc)
    actual = checked(engine, doc['target'], unused=unused)
    if stable(actual) != stable(doc['artifacts']):
        fail('Pinned final Apply evidence changed.')
    guard_inputs(engine, ledger, doc)
    return actual

def guard_dispatch(engine, ledger, source):
    doc = active(ledger, source['sha256'])
    if doc is not None:
        verify(engine, ledger, doc)

def guard_original(engine, ledger, source):
    doc = active(ledger, source['sha256'])
    if doc is not None:
        guard_inputs(engine, ledger, doc)
