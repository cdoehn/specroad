"""Closed original Restore audits, independent of today's mutable project."""
from types import SimpleNamespace

from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from ._codec import file_row
from .values import RestorePlan, require


def restore_audits(files, project_id):
    from ._execution_binding import checked_layout
    from ._execution_events import observed_events
    from ._execution_program import publication_program, prefixes, overlay
    retained = {}
    terminal_root = '.specroad/recovery/transaction-audit/restore-'
    for path, raw in files.items():
        if not path.startswith(terminal_root) or not path.endswith('/intent.json'):
            continue
        relative = path[len(terminal_root):].split('/')
        if len(relative) != 2:
            continue
        value = parse_json_object(raw)
        require(type(value.get('original_plan')) is dict and type(value.get('request')) is dict,
                'restore_historical_execution_invalid', path=path)
        plan = RestorePlan(canonical_json_bytes(value['original_plan']))
        require(plan.data['project_id'] == project_id, 'restore_historical_project_conflict', exit_code=6)
        project = SimpleNamespace(_root_identity=value['request'].get('root_identity'))
        layout = checked_layout(raw, plan, project)
        require(path == layout['terminal'] + '/intent.json', 'restore_historical_execution_path', exit_code=6)
        roots = plan.data['inventory']['roots']
        final = None
        for _, state in prefixes(plan.data['inventory']['entries'], publication_program(layout), layout, roots):
            final = state
        owned = lambda p: any(p == layout[k] or p.startswith(layout[k] + '/') for k in ('archive', 'terminal'))
        group = {p: b for p, b in files.items() if owned(p)}
        entries = {p: {**file_row(p, b), 'kind': 'file'} for p, b in group.items()}
        for p in group:
            for i in range(1, len(p.split('/'))):
                parent = '/'.join(p.split('/')[:i])
                entries.setdefault(parent, {'path': parent, 'kind': 'directory'})
        events = observed_events(layout, {'entries': list(entries.values())}, group)
        expected = {p: row for p, row in overlay(final, events).items() if owned(p) and row['kind'] == 'file'}
        require({p: row for p, row in entries.items() if owned(p) and row['kind'] == 'file'} == expected,
                'restore_historical_execution_incomplete', path=path, exit_code=6)
        require(not set(retained).intersection(group), 'restore_historical_execution_overlap', exit_code=6)
        retained.update(group)
    return retained
