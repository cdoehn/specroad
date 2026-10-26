"""Derive effects and exact crash prefixes from the immutable Restore binding.

A position is explanatory metadata, never evidence that an effect happened.
Recovery matches the complete observed inventory against these states.
"""
from ._codec import file_row
from .values import require


def publication_program(layout):
    active, archive, own = (layout[k] for k in ('active', 'archive', 'own'))
    program = [('create', active + '/intent.json'), ('create', archive + '/plan.json')]
    program += [('create', p) for p in sorted(own) if p.startswith(archive + '/objects/')]
    program += [('create', archive + '/manifest.json')]
    program += [('create', p) for p in layout['staged'].values()]
    program += [('create', active + '/prepared.json'), ('create', active + '/committing.json')]
    for i, path in enumerate(layout['changes']):
        program.append(('publish', path, layout['staged'][path]) if path in layout['target']
                       else ('remove', path))
        program.append(('create', active + '/effects/' + str(i) + '.json'))
    program.append(('create', archive + '/completed.json'))
    for i, move in enumerate(layout['binding']['archive_moves']):
        program += [('move', move['source'], move['target']),
                    ('create', active + '/archived/' + str(i) + '.json')]
    program.append(('move', active, layout['terminal']))
    return program


def parents(path, roots):
    for i in range(1, len(path.split('/'))):
        parent = '/'.join(path.split('/')[:i])
        if any(parent == r or parent.startswith(r + '/') for r in roots):
            yield parent


def effect(state, operation, layout, roots):
    """Pure expected membership, independently compared with actual bytes."""
    kind, path, *rest = operation
    if kind == 'create':
        state[path] = {**file_row(path, layout['own'][path]), 'kind': 'file'}
    elif kind == 'publish':
        del state[rest[0]]
        state[path] = {**file_row(path, layout['target'][path]), 'kind': 'file'}
    elif kind in ('remove', 'rmdir'):
        del state[path]
        if path in roots:
            state[path] = {'path': path, 'kind': 'missing'}
    elif kind == 'move':
        for old in list(state):
            if old == path or old.startswith(path + '/'):
                new = rest[0] + old[len(path):]
                state[new] = {**state.pop(old), 'path': new}
    else:
        raise ValueError('Unknown bound Restore effect')


def prefixes(initial, program, layout, roots):
    state = {r['path']: dict(r) for r in initial}
    for index, operation in enumerate(program):
        yield index, dict(state)
        if operation[0] in ('create', 'publish', 'move'):
            destination = operation[2] if operation[0] == 'move' else operation[1]
            for parent in parents(destination, roots):
                if state.get(parent, {}).get('kind') != 'directory':
                    require(state.get(parent, {}).get('kind') in (None, 'missing'),
                            'restore_parent_collision', path=parent, exit_code=7)
                    state[parent] = {'path': parent, 'kind': 'directory'}
                    yield index, dict(state)
        effect(state, operation, layout, roots)
    yield len(program), state


def overlay(state, evidence):
    result = dict(state)
    for path, row in evidence.items():
        require(path not in result or result[path] == row or result[path]['kind'] == 'missing',
                'restore_evidence_collision', path=path, exit_code=6)
        result[path] = row
    return result


def match_prefix(observed, initial, program, layout, roots, *, evidence=None):
    actual = {r['path']: r for r in observed}
    match = None
    for index, state in prefixes(initial, program, layout, roots):
        if overlay(state, evidence or {}) == actual:
            match = (index, state)
    require(match is not None, 'restore_unexplained_execution_state', exit_code=6)
    return match
