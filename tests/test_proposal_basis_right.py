"""Fixed selection, stored-data errors and the real shared CLI invocation seam."""
from copy import deepcopy

import pytest

from specroad.changes.core import prepare_change_plan
from specroad.cli.application import execute, execute_request
from specroad.cli.proposal_basis import proposal_basis_failure
from specroad.cli.registry import (CommandClass, CommandRegistry, CommandSpec,
    EffectScope, OptionSpec, PreflightProfile)
from specroad.cli.requests import CommandRequest
from specroad.cli.results import CommandResult
from specroad.graph.scope_admission import ScopeControlDependencyError
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from specroad.proposals import (Proposal, ProposalOriginal, ProposalError,
    build_proposal_basis, prepare_proposal_for_model)
from specroad.proposals.values import SPECIFICATION_SCOPE, content_sha256
from support.domain import relation
from support.read_only import no_write_attempts
from support.records import record_value, ref
from test_proposal_basis import project, fields, put_model


BAD_SCOPES = [
    {**SPECIFICATION_SCOPE, 'scope_kind': 'project'},
    {**SPECIFICATION_SCOPE, 'scope_kind': 'explicit', 'selector': {'artifact_ids': [], 'resource_ids': []}},
    {**SPECIFICATION_SCOPE, 'scope_kind': 'document', 'selector': {'document_id': ref('DOC')}},
    {**SPECIFICATION_SCOPE, 'scope_kind': 'release', 'selector': {'release_id': ref('REL')}},
    {**SPECIFICATION_SCOPE, 'boundary_policy': 'partial'},
    {**SPECIFICATION_SCOPE, 'configuration_id': ref('CFG')},
    {**SPECIFICATION_SCOPE, 'scope_kind': 'configuration', 'configuration_id': ref('CFG'),
        'selector': {'base_scope_descriptor': deepcopy(SPECIFICATION_SCOPE)}},
]


@pytest.mark.parametrize('descriptor', BAD_SCOPES)
def test_public_basis_rejects_every_disallowed_selection_before_model_use(descriptor):
    with no_write_attempts(), pytest.raises(ProposalError) as error:
        build_proposal_basis(None, scope_descriptor=descriptor)
    assert error.value.exit_code == 3
    assert error.value.reason == 'proposal_specification_scope_required'


@pytest.mark.parametrize('configuration', [ref('CFG'), '', False, {}, 0])
def test_configuration_is_not_silently_removed(configuration):
    with no_write_attempts(), pytest.raises(ProposalError) as error:
        build_proposal_basis(None, configuration_id=configuration)
    assert error.value.reason == 'proposal_configuration_forbidden'


def test_explicit_fixed_scope_is_equivalent_and_input_is_not_mutated(tmp_path):
    model = project(tmp_path / 'project'); descriptor = deepcopy(SPECIFICATION_SCOPE)
    with no_write_attempts():
        implicit = build_proposal_basis(model)
        explicit = build_proposal_basis(model, scope_descriptor=descriptor)
    assert implicit.manifest.canonical_bytes == explicit.manifest.canonical_bytes
    assert descriptor == SPECIFICATION_SCOPE


def test_mutable_compatibility_scope_cannot_change_the_fixed_contract(tmp_path, monkeypatch):
    model = project(tmp_path / 'project'); expected = build_proposal_basis(model).data
    monkeypatch.setitem(SPECIFICATION_SCOPE, 'scope_kind', 'project')
    with no_write_attempts():
        actual = build_proposal_basis(model)
        proposal = prepare_proposal_for_model(model, **fields(model))
    assert actual.data == expected == proposal.data['base']


@pytest.mark.parametrize('descriptor', BAD_SCOPES)
@pytest.mark.parametrize('reader', [ProposalOriginal, Proposal])
def test_saved_invalid_basis_is_model_error_without_rebinding(tmp_path, descriptor, reader):
    model = project(tmp_path / 'project'); supplied = fields(model)
    value = prepare_proposal_for_model(model, **supplied).data
    plan = value['change_plan']; plan.pop('change_plan_sha256')
    plan['base']['scope_descriptor'] = deepcopy(descriptor)
    value['change_plan'] = prepare_change_plan(plan).data
    value['base'] = deepcopy(value['change_plan']['base'])
    value['content_sha256'] = content_sha256(value)
    raw = jcs(value)
    with no_write_attempts(), pytest.raises(ProposalError) as error:
        reader(raw, path=supplied['identity'].path)
    assert error.value.exit_code == 3
    assert error.value.reason == 'proposal_specification_scope_required'


def controlled_model(root, kind):
    model = project(root)
    if kind == 'proposal':
        control = prepare_proposal_for_model(model, **fields(model)).data
        return put_model(model, control), control
    from specroad.changes.baselines import prepare_baseline_operation, object_documents
    from specroad.changes._target_materialization import materialize_target
    from specroad.model.paths import artifact_path
    from specroad.validation import ModelDocument
    operation = prepare_baseline_operation(model, baseline_id=ref('BASE'), name='Synthetic',
        actor={'actor_type': 'human', 'actor_id': 'synthetic-author'}, planned_at='2026-01-01T00:00:00Z')
    record = operation['record']
    return materialize_target(model, (*object_documents(operation),
        ModelDocument(artifact_path('baseline', record['id'], 'SR'), jcs(record)))), record


@pytest.mark.parametrize('kind', ['proposal', 'baseline'])
@pytest.mark.parametrize('route', ['references', 'conflicts_with', 'duplicates', 'indirect', 'subject'])
def test_every_control_dependency_retains_native_diagnostic(tmp_path, kind, route):
    model, control = controlled_model(tmp_path / 'project', kind)
    if route == 'subject':
        value = record_value('evidence')
        value['subjects'][0]['artifact_id'] = control['id']
        pointer = '/subjects/0/artifact_id'; relation_id = None
    else:
        edge = relation('references' if route == 'indirect' else route, control['id'])
        value = record_value('content_block', relations=[edge])
        pointer = '/relations/0/target'; relation_id = edge['relation_id']
    target = put_model(model, value)
    if route == 'duplicates':
        # Duplicates must join artifacts of the same type. This invalid edge
        # fails native endpoint validation before specification closure.
        with no_write_attempts(), pytest.raises(ModelError) as error:
            build_proposal_basis(target)
        assert error.value.reason == 'relation_type_pair_forbidden'
        assert error.value.pointer == pointer
        response = proposal_basis_failure('proposal.create', error.value)
        assert response.exit_code == 3
        assert response.details['model_failure']['reason'] == 'relation_type_pair_forbidden'
        assert response.details['model_failure']['pointer'] == pointer
        assert response.details['write_authorized'] is False
        return
    if route == 'indirect':
        edge = relation('contains', value['id']); edge['relation_id'] = 'REL-' + '1' * 26
        edge['position'] = 0
        section = record_value('section', relations=[edge])
        edge = relation('contains', section['id']); edge['relation_id'] = 'REL-' + '2' * 26
        edge['position'] = 0
        doc = record_value('document', relations=[edge])
        target = put_model(target, section, doc)
    with no_write_attempts(), pytest.raises(ScopeControlDependencyError) as error:
        build_proposal_basis(target)
    diagnostic = error.value.diagnostic()
    assert diagnostic['code'] == 'SRV140'
    assert diagnostic['reason'] == 'scope_control_dependency' and diagnostic['exit_code'] == 3
    assert diagnostic['source_id'] == value['id'] and diagnostic['target_id'] == control['id']
    assert diagnostic['relation_id'] == relation_id and diagnostic['pointer'] == pointer
    response = proposal_basis_failure('proposal.create', error.value)
    assert response.exit_code == 3
    assert response.diagnostics[0].code == 'SRV140'
    assert response.details['model_failure']['target_id'] == control['id']


def test_free_text_and_passive_extensions_are_not_control_dependencies(tmp_path):
    model, control = controlled_model(tmp_path / 'project', 'proposal')
    value = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    value['statement'] = 'Mention ' + control['id']
    value['extensions'] = {'synthetic.note': {'target': control['id']}}
    with no_write_attempts():
        result = build_proposal_basis(put_model(model, value))
    assert control['id'] not in {r['id'] for r in result.manifest.data['artifacts']}


@pytest.mark.parametrize('kind', ['proposal', 'baseline'])
def test_native_planned_target_cannot_introduce_a_control_dependency(tmp_path, kind):
    from specroad.changes.lifecycle import prepare_change_lifecycle
    from support.change_plans import document, result
    from support.folds import add_relation
    model, control = controlled_model(tmp_path / 'project', kind)
    block = record_value('content_block')
    model = put_model(model, block)
    supplied = fields(model)
    plan = document([add_relation(block, control, kind='references')], [])
    plan['base'] = build_proposal_basis(model).data
    folded = prepare_change_lifecycle(model.artifacts, plan['operations'],
        metadata_policy_version=plan['metadata_policy_version'], actor=plan['actor'],
        planned_at=plan['planned_at'], source_files=model.source_files, **model.reservations)
    final = next(a for a in folded.artifacts if a['id'] == block['id'])
    plan['result_artifacts'] = [result(final)]
    # A plausible declaration cannot replace closure of the actual target.
    plan['expected_result']['model_root_sha256'] = 'f' * 64
    supplied['change_plan'] = prepare_change_plan(plan)
    supplied['changes'] = [{'change_id': 'CHG-' + '0' * 26, 'targets': [block['id']],
        'rationale': 'Synthetic invalid dependency', 'requirement_or_issue_ids': [],
        'sources': [], 'assumptions': [], 'confidence': None}]
    with no_write_attempts(), pytest.raises(ScopeControlDependencyError) as error:
        prepare_proposal_for_model(model, **supplied)
    assert error.value.source_id == block['id'] and error.value.target_id == control['id']
    assert error.value.code == 'SRV140' and error.value.exit_code == 3


def registry(model, calls):
    """Embed the real basis API at the standard CLI seam, without a fake writer.

    Built-in authoring commands are installed by later M18 steps. This fixture
    exercises only their shared parsing/preflight/basis boundary and grants no
    publication capability.
    """
    def handler(invocation):
        calls.append(invocation.command.command_id)
        try:
            basis = build_proposal_basis(model)
            return CommandResult(invocation.command.command_id, result=basis.data)
        except ModelError as error:
            return proposal_basis_failure(invocation.command.command_id, error)
    return CommandRegistry((CommandSpec(command_id='proposal.create', words=('proposal', 'create'),
        command_class=CommandClass.NORMATIVE_WRITE, preflight_profile=PreflightProfile.PROJECT_WRITE,
        effect_scope=EffectScope.NORMATIVE_TRANSACTION, requires_project=True, handler=handler,
        options=(OptionSpec('--base-scope', takes_value=True), OptionSpec('--configuration', takes_value=True),
            OptionSpec('--project', takes_value=True), OptionSpec('--dry-run'))),))


@pytest.mark.parametrize('descriptor', BAD_SCOPES)
@pytest.mark.parametrize('structured', [False, True])
def test_cli_selection_is_usage_error_before_project_or_handler(tmp_path, descriptor, structured):
    path = tmp_path / 'scope.json'; path.write_bytes(jcs(descriptor))
    calls = []; commands = registry(None, calls)
    options = {'--base-scope': 'scope.json', '--project': str(tmp_path / 'absent')}
    with no_write_attempts():
        response = (execute_request(CommandRequest('proposal.create', options), registry=commands, cwd=tmp_path)
            if structured else execute(['proposal', 'create', '--base-scope', 'scope.json',
                '--project', str(tmp_path / 'absent')], registry=commands, cwd=tmp_path))
    assert response.result.exit_code == 2
    assert calls == [] and not (tmp_path / 'absent').exists()


@pytest.mark.parametrize('raw', [b'{', b'[]', b'{"scope_kind":"unknown"}',
    b'{"scope_version":"scope-v1","scope_version":"scope-v1"}'])
def test_cli_malformed_scope_is_data_error_not_usage_or_success(tmp_path, raw):
    (tmp_path / 'scope.json').write_bytes(raw); calls = []
    with no_write_attempts():
        result = execute(['proposal', 'create', '--base-scope', 'scope.json'],
            registry=registry(None, calls), cwd=tmp_path).result
    assert result.exit_code == 3 and calls == []


@pytest.mark.parametrize('options,code', [({'--configuration': ref('CFG')}, 2),
    ({'--base-scope': '-'}, 2), ({'--base-scope': 'missing.json'}, 5)])
def test_cli_configuration_stdin_and_missing_file_have_distinct_failures(tmp_path, options, code):
    calls = []
    with no_write_attempts():
        result = execute_request(CommandRequest('proposal.create', options),
            registry=registry(None, calls), cwd=tmp_path).result
    assert result.exit_code == code and calls == []


def test_cli_scope_symlink_is_security_error_before_project_access(tmp_path):
    original = tmp_path / 'original.json'; original.write_bytes(jcs(SPECIFICATION_SCOPE))
    (tmp_path / 'link.json').symlink_to(original)
    calls = []
    with no_write_attempts():
        result = execute(['proposal', 'create', '--base-scope', 'link.json'],
            registry=registry(None, calls), cwd=tmp_path).result
    assert result.exit_code == 7 and calls == []


def test_cli_changed_scope_input_is_conflict_before_handler(tmp_path, monkeypatch):
    from specroad.security import ProjectBoundary
    original = tmp_path / 'scope.json'; original.write_bytes(jcs(SPECIFICATION_SCOPE))
    read = ProjectBoundary.read_bytes
    reads = []
    def changed_read(boundary, path):
        raw = read(boundary, path)
        reads.append(path)
        return raw if len(reads) == 1 else raw + b'\n'
    monkeypatch.setattr(ProjectBoundary, 'read_bytes', changed_read)
    calls = []
    with no_write_attempts():
        result = execute(['proposal', 'create', '--base-scope', 'scope.json'],
            registry=registry(None, calls), cwd=tmp_path).result
    assert result.exit_code == 6 and calls == [] and len(reads) == 2


@pytest.mark.parametrize('explicit', [False, True])
def test_cli_fixed_selection_reaches_native_basis_without_write(tmp_path, explicit):
    model = project(tmp_path / 'project'); calls = []
    path = tmp_path / 'scope.json'; path.write_bytes(jcs(SPECIFICATION_SCOPE))
    args = ['proposal', 'create', '--project', model.binding.source_root, '--dry-run']
    if explicit:
        args += ['--base-scope', 'scope.json']
    with no_write_attempts():
        result = execute(args, registry=registry(model, calls), cwd=tmp_path).result
    assert result.exit_code == 0 and calls == ['proposal.create']
    assert result.result['model_root_sha256'] == build_proposal_basis(model).data['model_root_sha256']


def test_cli_reports_native_control_dependency_with_code_and_context(tmp_path):
    model, control = controlled_model(tmp_path / 'project', 'proposal')
    model = put_model(model, record_value('content_block', relations=[relation('references', control['id'])]))
    with no_write_attempts():
        result = execute(['proposal', 'create', '--project', model.binding.source_root, '--dry-run'],
            registry=registry(model, []), cwd=tmp_path).result
    assert result.exit_code == 3
    assert result.diagnostics[0].code == 'SRV140'
    assert result.details['model_failure']['target_id'] == control['id']
