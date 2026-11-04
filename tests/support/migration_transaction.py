"""Small real source/backup/plan fixtures; no stored success substitutes."""
from hashlib import sha256
from pathlib import Path
from .migration_plans import vector_source, target_inputs, FIELDS, planned_files
from .reference01 import encoded


def execution_inputs(files):
    import json
    from .languages import load_registry
    from specroad.storage.language_registry import registry_binding
    from specroad.migration.plan_values import unb64, b64
    inputs = target_inputs(files)
    config = json.loads(unb64(inputs['target_configuration']))
    registry = load_registry(); binding = registry_binding(registry)
    config['language_registry'] = binding
    inputs['target_configuration'] = b64(encoded(config))
    inputs['target_resources'].append({'path': binding['path'], 'bytes_base64': b64(registry.source_bytes)})
    inputs['target_resources'].sort(key=lambda row: row['path'])
    return inputs


def setup(tmp_path, *, files=None, fields=None, inputs=None):
    from specroad.migration.planning import plan_migration
    from specroad.migration.backup import create_source_backup
    from specroad.migration.plan_values import file_bindings
    from specroad.model.canonical import canonical_json_sha256
    from specroad.changes.publication_values import PublicationAuthority
    files = vector_source() if files is None else dict(files)
    root = tmp_path/'project'; root.mkdir()
    external = tmp_path/'backup'; external.mkdir()
    for name, raw in files.items():
        path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    report = plan_migration(files, inputs=execution_inputs(files) if inputs is None else inputs,
                            **{**FIELDS, **(fields or {})})
    assert report.ready
    plan = report.change_plan
    file_hash = canonical_json_sha256(file_bindings(files))
    backup = create_source_backup(root, output='source.zip', output_root=external,
                                   expected_source_files_sha256=file_hash)
    args = dict(expected_plan_sha256=plan.sha256, expected_inputs_sha256=plan.data['operations'][0]['inputs_sha256'],
        expected_target_version='0.2.0', transaction_id='synthetic-transition',
        backup_path=backup['file']['path'], backup_root=str(external),
        backup_sha256=backup['file']['sha256'], backup_size=backup['file']['size'],
        backup_source_files_sha256=file_hash,
        authority=PublicationAuthority('synthetic-host', '1', lambda request: True))
    return root, files, plan, args


def apply(root, plan, args):
    from specroad.migration.transaction import apply_migration_plan
    return apply_migration_plan(root, plan.source_bytes, **args)


def normative(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*')
            if p.is_file() and '.specroad' not in p.relative_to(root).parts and '.git' not in p.relative_to(root).parts}


def journal_path(root, args):
    return root/'.specroad/transactions'/args['transaction_id']/'journal.json'
