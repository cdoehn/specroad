"""Real native sources with explicitly known synthetic creation histories."""
from copy import deepcopy
import json

from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.paths import artifact_path
from support.merge_relations import history_for
from test_merge_inventory import bind_files


def bound_records(root, original, path, variants):
    files = []
    for value in variants:
        current = dict(original)
        if value is None:
            current.pop(path, None)
        else:
            current[path] = value if type(value) is bytes else jcs(value)
        files.append(current)
    sources = bind_files(root, files)
    return sources, history_for(sources)


def changed(value, **changes):
    result = deepcopy(value)
    result.update(changes)
    return result


def artifact(original, kind='goal'):
    path, raw = next((path, raw) for path, raw in original.items()
                     if path.startswith('spec/') and json.loads(raw)['artifact_type'] == kind)
    return path, json.loads(raw)


def decision(result, identifier):
    return next(row for row in result.data['decisions'] if row['identity']['id'] == identifier)


def with_successors(original, old, *, sides=((), (), ())):
    from support.domain import domain_value
    from support.relations import aid, edge
    result = []
    for numbers in sides:
        files = dict(original)
        for number in (1, 2):
            value = domain_value('goal', id=aid('goal', number=number))
            value['relations'] = ([edge(kind='supersedes', target=old['id'], number=number)]
                                  if number in numbers else [])
            files[artifact_path('goal', value['id'], 'SR')] = jcs(value)
        result.append(files)
    return result
