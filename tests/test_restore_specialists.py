"""Complete native specialist inputs; synthetic reviews grant no real approval."""
from hashlib import sha256

import pytest

from specroad.bundles import prepare_project_bundle
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.changes.target_model import _default_scope
from specroad.model.canonical import canonical_json_bytes
from specroad.planning import TaskDoneContext, HumanTaskDoneReview, prepare_task_implementation
from specroad.recovery import RestoreServices, RestoreError, prepare_restore_plan, execute_restore
from specroad.security import ProjectBoundary
from support.domain import domain_value
from support.model import put
from support.records import record_value
from support.restore import restore_case
from support.read_only import inventory, no_write_attempts
from test_task_implementation import review_data, verifier
from test_restore_invocation import authority


@pytest.mark.parametrize('fault', [None, 'missing', 'stale', 'incomplete'])
def test_implemented_task_requires_real_complete_current_done_inputs(tmp_path, fault):
    task = domain_value('task', implementation_status='implemented',
        done_criteria=['Reject invalid input.', 'Preserve the original file.'])
    options, _, _ = restore_case(tmp_path, values=[record_value('document'), task])
    calls = []
    def done(model):
        calls.append(model._sources_sha256)
        ctx = TaskDoneContext(model, task['id'], scope_descriptor=ScopeDescriptor(_default_scope()))
        data = review_data(ctx)
        if fault == 'incomplete':
            data['criteria'][-1] = False
        return (prepare_task_implementation(ctx, review=HumanTaskDoneReview(data),
                                           verifier=verifier(current=fault != 'stale')),)
    services = RestoreServices(task_done=None if fault == 'missing' else done)
    before = inventory(tmp_path)
    if fault is not None:
        with no_write_attempts(), pytest.raises(RestoreError):
            prepare_restore_plan(**options, services=services)
        assert inventory(tmp_path) == before
        return
    plan = prepare_restore_plan(**options, services=services)
    count = len(calls)
    result = execute_restore(plan.source_bytes, expected_target_root=plan.data['expected_target_root'],
        authority=authority(), actor={'actor_type': 'human', 'actor_id': 'synthetic-owner'}, services=services)
    assert result.data['result'] == 'restored' and len(calls) > count


@pytest.mark.parametrize('fault', [None, 'missing', 'changed'])
def test_code_reference_is_checked_against_actual_host_bytes_without_executing_code(tmp_path, fault):
    raw = b'raise RuntimeError("This source must never run")\n'
    reference = record_value('code_ref', reference_kind='file', path='source.py',
                             file_sha256=sha256(raw).hexdigest())
    options, _, _ = restore_case(tmp_path, values=[record_value('document'), reference])
    code = tmp_path / 'external-code'; code.mkdir()
    if fault != 'missing':
        put(code, 'source.py', b'changed' if fault == 'changed' else raw)
    service = RestoreServices(code_source=lambda model, record: ProjectBoundary(code))
    before = inventory(tmp_path)
    with no_write_attempts():
        if fault is None:
            plan = prepare_restore_plan(**options, services=service)
            assert plan.data['expected_target_root']
        else:
            with pytest.raises(RestoreError, match='code_reference_not_current'):
                prepare_restore_plan(**options, services=service)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('fault', [None, 'mapping', 'registry', 'profile'])
def test_mapping_registry_and_csv_profile_need_their_full_native_contracts(tmp_path, fault):
    from support.csv_codec import resources
    from support.exchange_mappings import registry
    profile, mapping = resources()
    external = registry(mapping)
    options, files, _ = restore_case(tmp_path)
    for name, resource in (('mapping', mapping), ('registry', external), ('profile', profile)):
        value = resource.data
        if fault == name:
            # Identity, version and JSON shape alone do not qualify a resource.
            if name == 'mapping':
                value['fields'][0]['target_field'] = ''
            else:
                value['mapping']['sha256'] = '0' * 64
        raw = canonical_json_bytes(value)
        files['mappings/' + name + '.json'] = raw
        for root in (options['source_root'], options['project_root']):
            put(root, 'mappings/' + name + '.json', raw)
    if fault is None:
        put(options['source_root'], options['source_path'], prepare_project_bundle(options['source_root']).source_bytes)
    before = inventory(tmp_path)
    with no_write_attempts():
        if fault is None:
            assert prepare_restore_plan(**options).data['expected_target_root']
        else:
            from specroad.recovery._validation import validate_project
            from specroad.model.errors import ModelError
            with pytest.raises(ModelError):
                validate_project(files)
    assert inventory(tmp_path) == before
