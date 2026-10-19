"""Native document/query inputs and a trusted fresh-process host for Work."""
import json

from specroad.cli.contracts import (CommandClass, CommandSpec, CommandProtocol,
                                  EffectScope, PreflightProfile)
from specroad.cli.registry import CommandRegistry
from specroad.documents.work import prepare_document_work, advance_document_work
from specroad.model.model_manifest import ProjectReadBinding
from specroad.runtime.consumption import WorkConsumption
from specroad.security import ProjectBoundary
from specroad.work.checkpoints import CheckpointStore
from specroad.work.root import WorkDirectory
from support.read_only import inventory, no_write_attempts
from support.records import block_value, record_value, ref
from support.targets import model
from test_document_includes import include_project, edge
from test_document_tables import table_project
from test_work_progress import unknown


def registry():
    def unused(invocation):
        raise AssertionError('Saved Work never invokes a registry handler')
    return CommandRegistry((CommandSpec('document.project', ('document', 'project'),
        CommandClass.READ_ONLY, PreflightProfile.BOOTSTRAP, EffectScope.NONE, unused,
        protocol=CommandProtocol('document-work-v1', {'command_id': 'document.project'},
                                 handler_exit_codes=(0,))),))


def artifacts(*, count=30, branch='embedded', limit=10):
    values = include_project(); query, *targets = table_project(branch, limit=limit)
    query['id'] = ref('BLOCK', '3')
    if query['relations']:
        query['relations'][0]['relation_id'] = edge('references', ref('VIEW'), 20)['relation_id']
    literal = block_value('table'); literal['id'] = ref('BLOCK', '4')
    literal['payload'] = {'columns': [{'field': 'ordinal'}, {'field': 'payload'}],
        'rows': [[n, {'label': 'Grüße', 'empty': None, 'present': False}] for n in range(count)]}
    reference = block_value('artifact_ref'); reference['id'] = ref('BLOCK', '5')
    reference['relations'] = [edge('references', targets[0]['id'], 21)]
    admonition = block_value('admonition'); admonition['id'] = ref('BLOCK', '6')
    page = block_value('page_break'); page['id'] = ref('BLOCK', '7')
    for position, block in enumerate((query, literal, reference, admonition, page), 1):
        values[3]['relations'].append(edge('contains', block['id'], 21 + position, position))
    unselected = block_value('prose'); unselected['id'] = (ref('BLOCK', '7')[:-1] + '8')
    values += [record_value('document', id=ref('DOC', '2'), document_role='supporting',
        relations=[edge('contains', ref('SEC', '2'), 30)]),
        record_value('section', id=ref('SEC', '2'), relations=[edge('contains', unselected['id'], 31)])]
    return [*values, query, literal, reference, admonition, page, unselected, *targets]


def setup(tmp_path, *, values=None):
    project = tmp_path / 'project'; project.mkdir(parents=True)
    observed = project.stat()
    supplied = model(artifacts() if values is None else values,
        binding=ProjectReadBinding('sample', str(project), (observed.st_dev, observed.st_ino)))
    for path, raw in supplied.source_files.items():
        target = project / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
    before = inventory(tmp_path)
    with no_write_attempts():
        initial = prepare_document_work(registry(), supplied, ref('DOC'))
    assert inventory(tmp_path) == before
    location = WorkDirectory(initial, protected_roots=(ProjectBoundary(project),), directory=tmp_path / 'work')
    store = CheckpointStore(location, initial); store.publish(initial)
    return supplied, project, initial, store


def advance(store, *, size=1, profile='constrained', sampler=unknown, options=None):
    call = WorkConsumption(sampler=sampler).begin({'--resource-profile': profile, **(options or {})})
    try:
        result = advance_document_work(store, call, registry=registry(), max_units=size)
    finally:
        measurement = call.finish()
    return result, measurement


PORTABLE = r'''
import json, sys
from pathlib import Path
from specroad.cli.contracts import CommandClass, CommandSpec, CommandProtocol, EffectScope, PreflightProfile
from specroad.cli.registry import CommandRegistry
from specroad.changes.target_model import TargetModel
from specroad.documents.work import prepare_document_work, advance_document_work, finalize_document_work
from specroad.documents.work_result import publish_document_result_files
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.runtime.consumption import WorkConsumption
from specroad.security import ProjectBoundary
from specroad.validation import ModelDocument
from specroad.work.checkpoints import CheckpointStore
from specroad.work.manifest import read_work_manifest
from specroad.work.root import WorkDirectory
from specroad.work.resume import _runtime_build
packet, work, project, action, profile = sys.argv[1:]
def forbidden(invocation): raise AssertionError('Stored Work cannot invoke handlers')
registry = CommandRegistry((CommandSpec('document.project', ('document','project'),
    CommandClass.READ_ONLY, PreflightProfile.BOOTSTRAP, EffectScope.NONE, forbidden,
    protocol=CommandProtocol('document-work-v1', {'command_id':'document.project'}, handler_exit_codes=(0,))),))
project = Path(project); packet = Path(packet)
if action == 'plan':
    data = json.loads(packet.read_bytes()); files = {p: bytes.fromhex(b) for p,b in data['files'].items()}
    resources = [ModelDocument(p, files[p]) for p in data['resources']]
    profiles = [ProfileResource(d.content) for d in resources]
    observation = project.stat()
    model = TargetModel(files['specroad.json'], ProjectReadBinding('sample', str(project),
        (observation.st_dev,observation.st_ino)), [ModelDocument(p,files[p]) for p in data['documents']],
        profile=compose_profiles(profiles,core_key='core@0.2.0'), resource_files=resources)
    initial = prepare_document_work(registry,model,data['document_id'])
    packet.write_text(json.dumps({'initial':initial.raw.hex(),'objects':{h:b.hex() for h,b in initial.objects.items()}}))
else:
    data = json.loads(packet.read_bytes())
    initial = read_work_manifest(bytes.fromhex(data['initial']), {h:bytes.fromhex(b) for h,b in data['objects'].items()},
                                registry=registry,expected_tool_build=_runtime_build())
store = CheckpointStore(WorkDirectory(initial, protected_roots=(ProjectBoundary(project),), directory=Path(work)), initial)
if action == 'plan':
    store.publish(initial)
    print(json.dumps({'generation':0,'units':len(initial.entries('tasks'))}))
elif action == 'advance':
    call = WorkConsumption().begin({'--resource-profile':profile})
    try: step = advance_document_work(store,call,registry=registry)
    finally: call.finish()
    print(json.dumps({'generation':step.manifest.as_dict()['checkpoint_generation'],'executed':list(step.executed_unit_ids)}))
elif action == 'finalize':
    step = finalize_document_work(store,registry=registry)
    print(json.dumps({'generation':step.manifest.as_dict()['checkpoint_generation'],'outcome':json.loads(step.outcome_bytes)}))
else:
    print(json.dumps(publish_document_result_files(store,registry=registry).as_dict()))
'''
