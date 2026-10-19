"""Complete document data, durable native units and external byte delivery."""
from hashlib import sha256
import json
from pathlib import Path

import pytest

from specroad import _build
from specroad.documents import compose_document, resolve_table_block, resolve_artifact_reference
from specroad.documents.blocks import ContentBlock
from specroad.documents.includes import DocumentIncludeCycleError
from specroad.documents.prose import parse_prose
from specroad.documents.work import finalize_document_work
from specroad.documents.work_result import publish_document_result_files
from specroad.model.canonical import canonical_json_bytes
from specroad.work.checkpoints import CheckpointStorageError
from specroad.work.resume import WorkResumeError
from support.command_parity import build_core, process_environment, run_python
from support.document_work import registry, artifacts, setup, advance, PORTABLE
from support.read_only import inventory, no_write_attempts
from support.records import ref
from support.targets import model
from test_work_progress import ticking
from test_work_resume import recorded


def assert_native(result, supplied):
    composition = compose_document(supplied, ref('DOC')).data
    assert result['composition'] == composition
    selected = {i for i, r in composition['records'].items() if r['artifact_type'] == 'content_block'}
    assert {b['artifact_id'] for b in result['blocks']} == selected
    assert (ref('BLOCK', '7')[:-1] + '8') not in selected
    assert sum(o['artifact_id'] == ref('BLOCK', '4') for o in composition['occurrences']) == 2
    for item in result['blocks']:
        identifier = item['artifact_id']; bound = composition['records'][identifier]
        block = ContentBlock(supplied.source_files[bound['path']], path=bound['path'])
        observation = item['observation']
        assert observation['block'] == block.binding
        if block.block_kind in ('query', 'table'):
            assert observation == resolve_table_block(supplied, identifier).data
        elif block.block_kind == 'artifact_ref':
            assert observation == resolve_artifact_reference(supplied, identifier).data
        elif block.block_kind in ('prose', 'admonition'):
            assert observation == parse_prose(block).data
        else:
            assert observation['record'] == block.data
        assert observation['write_authorized'] is False and observation['approval_granted'] is False
    assert result['source_scope'] == 'explicit_saved_model' and result['project_files_verified'] is False


@pytest.mark.parametrize('size', [1, 2, 100])
@pytest.mark.parametrize('profile', ['constrained', 'standard'])
def test_document_data_equals_native_kernels_across_work_windows(recorded, tmp_path, size, profile):
    supplied, project, initial, store = setup(tmp_path); before = inventory(project); executed = []
    while store.read().entries('remaining'):
        step, _ = advance(store, size=size, profile=profile)
        assert step.executed_unit_ids and not set(step.executed_unit_ids).intersection(executed)
        assert list(step.reused_unit_ids) == executed
        executed.extend(step.executed_unit_ids)
    pending = store.read()
    assert pending.as_dict()['state'] == 'running'
    final = finalize_document_work(store, registry=registry()); outcome = json.loads(final.outcome_bytes)
    assert_native(outcome['result'], supplied)
    assert len(executed) == len(initial.entries('tasks')) == 10
    assert outcome['summary']['complete'] is True and final.command_exit_code == 0
    assert final.manifest.as_dict()['checkpoint_generation'] == pending.as_dict()['checkpoint_generation'] + 1
    assert inventory(project) == before


@pytest.mark.parametrize('branch', ['embedded', 'query_view', 'table_view'])
def test_query_semantics_and_explicit_page_are_preserved(recorded, tmp_path, branch):
    supplied, _, _, store = setup(tmp_path, values=artifacts(branch=branch, limit=1))
    advance(store, size=100)
    result = json.loads(finalize_document_work(store, registry=registry()).outcome_bytes)['result']
    assert_native(result, supplied)
    query = next(b['observation'] for b in result['blocks'] if b['artifact_id'] == ref('BLOCK', '3'))
    assert query['row_count'] == (1 if branch == 'embedded' else 2)
    assert query['query_result']['total'] == 2
    assert query['query_result']['truncated'] is (branch == 'embedded')


@pytest.mark.parametrize('cache', ['absent', 'empty', 'corrupt'])
def test_saved_sources_survive_loss_without_repeating_completed_native_units(recorded, tmp_path, monkeypatch, cache):
    supplied, project, _, store = setup(tmp_path)
    first, _ = advance(store, size=5)
    for path in supplied.source_files: (project / path).unlink()
    if cache != 'absent':
        directory = project / '.specroad/cache'; directory.mkdir(parents=True)
        if cache == 'corrupt': (directory / 'untrusted').write_bytes(b'broken')
    before = inventory(project)
    from specroad.documents import work
    native = work._evaluate; seen = []
    def observed(current, task, model, rows):
        assert task['unit_id'] not in first.executed_unit_ids
        seen.append(task['unit_id']); return native(current, task, model, rows)
    monkeypatch.setattr(work, '_evaluate', observed)
    while store.read().entries('remaining'): advance(store)
    final = finalize_document_work(store, registry=registry())
    assert_native(json.loads(final.outcome_bytes)['result'], supplied)
    assert len(seen) == 5 and inventory(project) == before
    def forbidden(*args, **kwargs): raise AssertionError('Completed native work was repeated')
    monkeypatch.setattr(work, '_evaluate', forbidden)
    after = inventory(tmp_path)
    assert advance(store, size=100)[0].executed_unit_ids == ()
    assert finalize_document_work(store, registry=registry()).outcome_bytes == final.outcome_bytes
    assert inventory(tmp_path) == after


@pytest.mark.parametrize('done', [0, 1, 9])
def test_unfinished_units_cannot_finalize_or_publish_result_files(recorded, tmp_path, done):
    _, _, _, store = setup(tmp_path)
    if done: advance(store, size=done)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError): finalize_document_work(store, registry=registry())
    with no_write_attempts(), pytest.raises(WorkResumeError): publish_document_result_files(store, registry=registry())
    assert inventory(tmp_path) == before and store.read().as_dict()['state'] == 'running'


@pytest.mark.parametrize('flag', ['--step-cpu-ms', '--step-wall-ms'])
def test_soft_window_makes_one_durable_unit_of_progress(recorded, tmp_path, flag):
    _, _, initial, store = setup(tmp_path)
    step, measurement = advance(store, size=100, sampler=ticking(), options={flag: 1})
    assert len(step.executed_unit_ids) == 1 and measurement['soft_budget_exceeded']
    assert len(step.manifest.entries('remaining')) == len(initial.entries('tasks')) - 1


@pytest.mark.parametrize('size', [True, 0, -1, '1'])
def test_invalid_window_cannot_change_work_or_project(recorded, tmp_path, size):
    _, _, _, store = setup(tmp_path); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError): advance(store, size=size)
    assert inventory(tmp_path) == before


def test_native_include_cycle_retains_checkpoint_and_diagnostic(recorded, tmp_path):
    values = artifacts(); values[4]['relations'][0]['target'] = ref('DOC')
    supplied, project, initial, store = setup(tmp_path, values=values); before = inventory(project)
    with pytest.raises(DocumentIncludeCycleError) as direct: compose_document(supplied, ref('DOC'))
    with pytest.raises(DocumentIncludeCycleError) as stepped: advance(store)
    assert stepped.value.diagnostic() == direct.value.diagnostic()
    assert store.read().raw == initial.raw and inventory(project) == before


def test_failed_native_table_does_not_publish_an_empty_or_false_complete_unit(recorded, tmp_path):
    from specroad.documents.tables import TableBlockError
    values = artifacts()
    next(v for v in values if v['id'] == ref('BLOCK', '4'))['payload']['rows'].append([])
    supplied, project, _, store = setup(tmp_path, values=values)
    advance(store, size=5); previous = store.read(); before = inventory(project)
    with pytest.raises(TableBlockError) as direct: resolve_table_block(supplied, ref('BLOCK', '4'))
    with pytest.raises(TableBlockError) as stepped: advance(store)
    assert stepped.value.diagnostic() == direct.value.diagnostic()
    assert store.read().raw == previous.raw and inventory(project) == before


def test_incompatible_build_cannot_reuse_or_modify_saved_document(recorded, tmp_path, monkeypatch):
    _, _, _, store = setup(tmp_path); advance(store)
    monkeypatch.setattr(_build, 'BUILD_METADATA', {**_build.BUILD_METADATA, 'build_sha256': 'c' * 64})
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught: advance(store)
    assert caught.value.exit_code == 6 and inventory(tmp_path) == before


def test_missing_saved_source_cannot_fall_back_to_live_project(recorded, tmp_path):
    _, _, initial, store = setup(tmp_path)
    item = initial.entries('inputs')[0]
    matches = list((tmp_path / 'work').rglob(item['sha256']))
    assert len(matches) == 1; matches[0].unlink(); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(CheckpointStorageError): advance(store)
    assert inventory(tmp_path) == before


def test_saved_resource_bytes_packages_and_reservations_bind_the_restored_model(recorded, tmp_path):
    from specroad.changes.target_model import TargetModel
    from specroad.documents.work import prepare_document_work
    from specroad.model.attachments import AttachmentDescriptor
    from specroad.model.language_packages import LanguagePackage
    from specroad.profiles import compose_profiles
    from specroad.security import ProjectBoundary
    from specroad.storage.language_registry import registry_binding
    from specroad.validation import ModelDocument
    from specroad.work.checkpoints import CheckpointStore
    from specroad.work.root import WorkDirectory
    from support.languages import load_registry
    from support.profiles import profile_data
    from test_language_packages import package_data
    base = model(artifacts(), profiles=[profile_data(profile_id='core'), profile_data(profile_id='extra')])
    language = load_registry(); declaration = registry_binding(language)
    configuration = {**base.configuration.data, 'language_registry': declaration}
    package = LanguagePackage(canonical_json_bytes(package_data()))
    profile = compose_profiles(base.profile_resources, core_key=base.profile.profile_chain[0],
        cli_profiles=base.profile.profile_chain[1:], language_registry=language, language_packages=[package])
    raw = b'\x00complete attachment\xff'
    attachment = AttachmentDescriptor('attachments/input.bin', 'application/octet-stream', len(raw), sha256(raw).hexdigest())
    supplied = TargetModel(canonical_json_bytes(configuration), base.binding, base.documents, profile=profile,
        resource_files=[*base.resource_files, ModelDocument(declaration['path'], language.source_bytes),
                        ModelDocument(attachment.path, raw)], attachments=[attachment], language_packages=[package],
        reserved_artifact_ids=[ref('REQ', '7')], reserved_relation_ids=['REL-' + '7' * 26],
        previously_approved_ids=[ref('REQ', '6')])
    project = tmp_path / 'project'; project.mkdir()
    initial = prepare_document_work(registry(), supplied, ref('DOC'))
    project_inputs = {i['path']: initial.objects[i['sha256']] for i in initial.entries('inputs') if i['root_id'] == 'project'}
    assert project_inputs == supplied.source_files
    assert [initial.objects[i['sha256']] for i in initial.entries('inputs') if i['root_id'] == 'packages'] == [package.source_bytes]
    assert b'/explicit/provider' not in initial.raw and all(b'/explicit/provider' not in b for b in initial.objects.values())
    store = CheckpointStore(WorkDirectory(initial, protected_roots=(ProjectBoundary(project),), directory=tmp_path / 'work'), initial)
    store.publish(initial); before = inventory(project); advance(store, size=100)
    assert_native(json.loads(finalize_document_work(store, registry=registry()).outcome_bytes)['result'], supplied)
    assert inventory(project) == before


def test_complete_external_files_have_all_rows_hashes_and_fresh_references(recorded, tmp_path):
    supplied, project, _, store = setup(tmp_path, values=artifacts(count=250))
    before = inventory(project); advance(store, size=100)
    final = finalize_document_work(store, registry=registry()); checkpoint = store.read().raw
    delivery = publish_document_result_files(store, registry=registry()); observation = delivery.as_dict()
    envelope = observation['command_outcome']; reference = envelope['result_ref']
    raw = Path(reference['path']).read_bytes(); result = json.loads(raw)
    assert raw == canonical_json_bytes(json.loads(final.outcome_bytes)['result'])
    assert reference['size'] == len(raw) and reference['sha256'] == sha256(raw).hexdigest()
    assert reference['result_schema'] == 'document-work-v1' and envelope['result'] is None
    assert_native(result, supplied)
    literal = next(b['observation'] for b in result['blocks'] if b['artifact_id'] == ref('BLOCK', '4'))
    assert literal['row_count'] == 250 and literal['rows'][-1]['cells'][0]['value'] == 249
    manifest_ref = observation['delivery_manifest']; manifest_raw = Path(manifest_ref['path']).read_bytes()
    assert len(manifest_raw) == manifest_ref['size'] and sha256(manifest_raw).hexdigest() == manifest_ref['sha256']
    manifest = json.loads(manifest_raw)
    assert manifest['files'][0]['sha256'] == reference['sha256'] and manifest['files'][0]['size'] == len(raw)
    assert store.read().raw == checkpoint and inventory(project) == before
    after = inventory(tmp_path)
    with no_write_attempts():
        assert publish_document_result_files(store, registry=registry()).as_dict() == observation
    assert inventory(tmp_path) == after
    Path(reference['path']).write_bytes(raw[:-1]); after = inventory(tmp_path)
    with no_write_attempts(), pytest.raises((WorkResumeError, CheckpointStorageError)): delivery.as_dict()
    assert inventory(tmp_path) == after


@pytest.mark.parametrize('kind', ['module', 'zipapp'])
def test_real_distribution_resumes_in_new_processes_after_source_and_root_relocation(tmp_path, kind):
    supplied = model(artifacts()); project = tmp_path / 'project'; project.mkdir()
    for path, raw in supplied.source_files.items():
        target = project / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
    packet = tmp_path / 'independent-binding.json'
    packet.write_text(json.dumps({'files': {p: b.hex() for p, b in supplied.source_files.items()},
        'documents': [d.path for d in supplied.documents], 'resources': [d.path for d in supplied.resource_files],
        'document_id': ref('DOC')}))
    output = tmp_path / 'distribution'
    built = build_core(Path(__file__).resolve().parents[1], output)
    assert built.returncode == 0, built.stderr
    distribution = output / ('module' if kind == 'module' else 'specroad.pyz')
    work = tmp_path / 'work'; cwd = tmp_path / 'unrelated'; cwd.mkdir(); environment = process_environment()
    def invoke(action, profile='constrained'):
        body = 'import sys;sys.path.insert(0,' + repr(str(distribution)) + ');' + PORTABLE
        child = run_python(body, [str(packet), str(work), str(project), action, profile], cwd=cwd, environment=environment)
        assert child.returncode == 0, child.stderr
        return json.loads(child.stdout)
    plan = invoke('plan'); assert plan['generation'] == 0 and plan['units'] == 10
    first = invoke('advance'); assert len(first['executed']) == 1
    moved = tmp_path / 'moved-distribution'; distribution.rename(moved); distribution = moved
    moved = tmp_path / 'moved-work'; work.rename(moved); work = moved
    moved = tmp_path / 'moved-project'; project.rename(moved); project = moved
    for path in supplied.source_files: (project / path).unlink()
    before = inventory(project); executed = list(first['executed'])
    for index in range(1, plan['units']):
        step = invoke('advance', 'standard' if index % 2 else 'constrained')
        assert step['generation'] == index + 1 and len(step['executed']) == 1
        assert not set(step['executed']).intersection(executed); executed += step['executed']
    result = invoke('finalize'); assert result == invoke('finalize')
    assert result['generation'] == plan['units'] + 1
    assert_native(result['outcome']['result'], supplied)
    delivered = invoke('publish'); reference = delivered['command_outcome']['result_ref']
    raw = Path(reference['path']).read_bytes()
    assert json.loads(raw) == result['outcome']['result'] and sha256(raw).hexdigest() == reference['sha256']
    assert len(raw) == reference['size'] and invoke('advance')['executed'] == []
    assert inventory(project) == before
