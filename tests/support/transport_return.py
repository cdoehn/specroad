"""Small complete native returns. Host setup and offline execution stay separate."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.proposals.authoring import Proposal
from support.transport_outbound import register, request, run_request
from support.transport_opening import opening_request, offline
from test_proposal_basis import project, planned_change, fields


def origin(root, distribution, *, subproject=False):
    repository = root / 'repository'; repository.mkdir()
    model = repository / 'model' if subproject else repository
    project(model, bundled=True)
    registered = register(root, repository)
    value = request(root, model, distribution[1])
    response = run_request(root, value, source=distribution[0])
    assert response['code'] == 0, response
    return {'source': root / 'output/handoff.zip', 'runtime': Path(value['options']['--patchharbor-pyz']),
            'origin': model, 'repository': repository, 'registered': registered}


def sandbox(root, distribution, handoff, *, empty=False):
    value = opening_request(root, handoff, extract=True)
    result = offline(root, distribution[1], value)
    assert result['code'] == 0, result
    model = InspectionSnapshot(root / 'sandbox/project', None).model
    supplied = root / 'proposal.json'
    parameters = fields(model) if empty else planned_change(model)
    identity = parameters.pop('identity')
    plan = parameters.pop('change_plan')
    # Fixture inputs describe intent; the actual native construction, validation
    # and semantic check take place inside the same Python-only sandbox.
    program = """
from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.changes import ChangePlan
from specroad.model.identity_values import ArtifactIdentity
from specroad.proposals import prepare_proposal_for_model, ProposalContext
from specroad.proposals.validation import validate_proposal
from specroad.proposals.check import check_proposal_project
root=Path(""" + repr(str(root/'sandbox/project')) + """)
parameters=""" + repr(parameters) + """
parameters['identity']=ArtifactIdentity(""" + repr(identity.id) + ", 'random128-v1', 'proposal', 'SR')\n" + """
parameters['change_plan']=ChangePlan(""" + repr(plan.source_bytes) + """)
model=InspectionSnapshot(root,None).model
proposal=prepare_proposal_for_model(model,**parameters)
validate_proposal(ProposalContext(proposal.original,model))
target=Path(""" + repr(str(supplied)) + """)
target.write_bytes(proposal.source_bytes)
checked=check_proposal_project(root,str(target))
assert checked.exit_code==0,checked.as_dict()
print(json.dumps({'proposal':proposal.data,'path':proposal.original.path}))
"""
    prepared = offline_program(root, distribution[1], program)
    proposal = Proposal(supplied.read_bytes(), path=prepared['path'])
    output = root / 'output'; output.mkdir()
    return {'command_id': 'bundle.create', 'options': {
        '--project': str(root / 'sandbox/project'), '--profile': ['ai-runtime'], '--direction': 'return',
        '--reference': str(root / 'sandbox/reference/outbound.zip'),
        '--expected-sha256': sha256(handoff['source'].read_bytes()).hexdigest(), '--proposal': str(supplied),
        '--patchharbor-pyz': str(root / 'sandbox/runtime/patchharbor-1.8.0.pyz'),
        '--patchharbor-pyz-sha256': sha256(handoff['runtime'].read_bytes()).hexdigest(),
        '--output-root': str(output), '--output': 'return.zip', '--format': 'json'}}, proposal


def offline_program(root, distribution, program):
    environment = {k: os.environ[k] for k in ('LD_LIBRARY_PATH', 'SystemRoot', 'WINDIR') if k in os.environ}
    environment.update(PATH=str(root / 'no-executables'), HOME=str(root / 'home'), LANG='C.UTF-8', LC_ALL='C.UTF-8')
    body = """import sys,json
from pathlib import Path
def audit(event,args):
    if event in ('subprocess.Popen','os.system','os.posix_spawn','socket.__new__','socket.connect'):
        raise AssertionError('Return attempted external execution: '+event)
sys.addaudithook(audit)
sys.path.insert(0, """ + repr(str(distribution)) + ');\n' + program
    process = subprocess.run([sys.executable,'-I','-S','-B','-c',body], cwd=root, env=environment,
        stdin=subprocess.DEVNULL,capture_output=True)
    assert process.returncode == 0, process.stderr.decode(errors='replace')
    return json.loads(process.stdout)


def offline_export(root, distribution, request, *, before='', after='', argv=False):
    arguments = ['bundle', 'create']
    for flag, value in request['options'].items():
        for item in value if isinstance(value, list) else [value]:
            arguments.extend([flag, str(item)])
    call = 'dispatch_result(' + repr(arguments) + ')' if argv else 'execute_request(' + repr(request) + ').result'
    body = before + """
from specroad.cli.application import execute_request,dispatch_result
result = """ + call + """
value={'code':result.exit_code,'outcome':result.as_dict()}
""" + after + '\nprint(json.dumps(value))'
    return offline_program(root, distribution, body)
