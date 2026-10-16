"""Real working-Baseline publication, immutable bytes and native failure gates."""
from base64 import b64decode, b64encode
from hashlib import sha256
import json
import os
from unittest.mock import patch

import pytest

from specroad.archive.creation import prepare_working_baseline, create_working_baseline
from specroad.archive.project_snapshot import build_project_baseline_manifest
from specroad.changes import (ChangePlan, ChangeOperation, prepare_change_plan, TargetModel,
    PublicationAuthority, read_transaction_completion)
from specroad.changes.target_model import _default_scope
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.storage.language_registry import bundled_language_registry, registry_binding
from specroad.storage.project import ProjectSource
from specroad.validation import ModelDocument
from support.change_plans import operation
from support.model import put, configuration_value
from support.domain import domain_value, approved_value
from support.languages import load_registry
from support.profiles import profile_data
from support.read_only import inventory, no_write_attempts
from support.records import ref
from test_artifact_creation import ACTOR, TIME, ALLOW


def project(root, *, bundled=False, broken=False):
    root.mkdir()
    registry = bundled_language_registry() if bundled else load_registry()
    binding = registry_binding(registry)
    configuration = configuration_value(language_registry=binding)
    profile = ProfileResource(canonical_json_bytes(profile_data(profile_id='core')))
    effective = compose_profiles([profile], core_key=profile.key, language_registry=registry)
    artifact = domain_value('goal')
    if broken: artifact.pop('statement')
    info = root.stat()
    model = TargetModel(canonical_json_bytes(configuration),
        ProjectReadBinding(configuration['project_id'], str(root), (info.st_dev, info.st_ino)),
        [ModelDocument(artifact_path('goal', artifact['id'], 'SR'), canonical_json_bytes(artifact))],
        profile=effective, resource_files=[ModelDocument('profiles/core.json', profile.source_bytes),
                                         ModelDocument(binding['path'], registry.source_bytes)])
    for path, raw in model.source_files.items(): put(root, path, raw)
    (root / '.specroad/locks').mkdir(parents=True)
    (root / 'foreign.bin').write_bytes(b'untouched\0\xff')
    return model


def preview(model, **changes):
    fields = dict(baseline_id=ref('BASE'), name='Working snapshot', actor=ACTOR,
        planned_at=TIME, change_plan_id='CP-baseline', request_id='baseline-1')
    fields.update(changes)
    return prepare_working_baseline(model, **fields)


def plan_for(model):
    value = preview(model)
    assert value['target_validated'], value['diagnostics']
    return ChangePlan(canonical_json_bytes(value['plan']))


def apply(plan, model, **changes):
    fields = dict(transaction_id='txn-baseline', authority=ALLOW)
    fields.update(changes)
    return create_working_baseline(plan, model, **fields)


def changed_plan(plan, mutate):
    data = plan.data
    mutate(data)
    data.pop('change_plan_sha256')
    return prepare_change_plan(data)


def test_native_baseline_publishes_sealed_record_and_all_exact_objects(tmp_path):
    root = tmp_path / 'project'; model = project(root, bundled=True)
    before = {p: raw for p, raw in model.source_files.items()}
    base = model.manifest(model.artifacts, _default_scope())
    plan = plan_for(model)
    result = apply(plan, model)
    record = plan.data['operations'][0]['record']
    path = artifact_path('baseline', record['id'], 'SR')
    assert (root / path).read_bytes() == canonical_json_bytes(record)
    assert record['baseline_state'] == 'sealed' and record['maturity'] == 'approved'
    assert record['revision'] == 1 and record['created_by'] == record['updated_by'] == ACTOR
    assert record['created_at'] == record['updated_at'] == TIME
    assert record['model_root_sha256'] == base.sha256
    assert record['id'] not in {r['id'] for r in base.data['artifacts']}
    for row in record['manifest']:
        raw = (root / row['object_path']).read_bytes()
        assert len(raw) == row['size'] and sha256(raw).hexdigest() == row['sha256']
        if row['role'] == 'model_manifest': assert json.loads(raw) == base.data
    assert {row['role'] for row in record['manifest']} >= {
        'artifact', 'profile', 'language_registry', 'semantic_configuration', 'effective_profile', 'model_manifest'}
    for name, raw in before.items(): assert (root / name).read_bytes() == raw
    assert (root / 'foreign.bin').read_bytes() == b'untouched\0\xff'
    assert result['write_state'] == 'committed' and result['audit']['created_ids'] == [record['id']]
    assert result['completion']['current_target_verified'] and result['completion']['cleanup_completed']
    proof = read_transaction_completion(ProjectSource(root), 'txn-baseline').data
    assert proof['receipt_verified'] and proof['commit_completed']
    archived = tuple(ModelDocument(o['path'], b64decode(o['bytes_base64']))
                     for o in plan.data['operations'][0]['objects'])
    target = TargetModel(model.configuration_bytes, model.binding,
        (*model.documents, ModelDocument(path, canonical_json_bytes(record))),
        profile=model.profile, resource_files=(*model.resource_files, *archived))
    manifest = target.manifest(target.artifacts, _default_scope())
    assert manifest.sha256 == plan.data['expected_result']['model_root_sha256']
    assert {r['path'] for r in manifest.data['archive_objects']} == {d.path for d in archived}
    for kind in ('update', 'retire', 'transition', 'attachment_add', 'relation_add'):
        value = operation(kind)
        value['source' if kind == 'relation_add' else 'target'] = record['id']
        with pytest.raises(ModelError): ChangeOperation(value)
    assert (root / path).read_bytes() == canonical_json_bytes(record)


def test_snapshot_preparation_and_preview_are_read_only(tmp_path):
    root = tmp_path / 'project'; model = project(root); before = inventory(root)
    with no_write_attempts():
        data = preview(model)
        prepared = build_project_baseline_manifest(model, baseline_id=ref('BASE'))
    assert data['target_validated'] and data['write_state'] == 'not_committed'
    assert not prepared.assurance['write_authorized'] and not prepared.assurance['atomic_snapshot']
    assert inventory(root) == before


def test_confirmed_saved_request_replays_without_another_baseline(tmp_path):
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model)
    first = apply(plan, model); before = inventory(root)
    with no_write_attempts():
        second = apply(plan, model, transaction_id='different-transaction')
    assert second['replayed'] and second['audit']['created_ids'] == first['audit']['created_ids']
    assert second['completion']['transaction_id'] == 'txn-baseline'
    assert inventory(root) == before


@pytest.mark.parametrize('kind', ['update', 'retire', 'transition', 'attachment_add', 'relation_add'])
def test_generic_writes_still_cannot_modify_the_new_baseline(tmp_path, kind):
    root = tmp_path / 'project'; model = project(root)
    record = plan_for(model).data['operations'][0]['record']
    before = inventory(root); value = operation(kind)
    value['source' if kind == 'relation_add' else 'target'] = record['id']
    with pytest.raises(ModelError): ChangeOperation(value)
    assert inventory(root) == before


def test_unrelated_invalid_artifact_blocks_preparation_and_publication(tmp_path):
    root = tmp_path / 'project'; model = project(root, broken=True); before = inventory(root)
    with pytest.raises(ModelError): preview(model)
    assert inventory(root) == before


def test_missing_existing_semantic_gate_cannot_be_replaced_by_baseline_approval(tmp_path):
    root = tmp_path / 'project'; model = project(root)
    value = approved_value('goal')
    document = ModelDocument(model.documents[0].path, canonical_json_bytes(value))
    model = TargetModel(model.configuration_bytes, model.binding, [document],
        profile=model.profile, resource_files=model.resource_files)
    put(root, document.path, document.content)
    before = inventory(root); data = preview(model)
    assert not data['target_validated']
    with pytest.raises(ModelError): apply(ChangePlan(canonical_json_bytes(data['plan'])), model)
    assert inventory(root) == before


@pytest.mark.parametrize('change', ['missing', 'different', 'extra'])
def test_changed_object_inventory_is_refused_before_publication(tmp_path, change):
    root = tmp_path / 'project'; model = project(root); original = plan_for(model)
    def modify(data):
        objects = data['operations'][0]['objects']
        if change == 'missing': objects.pop()
        else:
            raw = b'unrelated bytes'; digest = sha256(raw).hexdigest()
            entry = {'path': 'archive/objects/' + digest[:2] + '/' + digest,
                     'bytes_base64': b64encode(raw).decode()}
            if change == 'different': objects[0] = entry
            else: objects.append(entry)
            objects.sort(key=lambda r: r['path'])
    plan = changed_plan(original, modify); before = inventory(root)
    with pytest.raises(ModelError): apply(plan, model)
    assert inventory(root) == before


@pytest.mark.parametrize('change', ['source_bytes', 'new_normative_file', 'existing_object'])
def test_fresh_live_inventory_and_collision_checks_prevent_writes(tmp_path, change):
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model)
    if change == 'source_bytes':
        put(root, model.documents[0].path, model.documents[0].content + b' ')
    elif change == 'new_normative_file':
        put(root, 'rules/unobserved.json', b'{}')
    else:
        put(root, plan.data['operations'][0]['objects'][0]['path'], b'collision')
    before = inventory(root)
    with pytest.raises(ModelError): apply(plan, model)
    assert inventory(root) == before


def test_host_authority_denial_creates_no_baseline_or_object(tmp_path):
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model); before = inventory(root)
    denied = PublicationAuthority('denied', '1', lambda request: False)
    with pytest.raises(ModelError): apply(plan, model, authority=denied)
    assert inventory(root) == before


@pytest.mark.parametrize('actor,request_id', [('ai', 'baseline-1'), ('ci', None)])
def test_specialized_write_retains_actor_and_request_id_policy(tmp_path, actor, request_id):
    root = tmp_path / 'project'; model = project(root)
    value = preview(model, actor={'actor_type': actor, 'actor_id': 'caller'}, request_id=request_id)
    plan = ChangePlan(canonical_json_bytes(value['plan'])); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError): apply(plan, model)
    assert inventory(root) == before


def test_release_label_cannot_bypass_the_missing_readiness_provider(tmp_path):
    model = project(tmp_path / 'project'); value = plan_for(model).data['operations'][0]
    value['record']['baseline_kind'] = 'release'
    with pytest.raises(ModelError) as error: ChangeOperation(value)
    assert error.value.reason == 'release_baseline_readiness_required'


def test_existing_archive_cannot_be_relabelled_or_changed(tmp_path):
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model)
    record = plan.data['operations'][0]['record']
    document = ModelDocument(artifact_path('baseline', record['id'], 'SR'), canonical_json_bytes(record))
    objects = [ModelDocument(o['path'], b64decode(o['bytes_base64'])) for o in plan.data['operations'][0]['objects']]
    objects[0] = ModelDocument(objects[0].path, b'changed')
    with pytest.raises(ModelError):
        TargetModel(model.configuration_bytes, model.binding, (*model.documents, document),
            profile=model.profile, resource_files=(*model.resource_files, *objects))


def test_saved_baseline_plan_cannot_be_used_as_generic_artifact_create(tmp_path):
    from specroad.authoring.execution import apply_authoring_plan
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError):
        apply_authoring_plan(plan, model, command_id='artifact.create',
            transaction_id='txn-wrong', authority=ALLOW)
    assert inventory(root) == before


def test_objects_are_published_before_the_sealed_record(tmp_path):
    import specroad.changes.committing as committing
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model)
    record_path = artifact_path('baseline', ref('BASE'), 'SR'); observed = []
    original = committing.replace_bound_image
    def observe(*args, **kwargs):
        result = original(*args, **kwargs)
        if (root / record_path).exists():
            for row in plan.data['operations'][0]['record']['manifest']:
                assert sha256((root / row['object_path']).read_bytes()).hexdigest() == row['sha256']
        observed.append((root / record_path).exists())
        return result
    with patch.object(committing, 'replace_bound_image', side_effect=observe): apply(plan, model)
    assert observed[-1] and not any(observed[:-1])


@pytest.mark.parametrize('when', ['existing', 'at_boundary'])
def test_atomic_archive_publication_never_replaces_a_competing_file(tmp_path, when):
    from specroad.changes._publication_io import replace_bound_image
    source = tmp_path / 'source'; target = tmp_path / 'target'; source.mkdir(); target.mkdir()
    raw = b'owned snapshot'; (source / 'image').write_bytes(raw)
    foreign = target / 'object'
    if when == 'existing': foreign.write_bytes(b'foreign bytes')
    source_fd = os.open(source, os.O_RDONLY | os.O_DIRECTORY)
    target_fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY)
    info = (source / 'image').stat()
    try:
        with pytest.raises(FileExistsError):
            replace_bound_image(source_fd, 'image', target_fd, 'object', size=len(raw),
                digest=sha256(raw).hexdigest(), identity=(info.st_dev, info.st_ino), create_only=True,
                source_changed=lambda: AssertionError('unexpected source change'),
                before_replace=(lambda: foreign.write_bytes(b'foreign bytes')) if when == 'at_boundary' else None)
    finally:
        os.close(source_fd); os.close(target_fd)
    assert foreign.read_bytes() == b'foreign bytes' and (source / 'image').read_bytes() == raw


def test_interrupted_publication_never_reports_a_valid_partial_baseline(tmp_path):
    import specroad.changes.committing as committing
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model)
    original = committing.replace_bound_image
    def fail_before_record(*args, **kwargs):
        if args[3].startswith('SR-BASE-'): raise OSError('injected publication failure')
        return original(*args, **kwargs)
    with patch.object(committing, 'replace_bound_image', side_effect=fail_before_record):
        with pytest.raises(ModelError) as error: apply(plan, model)
    assert error.value.write_state == 'unknown'
    assert not (root / artifact_path('baseline', ref('BASE'), 'SR')).exists()
    assert (root / 'archive/objects').exists()
    journal = json.loads((root / '.specroad/transactions/txn-baseline/journal.json').read_bytes())
    assert journal['state'] == 'committing' and journal['published_count'] < len(journal['files'])
    with pytest.raises(ModelError): read_transaction_completion(ProjectSource(root), 'txn-baseline')


def test_prepared_baseline_supports_independent_discard_basis_reconstruction(tmp_path):
    from specroad.changes import prepare_discard_recovery
    import specroad.authoring.execution as execution
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model)
    with patch.object(execution, 'publish_prepared_journal', side_effect=OSError('stop after staging')):
        with pytest.raises(OSError): apply(plan, model)
    raw = (root / '.specroad/transactions/txn-baseline/journal.json').read_bytes()
    assert json.loads(raw)['state'] == 'prepared'
    before = inventory(root)
    prepared = prepare_discard_recovery(root, 'txn-baseline',
        expected_project_id=model.binding.project_id, expected_journal_sha256=sha256(raw).hexdigest())
    assert prepared.data['base_model_root_sha256'] == plan.data['base']['model_root_sha256']
    assert inventory(root) == before


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_native_baseline_works_in_isolated_core_and_portable_distribution(tmp_path, mode):
    from support.portable import build_distribution
    from support.processes import run_core, run_python
    root = tmp_path / 'project'; model = project(root)
    body = '''from pathlib import Path
from specroad.archive.creation import prepare_working_baseline, create_working_baseline
from specroad.changes import TargetModel, ChangePlan, PublicationAuthority
from specroad.model.canonical import canonical_json_bytes
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.language_registry import LanguageRegistry
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'root=Path(' + repr(str(root)) + ')\n'
    body += 'configuration=' + repr(model.configuration.data) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in model.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in model.resource_files]) + '\n'
    body += '''mapping=dict(resources); data=configuration['language_registry']
registry=LanguageRegistry(mapping[data['path']],expected_sha256=data['sha256'],expected_version=data['registry_version'])
profile=ProfileResource(mapping['profiles/core.json']); info=root.stat()
model=TargetModel(canonical_json_bytes(configuration),ProjectReadBinding(configuration['project_id'],str(root),(info.st_dev,info.st_ino)),
 [ModelDocument(p,b) for p,b in documents],profile=compose_profiles([profile],core_key=profile.key,language_registry=registry),
 resource_files=[ModelDocument(p,b) for p,b in resources])
'''
    body += 'preview=prepare_working_baseline(model,baseline_id=' + repr(ref('BASE')) + ',name="Portable",actor=' + repr(ACTOR) + ',planned_at=' + repr(TIME) + ',change_plan_id="CP-portable",request_id="portable-1")\n'
    body += '''assert preview['target_validated']
result=create_working_baseline(ChangePlan(canonical_json_bytes(preview['plan'])),model,
 transaction_id='txn-portable',authority=PublicationAuthority('owned-host','1',lambda request:True))
assert result['write_state']=='committed' and result['completion']['current_target_verified']
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
