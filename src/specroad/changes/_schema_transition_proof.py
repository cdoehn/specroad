"""Shared, read-only byte proofs for the schema-transition writer and recovery.

No lock acquisition, authority callback, namespace mutation or test policy.
"""
from hashlib import sha256
from ..bundles.migration_source import verify_source_backup
from ..migration.plan_values import file_bindings
from ..migration.transaction_target import materialized_files
from .schema_transition_values import SchemaTransitionError, require, transaction_receipt
from ._schema_transition_io import read


def _backup(journal, raw):
    descriptor = journal.data['backup']
    require(len(raw) == descriptor['size'], 'transition_backup_changed')
    from ._snapshot_dispatch import verify_backup, recheck_source
    backup = verify_backup(journal.plan,raw,descriptor)
    op = journal.plan.data['operations'][0]
    require(file_bindings(backup.files) == op['source_files'], 'transition_source_binding')
    recheck_source(journal.plan,backup.files)
    return backup



def _images(journal, backup):
    images = {'source.zip': backup.source_bytes}
    target = materialized_files(journal.plan, backup.files)
    for index, row in enumerate(journal.plan.data['operations'][0]['changes']):
        path = row['path']
        if path in backup.files: images['before/' + str(index) + '.bin'] = backup.files[path]
        if path in target: images['staging/' + str(index) + '.bin'] = target[path]
    return images



def _verify_images(files, prefix, journal, backup, *, partial=False):
    from ..migration._backup_source import _scan
    originals = {p[len(prefix)+1:]: read(files, p) for p in _scan(files)
                 if p.startswith(prefix + '/')}
    verify_owned_images(originals, journal, backup, partial=partial)


def verify_owned_images(originals, journal, backup, *, partial=False):
    """Same exact native byte proof, without filesystem authority or root claims."""
    expected = _images(journal, backup)
    names = tuple(originals)
    required = {'journal.json'} | (set() if partial else set(expected))
    require(required <= set(names), 'transition_images_missing')
    for name in names:
        raw = originals[name]
        if name == 'journal.json':
            require(raw == journal.source_bytes, 'transition_journal_changed')
        elif name in expected:
            require(raw == expected[name] or partial and expected[name].startswith(raw), 'transition_image_changed')
        elif name.startswith('journal.') and name.endswith('.pending'):
            possible = [journal.successor(state, count).source_bytes
                for state, count in ((journal.data['state'], journal.data['published_count']),
                    ('prepared',0), ('committing',journal.data['published_count']),
                    ('committing',min(len(journal.plan.data['operations'][0]['changes']),journal.data['published_count']+1)),
                    ('rolling_back',journal.data['published_count']),
                    ('rolling_back',max(0,journal.data['published_count']-1)),
                    ('rolled_back',0), ('committed',len(journal.plan.data['operations'][0]['changes'])))]
            if journal.data['state'] == 'committing':
                # Recovery may observe one completed effect whose journal ack
                # was lost. Its first rollback marker binds that proven count.
                # This permits only the deterministic marker bytes; the actual
                # source/target prefix is still checked independently.
                count = min(len(journal.plan.data['operations'][0]['changes']),
                            journal.data['published_count'] + 1)
                possible.append(journal.successor('rolling_back', count).source_bytes)
            require(any(name == 'journal.' + sha256(value).hexdigest() + '.pending'
                        and value.startswith(raw) for value in possible),
                    'transition_pending_journal_changed')
        elif name.startswith('moves/') and name.endswith('.bin'):
            possible = [(p, b) for p, b in backup.files.items()] + list(materialized_files(journal.plan, backup.files).items())
            require(any(name == 'moves/' + sha256((p + ':' + sha256(b).hexdigest()).encode()).hexdigest() + '.bin'
                        and b.startswith(raw) for p, b in possible), 'transition_pending_image_changed')
        elif name.startswith('recovery-') and name.endswith('.json'):
            from .schema_transition_recovery import check_recovery_intent
            check_recovery_intent(name,raw,journal)
        elif name == 'transaction.json' and journal.data['state'] == 'committed':
            require(transaction_receipt(journal).startswith(raw), 'transition_receipt_changed')
        else:
            raise SchemaTransitionError('transition_unknown_work')


def _prefix(journal, source, actual):
    """Derive the actual complete effect prefix, independently of the cursor."""
    changes = journal.plan.data['operations'][0]['changes']
    target = materialized_files(journal.plan, source)
    changed = {r['path'] for r in changes}
    require({p: b for p, b in actual.items() if p not in changed} ==
            {p: b for p, b in source.items() if p not in changed}, 'transition_unrelated_files_changed')
    count = 0; before_seen = False
    for row in changes:
        p = row['path']; observed = actual.get(p)
        if observed == target.get(p) and not before_seen:
            count += 1
        elif observed == source.get(p): before_seen = True
        else: raise SchemaTransitionError('transition_unproven_file_prefix')
    return count
