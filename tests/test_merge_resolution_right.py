"""17.h.R: audited plan integrity, currentness and native input boundaries."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from specroad.merge import (build_merge_conflicts, parse_merge_resolutions, parse_resolution_value,
    read_merge_resolutions, resolve_merge_conflict, SourceRequest, load_merge_sources)
from specroad.model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from specroad.model.errors import ModelError
from specroad.security import SafetyViolation
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.contracts import CommandClass, PreflightProfile, EffectScope, CommandSpec
from specroad.cli.parameters import OptionSpec
from specroad.cli.command_errors import CommandUsageError
from specroad.cli.results import thaw
from support.merge_resolution import ACTOR, WHEN, PLAN_ID, ROLES, case, request_files, argv
from support.merge_lifecycle import artifact, bound_records, changed
from support.merge_relations import history_for
from support.read_only import inventory
from support.languages import small_restore_registry
from support.model import put
from test_merge_sources import sources as source_fixtures, read_only_sources
from test_merge_conflicts_right import rehash
from test_merge_resolution import resolve
from test_project_bundle import project


@pytest.fixture(scope='module')
def original(tmp_path_factory):
    return project(tmp_path_factory.mktemp('resolution-right-seed')/'project',
                   language_registry=small_restore_registry()).raw


@pytest.fixture
def bound(tmp_path, original):
    return case(tmp_path/'sources',original)


def options(plan):
    return {'expected_plan_sha256': plan.sha256, 'conflict_id':plan.conflicts[0]['conflict_id'],
            'actor':ACTOR, 'resolved_at':WHEN, 'take':'ours'}


@pytest.fixture(scope='module')
def decision_inputs(tmp_path_factory, original):
    """Share only immutable native plan/request bytes for pre-source rejection.

    Filesystem/currentness cases continue to use the fresh per-test bound fixture.
    No source, history, mutable request or approval is shared with these cases.
    """
    native = case(tmp_path_factory.mktemp('decision-inputs'), original)
    plan = native[2]
    unresolved = plan.canonical_bytes, jcs(options(plan))
    resolved = resolve(native, take='ours')
    request = options(plan)
    request.update(expected_plan_sha256=resolved.sha256,
                   conflict_id=resolved.data['resolutions'][0]['conflict_id'])
    return unresolved, (resolved.canonical_bytes, jcs(request))


@pytest.mark.parametrize('change', ['unknown','duplicate','choice_missing','choice_both','take_invalid',
    'actor_missing','actor_type','actor_empty','actor_extra','time_missing','time_invalid','input_hash','bad_hash'])
def test_invalid_decision_is_rejected_before_source_access(decision_inputs, change):
    raw, encoded_request = decision_inputs[change == 'duplicate']
    request = json.loads(encoded_request)
    if change == 'unknown': request['conflict_id'] = 'MC-'+'f'*64
    elif change == 'choice_missing': del request['take']
    elif change == 'choice_both': request['value'] = 'both'
    elif change == 'take_invalid': request['take'] = 'force'
    elif change == 'actor_missing': request['actor'] = {}
    elif change == 'actor_type': request['actor'] = {'actor_type':'root','actor_id':'x'}
    elif change == 'actor_empty': request['actor'] = {'actor_type':'human','actor_id':'  '}
    elif change == 'actor_extra': request['actor'] = {**ACTOR,'authenticated':True}
    elif change == 'time_missing': request['resolved_at'] = None
    elif change == 'time_invalid': request['resolved_at'] = '2026-02-30T25:00:00Z'
    elif change == 'input_hash': request['expected_plan_sha256'] = 'a'*64
    elif change == 'bad_hash': request['expected_plan_sha256'] = 'a'*63+'\n'
    # None cannot be qualified; a local rejection must win without any source I/O.
    with pytest.raises(ModelError) as error:
        resolve_merge_conflict(raw,None,history=None,**request)
    assert error.value.reason != 'merge_sources_required'


@pytest.mark.parametrize('raw', [b'',b'undefined',b'NaN',b'Infinity',b'-Infinity',b'1e400',
    b'1.00000000000000001',b'{"x":1,"x":2}',b'"\\ud800"',b'\xff',b'0,"other":1',b'{} {}'])
def test_invalid_json_value_is_never_silently_repaired(raw):
    with pytest.raises(ModelError): parse_resolution_value(raw)


@pytest.mark.parametrize('kind',['nan','inf','foreign','tuple','bytes','cycle','unicode','numeric_key'])
def test_invalid_api_values_fail_the_same_canonical_domain(bound,kind):
    value = {'nan':float('nan'),'inf':float('inf'),'foreign':object(),'tuple':(1,),
             'bytes':b'1','unicode':'\ud800','numeric_key':{1:'x'},'cycle':[]}[kind]
    if kind == 'cycle': value.append(value)
    with pytest.raises(ModelError): resolve(bound,value=value)


@pytest.mark.parametrize('change', ['top_extra','event_extra','choice_extra','actor_extra','time',
    'event_hash','previous_hash','catalogue_hash','list_hash','value','target','rest','pending',
    'ready','write','approval','duplicate'])
def test_stored_resolution_rejects_inconsistent_audit_projection_or_authority(bound,change):
    result = resolve(bound,take='ours'); data = result.data
    event = data['resolutions'][0]
    if change == 'top_extra': data['extra'] = True
    elif change == 'event_extra': event['extra'] = True
    elif change == 'choice_extra': event['choice']['extra'] = True
    elif change == 'actor_extra': event['actor']['authenticated'] = True
    elif change == 'time': event['resolved_at'] = 'tomorrow'
    elif change == 'event_hash': event['resolution_id'] = 'MR-'+'f'*64
    elif change == 'previous_hash': event['previous_sha256'] = 'f'*64
    elif change == 'catalogue_hash': data['catalogue_sha256'] = 'f'*64
    elif change == 'list_hash': data['resolutions_sha256'] = 'f'*64
    elif change == 'value': event['value']['value'] = 'other'
    elif change == 'target': data['targets'][0]['pointer'] = '/different'
    elif change == 'rest': data['unresolved_conflict_ids'] = []
    elif change == 'pending': data['pending_gates'] = []
    elif change == 'ready': data['ready'] = True
    elif change == 'write': data['write_authorized'] = True
    elif change == 'approval': data['approval_granted'] = True
    else: data['resolutions'].append(deepcopy(event))
    with pytest.raises(ModelError): parse_merge_resolutions(jcs(data))


def test_reordered_valid_audit_events_are_not_a_valid_chain(bound):
    first = resolve(bound,take='ours')
    result = resolve(bound,plan=first,pointer='/extensions/vendor.resolve/item',take='theirs')
    data = result.data; data['resolutions'].reverse(); data['resolutions_sha256'] = digest(data['resolutions'])
    with pytest.raises(ModelError,match='merge_resolution_event_binding'):
        parse_merge_resolutions(jcs(data))


@pytest.mark.parametrize('change',['missing_conflict','value','impact','source','history'])
def test_rehashed_catalogue_forgeries_cannot_pass_native_source_gate(bound,change):
    sources,history,plan = bound; data = plan.data
    if change == 'missing_conflict': data['conflicts'] = data['conflicts'][:1]
    elif change == 'value': data['conflicts'][0]['values']['base']['value'] = 'forged'
    elif change == 'impact': data['conflicts'][0]['impact']['by_role']['base'] = []
    elif change == 'source': data['source_bindings']['ours']['model_root_sha256'] = 'f'*64
    else: data['history_input_sha256'] = 'f'*64
    if change == 'impact':
        # Synthetic goal may have no incident edge: add a claimed direct one.
        row = data['conflicts'][0]
        row['impact']['by_role']['base'] = [{'relation_id':'REL-forged','source_id':row['identity']['id'],
                                            'target_id':'foreign','relation_type':'refines'}]
    raw = rehash(data)
    request = options(plan); request['conflict_id'] = data['conflicts'][0]['conflict_id']
    request['expected_plan_sha256'] = digest(data)
    with pytest.raises(ModelError,match='merge_conflicts_binding_mismatch'):
        resolve_merge_conflict(raw,sources,history=history,**request)


@pytest.mark.parametrize('role',ROLES)
def test_changed_original_sources_prevent_new_decision_even_after_one_resolution(bound,role):
    sources,history,plan = bound
    first = resolve(bound,take='ours')
    source = getattr(sources,role); path = Path(source.source_root)/'specroad.json'
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises((ModelError,SafetyViolation)):
        resolve(bound,plan=first,pointer='/extensions/vendor.resolve/item',take='theirs')


@pytest.mark.parametrize('mode',['immutable','lifecycle','origin'])
def test_protection_conflicts_cannot_be_overridden_by_take_or_explicit_value(tmp_path,original,mode):
    path,value = artifact(original,'evidence' if mode == 'immutable' else 'goal')
    versions = [changed(value,maturity=s) for s in ('draft','proposed','rejected')] if mode == 'lifecycle' else [value,changed(value,title='changed'),value]
    sources,history = bound_records(tmp_path,original,path,versions)
    if mode == 'origin':
        next(row for row in history['observations'] if row['role']=='ours' and row['identity']['id']==value['id'])['origin']=None
    plan = build_merge_conflicts(sources,plan_id=PLAN_ID,history=history)
    for decision in ({'take':'ours'},{'value':None}):
        with pytest.raises(ModelError,match='merge_resolution_not_allowed'):
            resolve((sources,history,plan),pointer='',**decision)


@pytest.mark.parametrize('change',['input_hash','conflict','actor','time'])
def test_cli_invalid_local_decision_does_not_open_input_descriptor(bound,tmp_path,change):
    sources,history,plan = bound; request = request_files(tmp_path/'plans',sources,history,plan)
    Path(request['options']['--inputs']).unlink()
    if change == 'input_hash': request['options']['--expected-plan-sha256'] = 'f'*64
    elif change == 'conflict': request['options']['--conflict'] = 'MC-'+'f'*64
    elif change == 'actor': request['options']['--actor-id'] = '  '
    else: request['options']['--resolved-at'] = 'tomorrow'
    assert dispatch_result(argv(request)).exit_code == 3
    assert execute_request(request).result.exit_code == 3


@pytest.mark.parametrize('change',['missing','both','invalid_take','write_flag'])
def test_cli_choice_and_nonwrite_option_constraints(bound,tmp_path,change):
    sources,history,plan=bound; request=request_files(tmp_path/'plans',sources,history,plan)
    if change=='missing': del request['options']['--take']
    elif change=='both': request['options']['--value']='null'
    elif change=='invalid_take': request['options']['--take']='force'
    else: request['options']['--dry-run']=True
    before=inventory(tmp_path)
    assert dispatch_result(argv(request)).exit_code == 2
    assert execute_request(request).result.exit_code == 2
    assert inventory(tmp_path)==before


@pytest.mark.parametrize('input_name',['plan','descriptor'])
@pytest.mark.parametrize('kind',['leaf_link','parent_link','directory','missing','fifo'])
def test_cli_secure_regular_input_boundary(bound,tmp_path,input_name,kind):
    sources,history,plan=bound; request=request_files(tmp_path/'plans',sources,history,plan)
    location = request['arguments'] if input_name=='plan' else request['options']
    key = 'merge_plan' if input_name=='plan' else '--inputs'
    file = Path(location[key]); target = tmp_path/'bad'
    if kind=='leaf_link': target.symlink_to(file)
    elif kind=='parent_link':
        target.symlink_to(file.parent,target_is_directory=True);target=target/file.name
    elif kind=='directory': target.mkdir()
    elif kind=='fifo':
        if not hasattr(os,'mkfifo'): pytest.skip('No native FIFO on this platform')
        os.mkfifo(target)
    location[key]=str(target)
    before=inventory(tmp_path)
    assert dispatch_result(argv(request)).exit_code==(5 if kind=='missing' else 7)
    assert inventory(tmp_path)==before


@pytest.mark.parametrize('change',['extra','missing_role','kind','relative_root','reference','history','changed_source'])
def test_explicit_descriptor_cannot_replace_native_qualification(bound,tmp_path,change):
    sources,history,plan=bound; request=request_files(tmp_path/'plans',sources,history,plan)
    file=Path(request['options']['--inputs']);data=json.loads(file.read_bytes())
    if change=='extra':data['approve']=True
    elif change=='missing_role':del data['sources']['base']
    elif change=='kind':data['sources']['base']['kind']='remote_url'
    elif change=='relative_root':data['sources']['base']['root']='relative'
    elif change=='reference':data['sources']['base']['reference']='HEAD'
    elif change=='history':data['history']['source_bindings_sha256']='f'*64
    else:
        path=Path(sources.base.source_root)/'specroad.json';path.write_bytes(path.read_bytes()+b'\n')
    file.write_bytes(jcs(data));before=inventory(tmp_path)
    assert dispatch_result(argv(request)).exit_code==3
    assert inventory(tmp_path)==before


@pytest.mark.parametrize('kind',['local','git','baseline','bundle'])
def test_cli_accepts_explicit_native_source_kinds_without_checkout_or_project_write(tmp_path,kind):
    requests,files,_,git = source_fixtures(tmp_path)
    path=next(p for p in files if p.startswith('spec/goals/'))
    for role in ('ours','theirs'):
        root=tmp_path/role;root.mkdir()
        values=dict(files);value=json.loads(values[path]);value['title']=role;values[path]=jcs(value)
        for name,raw in values.items(): put(root,name,raw)
        requests[role]=SourceRequest(root)
    sources=load_merge_sources(requests[kind],requests['ours'],requests['theirs'])
    history=history_for(sources);plan=build_merge_conflicts(sources,plan_id=PLAN_ID,history=history)
    request=request_files(tmp_path/'plans',sources,history,plan)
    file=Path(request['options']['--inputs']);data=json.loads(file.read_bytes())
    native=requests[kind]
    data['sources']['base']={'kind':native.kind,'root':str(native.root),'reference':native.reference}
    file.write_bytes(jcs(data));before=inventory(tmp_path);git_before=git.capture()
    with read_only_sources():result=dispatch_result(argv(request))
    assert result.exit_code==0, result.as_dict()
    assert thaw(result.result)['plan']['catalogue']['source_bindings']['base']['kind']==kind
    assert inventory(tmp_path)==before and git.capture()==git_before


def test_audit_option_exception_is_exactly_scoped_to_the_resolution_plan_command():
    command=builtin_registry().resolve('merge.resolve')
    assert command.command_class is CommandClass.PLAN_OUTPUT
    assert command.preflight_profile is PreflightProfile.INPUT_READ
    assert command.effect_scope is EffectScope.EXTERNAL_OUTPUT
    assert not command.requires_project and not command.requires_write_paths
    assert command.protocol.lock_kind=='none'
    for identifier,words,profile in [('other',('other',),PreflightProfile.INPUT_READ),
        ('merge.resolve',('different',),PreflightProfile.INPUT_READ),
        ('merge.resolve',('merge','resolve'),PreflightProfile.BOOTSTRAP)]:
        with pytest.raises(CommandUsageError):
            CommandSpec(identifier,words,CommandClass.PLAN_OUTPUT,profile,EffectScope.EXTERNAL_OUTPUT,
                        handler=command.handler, options=(OptionSpec('--actor-id',takes_value=True),))


def test_native_reader_completion_does_not_hide_a_late_real_source_change(bound):
    from unittest.mock import patch
    from specroad.merge import resolutions as service
    sources, _, _ = bound
    native_read = service.read_merge_conflicts
    path = Path(sources.theirs.source_root) / 'specroad.json'
    def read_then_change(*args, **kwargs):
        result = native_read(*args, **kwargs)
        path.write_bytes(path.read_bytes() + b'\n')
        return result
    # Native qualification/reconstruction really run; only the timing of a real
    # disk change is injected. No source check or success outcome is fabricated.
    with patch.object(service, 'read_merge_conflicts', side_effect=read_then_change):
        with pytest.raises((ModelError, SafetyViolation)):
            resolve(bound, take='ours')


@pytest.mark.parametrize('input_name', ['plan','descriptor'])
def test_cli_rechecks_actual_input_bytes_before_returning(bound, tmp_path, input_name):
    from unittest.mock import patch
    from specroad.security import ProjectBoundary
    sources, history, plan = bound
    request = request_files(tmp_path/'plans',sources,history,plan)
    file = Path(request['arguments']['merge_plan'] if input_name=='plan' else request['options']['--inputs'])
    descriptor = Path(request['options']['--inputs'])
    native_read = ProjectBoundary.read_bytes
    changed_once = False
    def read_then_change(boundary, name, *args, **kwargs):
        nonlocal changed_once
        raw = native_read(boundary, name, *args, **kwargs)
        if not changed_once and boundary.root == descriptor.parent and name == descriptor.name:
            changed_once = True
            file.write_bytes(file.read_bytes()+b'\n')
        return raw
    with patch.object(ProjectBoundary, 'read_bytes', read_then_change):
        result = dispatch_result(argv(request))
    assert changed_once and result.exit_code == 7


@pytest.mark.parametrize('raw', [b'', b'not a zip', b'PK\x03\x04truncated'])
def test_cli_malformed_native_bundle_is_a_model_error_not_an_internal_failure(bound,tmp_path,raw):
    sources,history,plan=bound
    request=request_files(tmp_path/'plans',sources,history,plan)
    source=tmp_path/'source.zip';source.write_bytes(raw)
    descriptor=Path(request['options']['--inputs']);data=json.loads(descriptor.read_bytes())
    data['sources']['base']={'kind':'bundle','root':str(source),'reference':None}
    descriptor.write_bytes(jcs(data));before=inventory(tmp_path)
    assert dispatch_result(argv(request)).exit_code==3
    assert inventory(tmp_path)==before
