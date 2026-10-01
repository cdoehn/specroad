"""Native pending journals in owned temporary project roots."""
from pathlib import Path
from specroad.changes import (RecoveryAuthority, project_lock, begin_building_journal,
                              stage_building_journal, discard_unpublished_transaction)
from .publication import prepared, options, ALLOW, TRANSACTION
from .targets import ACTOR

RECOVER = RecoveryAuthority('test-recovery-authorizer', '1', lambda request: True)


def pending(root, state='building', **kwargs):
    m, p, c = prepared(root, **kwargs)
    with project_lock(root, **options(c)) as held:
        j = begin_building_journal(c, held_lock=held, transaction_id=TRANSACTION, authority=ALLOW)
        if state == 'prepared':
            j = stage_building_journal(c, j, held_lock=held, authority=ALLOW)
    return m, p, c, j


def recovery_options(c, **overrides):
    return {**options(c), 'kind': 'recovery', 'command': 'recover discard', **overrides}


def discard(c, j, held, **kwargs):
    return discard_unpublished_transaction(c, TRANSACTION, held_lock=held,
        authority=kwargs.pop('authority', RECOVER), actor=kwargs.pop('actor', ACTOR),
        reason=kwargs.pop('reason', 'Explicit unpublished preparation discard'),
        expected_journal_sha256=kwargs.pop('expected_journal_sha256', j.sha256), **kwargs)


def tree(root):
    """All regular bytes, including operational evidence and the current lock."""
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in Path(root).rglob('*') if p.is_file()}
