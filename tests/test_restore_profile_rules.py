"""Restore qualifies actual installed profile/SRX rules before any write."""
from hashlib import sha256

import pytest

from specroad.archive.project_snapshot import build_project_baseline_manifest
from specroad.bundles import prepare_project_bundle
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.recovery import RestoreError, prepare_restore_plan
from support.domain import domain_value
from support.inspection import inspection_project
from support.model import put
from support.profile_composition import lint, profile
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
@pytest.mark.parametrize('satisfied', [True, False])
def test_full_restore_executes_bound_profile_rules_and_preserves_the_resource(tmp_path, kind, satisfied):
    rule = lint('restore:goal-title', severity='error')
    rule['artifact_types'] = ['goal']
    rule['program']['expression'] = {'op': 'eq', 'args': [
        {'op': 'field', 'context': 'artifact', 'pointer': '/title'},
        {'op': 'literal', 'value': 'Matching title'}]}
    local = profile('restore-local', lint_rules=[rule])
    origin, current = tmp_path / 'origin', tmp_path / 'current'
    model = inspection_project(origin, extra_profiles=(local,),
        artifacts=[record_value('document'), domain_value('goal',
            title='Matching title' if satisfied else 'Different title')])
    current.mkdir()
    for path, raw in model.source_files.items():
        put(current, path, raw)
    if kind == 'project_bundle':
        path, raw, extra = 'project.zip', prepare_project_bundle(origin).source_bytes, {}
        expected_profile_hash = sha256(local.source_bytes).hexdigest()
    else:
        snapshot = build_project_baseline_manifest(model, baseline_id=ref('BASE'))
        expected_profile_hash = next(row['sha256'] for row in snapshot.data['manifest']
            if row.get('source_path') == 'profiles/restore-local.json')
        value = record_value('baseline', **{key: snapshot.data[key] for key in
            ('scope_descriptor', 'manifest', 'model_root_sha256', 'configuration_hash', 'profiles', 'tool_version')})
        path, raw = artifact_path('baseline', value['id'], 'SR'), canonical_json_bytes(value)
        for item in snapshot.objects:
            put(origin, item.reference.path, item.content)
        extra = {'default_locale': 'en-GB', 'generated_path': 'output'}
    put(origin, path, raw)
    before = inventory(tmp_path)
    with no_write_attempts():
        if satisfied:
            plan = prepare_restore_plan(project_root=current, source_root=origin,
                source_kind=kind, source_path=path, **extra)
            saved = next(row for row in plan.data['target']['entries']
                if row['path'] == 'profiles/restore-local.json')
            assert saved['sha256'] == expected_profile_hash
        else:
            with pytest.raises(RestoreError) as failed:
                prepare_restore_plan(project_root=current, source_root=origin,
                    source_kind=kind, source_path=path, **extra)
            assert failed.value.exit_code == 3
            assert not failed.value.mutation_possible
    assert inventory(tmp_path) == before
