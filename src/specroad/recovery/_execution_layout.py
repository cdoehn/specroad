"""Exact local evidence layout derived before any Restore write.

The journal names itself and binds every other own file by bytes and hash.
No self-referential hash is invented. Future recovery must reconstruct this
layout from the original plan/request, not trust an arbitrary owned-path list.
"""
from base64 import b64decode

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ._codec import file_row
from ._operational_history import operational_path


def execution_layout(plan, request, authority):
    data = plan.data
    token = canonical_json_sha256(request)
    active = '.specroad/recovery/restore-' + token
    archive = '.specroad/recovery/archive/' + token
    terminal = '.specroad/recovery/transaction-audit/restore-' + token
    objects = {r['sha256']: b64decode(r['data_base64'], validate=True) for r in data['objects']}
    target = {r['path']: objects[r['sha256']] for r in data['target']['entries']}
    before = {r['path']: r for r in data['inventory']['entries'] if r['kind'] == 'file'}
    changes = sorted({p for p in before if not operational_path(p) and p not in target}
        | {p for p, raw in target.items() if before.get(p) != {**file_row(p, raw), 'kind': 'file'}},
        key=lambda p: p.encode('utf-8'))
    effects = [{'path': p, 'before': before.get(p),
                'after': None if p not in target else file_row(p, target[p])} for p in changes]
    staged = {p: active + '/staging/' + str(i) for i, p in enumerate(target)}
    manifest = {'format_version': 'restore-backup-v1', 'request_sha256': token,
                'inventory': data['inventory'], 'backup': data['backup']}
    own = {archive + '/plan.json': plan.source_bytes,
           archive + '/manifest.json': canonical_json_bytes(manifest)}
    for digest in sorted({r['sha256'] for r in data['backup']['entries']}):
        own[archive + '/objects/' + digest] = objects[digest]
    own.update({staged[p]: raw for p, raw in target.items()})
    for state in ('prepared', 'committing'):
        own[active + '/' + state + '.json'] = canonical_json_bytes({'state': state, 'request_sha256': token})
    for index, effect in enumerate(effects):
        own[active + '/effects/' + str(index) + '.json'] = canonical_json_bytes({
            'request_sha256': token, 'index': index, **effect})
    moves = [{'source': row['path'], 'target': archive + '/originals/' + str(i),
              'inventory_sha256': row['sha256']}
             for i, row in enumerate(request['affected_journals']['entries'])]
    for i, move in enumerate(moves):
        own[active + '/archived/' + str(i) + '.json'] = canonical_json_bytes({'request_sha256': token, **move})
    completed = {'format_version': 'restore-completion-v1', 'request_sha256': token,
        'request': request, 'result': 'restored', 'expected_target_root': data['expected_target_root'],
        'backup_manifest_sha256': canonical_json_sha256(manifest),
        'authority_id': authority.authority_id, 'authority_version': authority.version,
        'historical_findings': list(plan.history_assessments)}
    own[archive + '/completed.json'] = canonical_json_bytes(completed)
    journal_path = active + '/intent.json'
    directories = set()
    for path in [*own, journal_path, terminal, *(m['target'] for m in moves), *changes]:
        directories.update('/'.join(path.split('/')[:i]) for i in range(1, len(path.split('/'))))
    original = {r['path']: r['kind'] for r in data['inventory']['entries']}
    # Parent directories outside the original roots (notably .specroad itself)
    # are also explicitly named; the native lock owns its separate metadata.
    own_directories = sorted((p for p in directories if original.get(p) != 'directory'),
                             key=lambda p: p.encode('utf-8'))
    binding = {'format_version': 'restore-execution-v1', 'execution_id': token,
        'request': request, 'authority_id': authority.authority_id, 'authority_version': authority.version,
        'original_plan': data, 'journal_path': journal_path,
        'own_files': [file_row(p, own[p]) for p in sorted(own, key=lambda p: p.encode('utf-8'))],
        'own_directories': own_directories, 'effects': effects, 'archive_moves': moves,
        'terminal_move': {'source': active, 'target': terminal}}
    own[journal_path] = canonical_json_bytes(binding)
    return {'token': token, 'active': active, 'archive': archive, 'terminal': terminal,
            'own': own, 'target': target, 'changes': changes, 'staged': staged,
            'binding': binding, 'completed': completed}
