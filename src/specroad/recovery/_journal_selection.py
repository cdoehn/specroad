"""Explicit original-inventory selection; observation never grants authority."""
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.operational_paths import passive_journal_directory
from ..storage.json_syntax import parse_json_object
from ._codec import safe_path, digest as hash_value
from .values import require, RestoreError


def journal_selection(plan, raw, active):
    data = plan.data
    expected_plan = data['restore_plan_sha256']
    value = ({'format_version': 'restore-journal-selection-v1',
              'restore_plan_sha256': expected_plan, 'entries': []}
             if raw is None else parse_json_object(raw))
    require(raw is None or type(raw) is bytes and canonical_json_bytes(value) == raw,
            'restore_selection_canonical_bytes_required')
    require(set(value) == {'format_version', 'restore_plan_sha256', 'entries'}
            and value['format_version'] == 'restore-journal-selection-v1'
            and type(value['entries']) is list, 'restore_selection_invalid')
    hash_value(value['restore_plan_sha256'])
    require(value['restore_plan_sha256'] == expected_plan, 'restore_selection_plan_conflict', exit_code=6)
    selected = []
    backup = {r['path']: r for r in data['backup']['entries']}
    for entry in value['entries']:
        require(type(entry) is dict and set(entry) == {'path', 'sha256'}, 'restore_selection_entry_invalid')
        path = safe_path(entry['path'])
        hash_value(entry['sha256'])
        parts = path.split('/')
        require(len(parts) == 3 and parts[0] == '.specroad'
                and parts[1] in ('transactions', 'recovery')
                and not passive_journal_directory(parts[1], parts[2])
                and parts[2] != 'archive', 'restore_selection_area_forbidden', path=path, exit_code=7)
        rows = [r for r in data['inventory']['entries']
                if r['path'] == path or r['path'].startswith(path + '/')]
        require(rows and rows[0]['path'] == path and rows[0]['kind'] in ('file', 'directory'),
                'restore_selection_missing_original', path=path, exit_code=6)
        require(canonical_json_sha256(rows) == entry['sha256'],
                'restore_selection_inventory_conflict', path=path, exit_code=6)
        require(path in active, 'restore_selection_not_active', path=path, exit_code=7)
        for row in rows:
            if row['kind'] == 'file':
                require(backup.get(row['path']) == {k: row[k] for k in ('path', 'size', 'sha256')},
                        'restore_selection_backup_missing', path=row['path'])
        selected.append(path)
    require(selected == sorted(set(selected), key=lambda p: p.encode('utf-8')),
            'restore_selection_order_invalid')
    if set(active) != set(selected):
        raise RestoreError('restore_unselected_journals', exit_code=5, recovery_required=True)
    return value
