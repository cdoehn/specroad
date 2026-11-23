"""Independent regression boundaries from the failed native authoring gate."""
from base64 import b64decode
from hashlib import sha256
import json

import pytest

from specroad.authoring.native_generic import author_generic
from specroad.authoring.project_sources import AuthoringSources
from specroad.cli.application import execute_request
from specroad.documents.structure import assess_document_structure
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.qualification.formats import declared_resource
from specroad.qualification.project import validate_project
from support.model import put
from support.native_authoring_cases import specialist_example, store
from support.native_plan_authoring import ACTOR, ENTRY, PLAN, files, setup, values
from test_document_structure import contains, section


def test_document_contains_and_native_plan_tree_coexist_without_crossing(tmp_path):
    root = setup(tmp_path / 'project')
    document = next(v for v in values(root).values() if v['artifact_type'] == 'document')
    child = section()
    document['relations'] = [contains(child['id'], '5', 4)]
    store(root, document)
    store(root, child)
    before = files(root)
    model = AuthoringSources(root).model
    report = assess_document_structure(model)
    assert report.structure_valid, report.data['diagnostics']
    result = report.require_document(document['id'])
    assert result['root_section_ids'] == [child['id']]
    assert [row['artifact_id'] for row in result['preorder']] == [child['id']]
    assert set(report.data['children']) == {document['id'], child['id']}
    assert {PLAN, ENTRY} <= {row['artifact_id'] for row in report.data['source_bindings']}
    checked, _ = validate_project(model.source_files)
    assert checked.source_files == model.source_files and files(root) == before


def test_plan_tree_never_hides_invalid_document_containment(tmp_path):
    root = setup(tmp_path / 'project')
    document = next(v for v in values(root).values() if v['artifact_type'] == 'document')
    document['relations'] = [contains(ENTRY, '5')]
    store(root, document)
    before = files(root)
    report = assess_document_structure(AuthoringSources(root).model)
    assert not report.structure_valid and report.data['diagnostics']
    assert report.data['documents'] is None and files(root) == before


@pytest.mark.parametrize('name', ['view.create', 'change.apply'])
def test_relative_authoring_input_uses_invocation_cwd_not_process_cwd(tmp_path, monkeypatch, name):
    root = tmp_path / 'project'
    fields = specialist_example(root, 'view.create')
    if name == 'view.create':
        raw = jcs(fields)
        arguments, options = {}, {'--input': 'input.json'}
    else:
        preview = author_generic(root, {'command_id': 'view.create', **fields},
                                 actor=ACTOR, dry_run=True)
        raw = jcs(preview['plan'])
        arguments, options = {'plan_file': 'input.json'}, {}
    put(root, 'input.json', raw)
    foreign = tmp_path / 'other'
    put(foreign, 'input.json', b'not the explicitly selected input')
    monkeypatch.chdir(foreign)
    before = files(root)
    response = execute_request({'command_id': name, 'arguments': arguments,
        'options': {**options, '--actor-type': 'human', '--actor-id': ACTOR['actor_id'],
                    '--dry-run': True}}, cwd=root).result
    assert response.exit_code == 0, response.diagnostics
    assert response.result['outcome']['dry_run']
    assert files(root) == before and files(foreign) == {'input.json': b'not the explicitly selected input'}


def test_baseline_preserves_project_schema_and_requires_exact_archive_bytes(tmp_path):
    root = setup(tmp_path / 'project', with_plan=False)
    source = AuthoringSources(root).model
    before = files(root)
    preview = author_generic(root, {'command_id': 'baseline.create', 'name': 'Working snapshot'},
                             actor=ACTOR, dry_run=True)
    operation, = preview['plan']['operations']
    record = operation['record']
    objects = {row['path']: b64decode(row['bytes_base64'], validate=True) for row in operation['objects']}
    config_row, = [row for row in record['manifest'] if row['role'] == 'semantic_configuration']
    config_raw = objects[config_row['object_path']]
    assert json.loads(config_raw)['schema_version'] == '0.3.0'
    assert sha256(config_raw).hexdigest() == config_row['sha256']
    target = {**source.source_files, **objects,
              artifact_path('baseline', record['id'], 'SR'): jcs(record)}
    checked, _ = validate_project(target)
    assert checked.source_files == target
    with pytest.raises(ModelError):
        validate_project({**target, config_row['object_path']: config_raw + b' '})
    assert files(root) == before


def test_archived_project_version_does_not_admit_future_artifact_or_project_versions(tmp_path):
    root = setup(tmp_path / 'project', with_plan=False)
    config = json.loads((root / 'specroad.json').read_bytes())
    for value in ({**config, 'schema_version': '0.4.0'},
                  {**config, 'artifact_type': 'goal'}):
        raw = jcs(value)
        digest = sha256(raw).hexdigest()
        with pytest.raises(ModelError) as caught:
            declared_resource(raw, 'archive/objects/' + digest[:2] + '/' + digest)
        assert caught.value.reason == 'restore_unsupported_source_schema_version'


@pytest.mark.parametrize('actor_type', ['human', 'ai'])
@pytest.mark.parametrize('dry_run', [False, True], ids=['publish', 'preview'])
def test_baseline_proposal_refusal_precedes_identity_and_writer(tmp_path, monkeypatch, actor_type, dry_run):
    from specroad.authoring import native_generic
    from specroad.proposals.errors import ProposalError
    from support.native_plan_authoring import ALLOW, proposal_input
    root = setup(tmp_path / 'project', with_plan=False)
    before = files(root)
    def forbidden(*args, **kwargs):
        raise AssertionError('Rejected Proposal must not allocate identities or enter the writer')
    monkeypatch.setattr(native_generic, 'uuid4', forbidden)
    monkeypatch.setattr(native_generic, 'project_lock', forbidden)
    with pytest.raises(ProposalError) as caught:
        native_generic.author_generic(root,
            {'command_id': 'baseline.create', 'name': 'Explicit snapshot'},
            actor={'actor_type': actor_type, 'actor_id': 'synthetic-author'},
            request_id='baseline-proposal-refusal', dry_run=dry_run,
            as_proposal=True, proposal_fields=proposal_input(), authority=ALLOW)
    assert caught.value.exit_code == 3 and caught.value.reason == 'proposal_control_target_forbidden'
    attempt = caught.value.authoring_attempt
    assert attempt['write_state'] == 'not_committed'
    assert attempt['planned_created_ids'] is None and attempt['expected_model_root_sha256'] is None
    assert attempt['recovery_required'] is False and attempt['approval_granted'] is False
    assert files(root) == before


def test_raw_authoring_still_refuses_unnamespaced_extension_without_writes(tmp_path):
    from specroad.cli.commands import builtin_registry
    root = setup(tmp_path / 'project')
    identity = next(v['id'] for v in values(root).values() if v['artifact_type'] == 'goal')
    before = files(root)
    registry = builtin_registry()
    invocation = registry.parse(['artifact', 'update', identity, '--set', '/extensions/b=2',
        '--expected-revision', '1', '--dry-run', '--actor-type', 'human', '--actor-id', 'synthetic'])
    response = registry.execute_result(invocation, cwd=root)
    assert response.exit_code == 3, response.as_dict()
    assert files(root) == before
