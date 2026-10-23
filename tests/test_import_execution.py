"""Real import publication and refusal through the ordinary transaction writer."""
from copy import deepcopy
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.authoring import execution as writer
from specroad.changes import PublicationAuthority, TargetPolicy, inspect_project_lock
from specroad.changes.receipt_values import TransactionReceipt, transaction_receipt_path, request_receipt_path
from specroad.exchange import ImportIdentityError, apply_import_plan, prepare_import_plan
from specroad.mappings import ExchangeMapping
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from support.folds import goal
from support.import_execution import ALLOW, apply, candidates, inputs, project
from support.import_planning import BASE, EXTERNAL, LOCAL, PAYLOAD, candidate, imported, mapping
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import record_value
from support.targets import ACTOR, TIME, SCOPE, gate


def assert_native_files(root, model, report):
    changed = {}
    for item in report['change_plan']['result_artifacts']:
        value = item['artifact']
        path = artifact_path(value['artifact_type'], value['id'], 'SR')
        actual = json.loads((root / path).read_bytes())
        assert actual == value and canonical_json_sha256(actual) == item['sha256']
        changed[path] = value
    for path, raw in model.source_files.items():
        if path not in changed:
            assert (root / path).read_bytes() == raw
    assert (root / 'foreign.bin').read_bytes() == b'Unmanaged bytes stay unchanged.\x00'


@pytest.mark.parametrize('saved', [False, True], ids=['fresh', 'saved'])
@pytest.mark.parametrize('input_format', ['csv', 'ndjson', 'reqif', 'reqifz'])
@pytest.mark.parametrize('strategy', ['update_if_unchanged', 'create_new_revision'])
def test_one_native_transaction_publishes_existing_and_new_artifacts(tmp_path, saved, input_format, strategy):
    resource = mapping(source_format='reqif' if input_format == 'reqifz' else input_format)
    root = tmp_path / 'project'; m, resource = project(root, resource=resource)
    values = candidates(); owned = deepcopy(values); seen = []
    def authorize(request):
        assert inspect_project_lock(root).data['record']['kind'] == 'writer'
        seen.append(request.plan.sha256)
        return True
    with patch('secrets.token_bytes', side_effect=AssertionError('explicit IDs only')):
        result = apply(m, values, resource, saved=saved,
            options={'input_format': input_format, 'strategy': strategy},
            authority=PublicationAuthority('owned-import-authorizer', '1', authorize))
    report, actual = result['submitted_import_plan'], result['execution']
    assert report['plan_valid'] and not report['import_completed'] and not report['write_authorized']
    assert result['submitted_import_plan_sha256'] == canonical_json_sha256(report)
    assert not result['input_parsed'] and not result['approval_granted']
    assert actual['command_id'] == 'import.apply' and actual['exit_code'] == 0
    assert actual['write_state'] == 'committed' and not actual['no_change'] and not actual['replayed']
    assert actual['target_model_root_sha256'] == report['target_model_root_sha256']
    assert actual['plan_sha256'] == report['change_plan']['change_plan_sha256']
    assert seen and set(seen) == {actual['plan_sha256']}
    assert actual['audit']['operations'] == report['operations']
    completion = actual['completion']
    assert completion['current_target_verified'] and completion['cleanup_completed']
    receipt = TransactionReceipt((root / completion['receipts']['transaction']['path']).read_bytes()).data
    assert receipt['journal']['plan_sha256'] == actual['plan_sha256']
    assert receipt['operations'] == report['operations']
    artifacts = {v['artifact']['id']: v['artifact'] for v in report['change_plan']['result_artifacts']}
    old = next(a for a in m.artifacts if a['external_identities'])
    assert artifacts[old['id']]['revision'] == old['revision'] + 1
    assert artifacts[values[1]['new_artifact']['id']]['revision'] == 1
    assert report['updated_ids'] == [old['id']]
    assert report['created_ids'] == [values[1]['new_artifact']['id']]
    for a in artifacts.values():
        assert a['statement'] == EXTERNAL
        assert a['external_identities'][0]['last_source_payload_sha256'] == sha256(PAYLOAD).hexdigest()
    assert_native_files(root, m, report)
    assert values == owned


@pytest.mark.parametrize('saved', [False, True], ids=['fresh', 'saved'])
def test_retry_replays_original_receipt_without_lock_write_or_new_target_claim(tmp_path, saved):
    root = tmp_path / 'project'; m, resource = project(root); values = candidates()
    original = apply(m, values, resource, saved=saved)
    before = inventory(root)
    with no_write_attempts(), patch.object(writer, 'project_lock', side_effect=AssertionError('no retry lock')):
        repeated = apply(m, values, resource, saved=saved, transaction_id='txn-retry')
    actual = repeated['execution']; first = original['execution']
    assert actual['replayed'] and actual['audit'] == {**first['audit'], 'replayed': True}
    assert actual['completion']['receipts'] == first['completion']['receipts']
    assert actual['plan_sha256'] == first['plan_sha256']
    assert not actual['completion']['current_target_verified']
    assert not repeated['submitted_import_plan']['import_completed'] and inventory(root) == before


def test_same_operations_with_new_plan_envelope_report_historical_audit_separately(tmp_path):
    root = tmp_path / 'project'; m, resource = project(root); values = candidates()
    first = apply(m, values, resource)['execution']; before = inventory(root)
    with no_write_attempts():
        result = apply(m, values, resource, options={'change_plan_id': 'CP-later-envelope'})
    actual = result['execution']; submitted = result['submitted_import_plan']
    assert actual['replayed'] and actual['audit']['change_plan_id'] == first['audit']['change_plan_id']
    assert submitted['change_plan_id'] == 'CP-later-envelope'
    assert actual['plan_sha256'] != submitted['change_plan']['change_plan_sha256']
    assert actual['completion']['receipts'] == first['completion']['receipts'] and inventory(root) == before


def test_reused_request_with_other_operations_preserves_the_original_receipt(tmp_path):
    root = tmp_path / 'project'; m, resource = project(root)
    first = apply(m, candidates(), resource); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        apply(m, [candidate('Different incoming value.')], resource)
    assert caught.value.exit_code == 6 and inventory(root) == before
    receipt = first['execution']['completion']['receipts']['transaction']['path']
    assert TransactionReceipt((root / receipt).read_bytes()).data['operations'] == first['execution']['audit']['operations']


@pytest.mark.parametrize('saved', [False, True], ids=['fresh', 'saved'])
def test_bound_attachment_and_source_reference_share_the_complete_native_target(tmp_path, saved):
    resource = mapping(); data = resource.data
    data['types'].append({'external_type': 'Source', 'artifact_type': 'source'})
    data['fields'].append({'external_type': 'Source', 'external_field': 'Locator', 'target_field': 'locator', 'value_map': None})
    resource = ExchangeMapping(canonical_json_bytes(data))
    root = tmp_path / 'project'; m, resource = project(root, resource=resource)
    descriptor = m.attachment_descriptors[0]
    source = record_value('source', created_at=TIME, updated_at=TIME, created_by=ACTOR,
        updated_by=ACTOR, content_sha256=descriptor.sha256)
    c = candidate(new=True, key='source-input'); c.update(external_type='Source',
        fields={'Locator': descriptor.path}, new_artifact=source)
    def check(context):
        actual = context.artifact(source['id'])
        assert actual['locator'] == descriptor.path
        assert actual['content_sha256'] == sha256(m.source_files[descriptor.path]).hexdigest()
        return context.result()
    result = apply(m, [candidate(), c], resource, saved=saved,
        options={'gates': [gate('external_resources', check=check)]})
    report, actual = result['submitted_import_plan'], result['execution']
    assert report['attachments'] == [{'kind': 'attachment', **descriptor.data}]
    assert actual['completion']['current_target_verified']
    assert actual['target_model_root_sha256'] == report['target_model_root_sha256']
    assert_native_files(root, m, report)
    assert (root / descriptor.path).read_bytes() == PAYLOAD
    assert source['id'] in actual['audit']['created_ids']


@pytest.mark.parametrize('saved', [False, True], ids=['fresh', 'saved'])
@pytest.mark.parametrize('case', ['empty', 'unchanged', 'skip', 'local-only'])
def test_noop_requires_authority_without_revision_journal_or_receipt(tmp_path, saved, case):
    root = tmp_path / 'project'
    m, resource = project(root, artifacts=[imported(local=LOCAL if case == 'local-only' else BASE)])
    values = [] if case == 'empty' else [candidate(BASE if case in ('unchanged', 'local-only') else EXTERNAL)]
    options = {'strategy': 'skip'} if case == 'skip' else {}
    before = inventory(root); seen = []
    result = apply(m, values, resource, saved=saved, options=options,
        authority=PublicationAuthority('noop-import-host', '1', lambda r: seen.append(r.plan.sha256) or True))
    actual = result['execution']; report = result['submitted_import_plan']
    assert seen and actual['no_change'] and actual['completion'] is None
    assert actual['write_state'] == 'not_committed' and not actual['replayed']
    assert report['operations'] == report['created_ids'] == report['updated_ids'] == []
    assert inventory(root) == before


@pytest.mark.parametrize('saved', [False, True], ids=['fresh', 'saved'])
@pytest.mark.parametrize('case', ['loss', 'diverged', 'error-strategy', 'missing-gate', 'invalid-target'])
def test_invalid_complete_plan_never_enters_writer(tmp_path, saved, case):
    root = tmp_path / 'project'
    m, resource = project(root, artifacts=[imported(local=LOCAL if case == 'diverged' else BASE)])
    values = [candidate()]; options = {}
    if case == 'loss': values[0]['fields']['Unsupported'] = {'unmapped': [None, True]}
    elif case == 'error-strategy': options['strategy'] = 'error'
    elif case == 'missing-gate': options['policy'] = TargetPolicy('import', '1', ('extension:required',))
    elif case == 'invalid-target':
        options['gates'] = [gate(check=lambda c: c.result([{'reason': 'invalid_complete_target', 'severity': 'error'}]))]
    before = inventory(root)
    with no_write_attempts(), patch.object(writer, 'project_lock', side_effect=AssertionError('no rejected-plan lock')):
        with pytest.raises(ImportIdentityError): apply(m, values, resource, saved=saved, options=options)
    assert inventory(root) == before


@pytest.mark.parametrize('field', ['input_bytes', 'mapping_resources', 'candidates', 'plan_valid', 'write_authorized'])
def test_saved_report_cannot_authorize_changed_inputs_or_forged_success(tmp_path, field):
    root = tmp_path / 'project'; m, resource = project(root); values = candidates(); args = inputs(resource)
    report = prepare_import_plan(m, values, **args); raw = report.canonical_bytes
    if field == 'input_bytes': args[field] += b'changed'
    elif field == 'mapping_resources': args[field] = [ExchangeMapping(json.dumps(resource.data, indent=2).encode())]
    elif field == 'candidates': values[0]['fields']['Text'] = 'Another value.'
    else:
        data = report.data; data[field] = not data[field]; raw = canonical_json_bytes(data)
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ImportIdentityError):
        apply_import_plan(m, values, **args, plan_bytes=raw, transaction_id='txn-forged', authority=ALLOW)
    assert inventory(root) == before


@pytest.mark.parametrize('path', ['specroad.json', 'profiles/core.json', 'mappings/supplier.json',
    'attachments/supplier.bin', 'untouched-artifact'])
def test_live_changed_bound_bytes_block_publication_without_erasing_external_change(tmp_path, path):
    root = tmp_path / 'project'; m, resource = project(root); values = candidates()
    report = prepare_import_plan(m, values, **inputs(resource))
    assert report.plan_valid
    raw = report.canonical_bytes
    if path == 'untouched-artifact':
        a = goal(2); path = artifact_path(a['artifact_type'], a['id'], 'SR')
    (root / path).write_bytes((root / path).read_bytes() + b' ')
    before = inventory(root)
    with pytest.raises(ModelError) as caught: apply(m, values, resource, plan_bytes=raw)
    assert caught.value.reason == ('publication_configuration_changed' if path == 'specroad.json' else 'publication_base_changed')
    assert inventory(root) == before


def test_publication_authority_denial_leaves_all_bytes_unchanged(tmp_path):
    root = tmp_path / 'project'; m, resource = project(root); before = inventory(root)
    with pytest.raises(ModelError) as caught:
        apply(m, candidates(), resource, authority=PublicationAuthority('denying-import-host', '1', lambda r: False))
    assert caught.value.exit_code == 7 and inventory(root) == before


@pytest.mark.parametrize('actor_type,request_id,code', [('ai', None, 2), ('ai', 'ai-request', 7), ('ci', None, 2)])
def test_import_cannot_bypass_actor_and_request_policy(tmp_path, actor_type, request_id, code):
    root = tmp_path / 'project'; m, resource = project(root); before = inventory(root)
    actor = {'actor_type': actor_type, 'actor_id': 'importer'}
    values = candidates()
    # A valid creation envelope must belong to the declared planning actor,
    # so this case reaches the writer's actor/request boundary.
    values[1]['new_artifact'].update(created_by=actor, updated_by=actor)
    options = {'actor': actor, 'request_id': request_id}
    assert prepare_import_plan(m, values, **(inputs(resource) | options)).plan_valid
    with pytest.raises(ModelError) as caught:
        apply(m, values, resource, options=options)
    assert caught.value.exit_code == code
    assert caught.value.reason == ('normative_request_id_required' if request_id is None else 'ai_requires_proposal')
    assert inventory(root) == before


def test_trusted_gate_is_rechecked_on_the_complete_target_before_publication(tmp_path):
    root = tmp_path / 'project'; m, resource = project(root); before = inventory(root); seen = []
    def check(context):
        seen.append(tuple(context.subjects))
        return context.result([] if len(seen) == 1 else [{'reason': 'authority_context_expired', 'severity': 'error'}])
    with pytest.raises(ModelError): apply(m, candidates(), resource, options={'gates': [gate(check=check)]})
    assert len(seen) >= 2 and all(goal(2)['id'] in ids for ids in seen)
    assert inventory(root) == before


def test_failure_after_staging_retains_native_recovery_and_never_fakes_completion(tmp_path):
    root = tmp_path / 'project'; m, resource = project(root)
    with patch.object(writer, 'publish_prepared_journal', side_effect=OSError('synthetic interruption')) as publish:
        with pytest.raises(OSError): apply(m, candidates(), resource)
    assert publish.call_count == 1
    for path, raw in m.source_files.items(): assert (root / path).read_bytes() == raw
    assert not (root / artifact_path('goal', goal(1)['id'], 'SR')).exists()
    journal = root / '.specroad/transactions/txn-import/journal.json'
    # Prepared payloads remain native recovery inputs; no automatic retry or rollback.
    assert json.loads(journal.read_bytes())['state'] == 'prepared'
    assert not (root / transaction_receipt_path('txn-import')).exists()
    assert not (root / request_receipt_path('import-execution-request')).exists()


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_isolated_runtime_imports_and_replays_real_native_transaction(tmp_path, mode):
    root = tmp_path / 'project'; m, resource = project(root); values = candidates()
    body = 'import json\nfrom pathlib import Path\nfrom specroad.exchange import apply_import_plan\n'
    body += 'from specroad.changes import TargetModel,TargetPolicy,PublicationAuthority\n'
    body += 'from specroad.profiles import ProfileResource,compose_profiles\nfrom specroad.validation import ModelDocument,ModelGate\n'
    body += 'from specroad.model.model_manifest import ProjectReadBinding\nfrom specroad.model.attachments import AttachmentDescriptor\n'
    body += 'from specroad.mappings import ExchangeMapping\n'
    body += 'root=Path(' + repr(str(root)) + ');st=root.stat()\n'
    body += 'p=ProfileResource(' + repr(m.profile_resources[0].source_bytes) + ')\n'
    artifact_paths = {artifact_path(a['artifact_type'], a['id'], 'SR') for a in m.artifacts}
    documents = [(p, b) for p, b in m.source_files.items() if p in artifact_paths]
    resources = [(p, b) for p, b in m.source_files.items() if p not in artifact_paths and p != 'specroad.json']
    body += 'm=TargetModel(' + repr(m.configuration_bytes) + ",ProjectReadBinding('sample',str(root),(st.st_dev,st.st_ino)),"
    body += '[ModelDocument(p,b) for p,b in ' + repr(documents) + '],profile=compose_profiles([p],core_key=p.key),'
    body += 'resource_files=[ModelDocument(p,b) for p,b in ' + repr(resources) + '],'
    body += 'attachments=[AttachmentDescriptor(' + repr('attachments/supplier.bin') + ", 'application/octet-stream'," + str(len(PAYLOAD)) + ',' + repr(sha256(PAYLOAD).hexdigest()) + ')])\n'
    body += 'resource=ExchangeMapping(' + repr(resource.source_bytes) + ')\n'
    body += 'def check_mapping(c):\n    ExchangeMapping(resource.source_bytes)\n    return c.result()\n'
    body += 'g=ModelGate("extension:target-resources","isolated-single-mapping-v1",lambda c:c.dependency_result({i:[] for i in c.subjects}),check_mapping,resource.source_sha256)\n'
    body += 'args=dict(input_format="reqif",input_bytes=' + repr(PAYLOAD) + ',mapping_resources=[resource],mapping_key=resource.key,mapping_sha256=resource.sha256,'
    body += 'strategy="update_if_unchanged",change_plan_id="CP-isolated",request_id="request-isolated",actor=' + repr(ACTOR)
    body += ',planned_at=' + repr(TIME) + ',scope_descriptor=' + repr(SCOPE) + ',metadata_policy_version="change-metadata-v1",policy=TargetPolicy("import","1",()),gates=[g],transaction_id="txn-isolated",authority=PublicationAuthority("isolated-test-host","1",lambda r:True))\n'
    body += 'first=apply_import_plan(m,' + repr(values) + ',**args)\n'
    body += 'again=apply_import_plan(m,' + repr(values) + ',**args)\n'
    body += 'print(json.dumps({"first":first,"again":again}))\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c', 'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    values = json.loads(result.stdout); first = values['first']['execution']; again = values['again']['execution']
    assert first['write_state'] == 'committed' and first['completion']['current_target_verified']
    assert again['replayed'] and again['completion']['receipts'] == first['completion']['receipts']
    assert not again['completion']['current_target_verified']
    assert_native_files(root, m, values['first']['submitted_import_plan'])


def test_mapping_resource_requires_explicit_trusted_resource_gate(tmp_path):
    root = tmp_path / 'project'; m, resource = project(root); args = inputs(resource)
    args['gates'] = []
    before = inventory(root)
    report = prepare_import_plan(m, candidates(), **args)
    assert report.data['target_assessment']['missing_command_gates'] == ['extension:target-resources']
    assert not report.plan_valid
    with no_write_attempts(), pytest.raises(ImportIdentityError):
        apply_import_plan(m, candidates(), **args, transaction_id='txn-without-resource-gate', authority=ALLOW)
    assert inventory(root) == before
