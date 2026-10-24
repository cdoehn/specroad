"""Actual Core/PYZ processes, relocated Work and no original source files."""
import json
from pathlib import Path

import pytest

from specroad.exchange import prepare_import_plan
from support.command_parity import build_core, process_environment, run_python
from support.exchange_oracles import assert_import_plan_equal
from support.folds import goal
from support.import_execution import project, inputs
from support.import_planning import imported
from support.import_work import transport
from support.read_only import inventory


# Explicit trusted test-host code. The checkpoint contains only inert data.
HOST = r'''
import json,sys
from hashlib import sha256
from pathlib import Path
from specroad.changes import TargetModel,TargetPolicy
from specroad.cli.contracts import CommandClass,CommandSpec,CommandProtocol,EffectScope,PreflightProfile
from specroad.cli.registry import CommandRegistry
from specroad.exchange.import_work import prepare_import_work,advance_import_work,finalize_import_work
from specroad.mappings import ExchangeMapping
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource,compose_profiles
from specroad.runtime.consumption import WorkConsumption
from specroad.security import ProjectBoundary
from specroad.validation import ModelDocument,ModelGate
from specroad.work.checkpoints import CheckpointStore
from specroad.work.manifest import read_work_manifest
from specroad.work.resume import _runtime_build
from specroad.work.root import WorkDirectory
def unused(invocation):raise AssertionError('No stored executable code')
registry=CommandRegistry((CommandSpec('import.plan',('import','plan'),CommandClass.READ_ONLY,
    PreflightProfile.BOOTSTRAP,EffectScope.NONE,unused,protocol=CommandProtocol('import-plan-work-v1',
    {'command_id':'import.plan'},handler_exit_codes=(0,3,5))),))
policy=TargetPolicy('ordinary-change','1',())
packet,work,project,action=sys.argv[1:];packet=Path(packet);data=json.loads(packet.read_text())
if action=='plan':
    files={p:bytes.fromhex(b) for p,b in data['files'].items()}
    profiles=[ProfileResource(files[p]) for p in data['resources'] if p.startswith('profiles/')]
    profile=compose_profiles(profiles,core_key=profiles[0].key)
    stat=Path(project).stat()
    model=TargetModel(files['specroad.json'],ProjectReadBinding('sample',project,(stat.st_dev,stat.st_ino)),
        [ModelDocument(p,files[p]) for p in data['documents']],profile=profile,
        resource_files=[ModelDocument(p,files[p]) for p in data['resources']],
        attachments=[AttachmentDescriptor.from_data(a) for a in data['attachments']])
    resource=ExchangeMapping(files['mappings/supplier.json'])
    initial=prepare_import_work(registry,model,data['candidates'],policy=policy,
        mapping_resources=[resource],input_bytes=bytes.fromhex(data['input_bytes']),**data['options'])
    packet.write_text(json.dumps({'initial':initial.raw.hex(),'objects':{k:v.hex() for k,v in initial.objects.items()}}))
else:
    initial=read_work_manifest(bytes.fromhex(data['initial']),{k:bytes.fromhex(v) for k,v in data['objects'].items()},
                              registry=registry,expected_tool_build=_runtime_build())
location=WorkDirectory(initial,protected_roots=(ProjectBoundary(project),),directory=work)
store=CheckpointStore(location,initial)
if action=='plan':
    store.publish(initial);print(json.dumps({'units':len(initial.entries('tasks')),'generation':0}))
elif action=='advance':
    item=next(i for i in initial.entries('inputs') if (i['root_id'],i['path'])==('import','mapping.json'))
    raw=initial.objects[item['sha256']]
    def check(context):ExchangeMapping(raw);return context.result()
    gate=ModelGate('extension:target-resources','synthetic-single-mapping-v1',
        lambda c:c.dependency_result({i:[] for i in c.subjects}),check,sha256(raw).hexdigest())
    call=WorkConsumption().begin({'--resource-profile':'constrained','--step-cpu-ms':1})
    try:step=advance_import_work(store,call,registry=registry,policy=policy,gates=[gate],max_units=1)
    finally:call.finish()
    print(json.dumps({'executed':list(step.executed_unit_ids),'generation':step.manifest.as_dict()['checkpoint_generation']}))
else:
    final=finalize_import_work(store,registry=registry)
    print(json.dumps({'outcome':json.loads(final.outcome_bytes),'generation':final.manifest.as_dict()['checkpoint_generation']}))
'''


@pytest.mark.parametrize('kind', ['module', 'zipapp'])
def test_recorded_distribution_resumes_saved_import_in_new_processes(tmp_path, kind):
    resource, _, raw, candidates = transport('ndjson')
    native, _ = project(tmp_path/'project', artifacts=[imported(), goal(9)], resource=resource)
    args = {**inputs(resource), 'input_format': 'ndjson', 'input_bytes': raw}
    expected = prepare_import_plan(native, candidates, **args)
    assert expected.plan_valid
    packet = tmp_path/'independent-binding.json'
    packet.write_text(json.dumps({'files': {p:b.hex() for p,b in native.source_files.items()},
        'documents': [d.path for d in native.documents], 'resources': [d.path for d in native.resource_files],
        'attachments': [a.data for a in native.attachment_descriptors], 'candidates': candidates,
        'input_bytes': raw.hex(), 'options': {k:v for k,v in args.items()
            if k not in ('input_bytes','mapping_resources','policy','gates')}}))
    distribution_dir = tmp_path/'distribution'
    built = build_core(Path(__file__).resolve().parents[1], distribution_dir)
    assert built.returncode == 0, built.stderr
    distribution = distribution_dir/('module' if kind == 'module' else 'specroad.pyz')
    work = tmp_path/'work'; root = tmp_path/'project'; cwd = tmp_path/'unrelated'; cwd.mkdir()
    def invoke(action):
        body = 'import sys;sys.path.insert(0,' + repr(str(distribution)) + ');' + HOST
        result = run_python(body,[str(packet),str(work),str(root),action],cwd=cwd,environment=process_environment())
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    planned = invoke('plan'); assert planned['units'] == 5
    first = invoke('advance'); executed = first['executed']; assert len(executed) == 1
    moved = tmp_path/'relocated-distribution'; distribution.rename(moved); distribution = moved
    moved = tmp_path/'relocated-work'; work.rename(moved); work = moved
    moved = tmp_path/'relocated-project'; root.rename(moved); root = moved
    for path in native.source_files: (root/path).unlink()
    before = inventory(root)
    for number in range(1,planned['units']):
        step = invoke('advance')
        assert len(step['executed']) == 1 and not set(step['executed']).intersection(executed)
        executed += step['executed']; assert step['generation'] == number+1
    final = invoke('finalize')
    assert_import_plan_equal(final['outcome']['result']['import_plan'], expected.canonical_bytes)
    assert final['generation'] == 6 and final == invoke('finalize')
    assert invoke('advance')['executed'] == [] and inventory(root) == before
