"""Synthetic known origins, explicitly supplied rather than discovered ancestry."""
from copy import deepcopy
import json

from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.snapshots.inventory import source_resource_rows
from test_merge_inventory import bind_files

ROLES = ('base', 'ours', 'theirs')


def history_for(sources):
    observations = []
    for role in ROLES:
        rows, _ = source_resource_rows(getattr(sources, role))
        for identity, _ in rows.values():
            if identity['kind'] in ('attachment', 'archive'):
                continue
            observations.append({'role': role, 'identity': identity,
                'origin': {'namespace': 'synthetic-known-history',
                           'creation_event': 'fixture-created:' + jcs(identity).decode()}})
    return {'history_format_version': 'merge-history-input-v1',
            'source_bindings_sha256': sources.sha256, 'observations': observations}


def bound_relations(root, original, values):
    """Every variant is a real fully qualified project, never a fake root hash."""
    path = next(path for path in original if path.startswith('spec/goals/'))
    variants = []
    for relations in values:
        files = dict(original); owner = json.loads(files[path]); owner['relations'] = deepcopy(relations)
        files[path] = jcs(owner); variants.append(files)
    sources = bind_files(root, variants)
    return sources, history_for(sources), owner['id']


def relation_observation(history, role='ours', number=1):
    from support.relations import rid
    return next(row for row in history['observations']
                if row['role'] == role and row['identity']['kind'] == 'relation'
                and row['identity']['id'] == rid(number))


def edge(**changes):
    from support.relations import edge as native_edge, aid
    values = {'kind': 'conflicts_with', 'target': aid(number=0)}
    values.update(changes)
    return native_edge(**values)
