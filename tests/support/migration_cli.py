"""Synthetic public migration inputs; no stored plan or fake writer outcome."""
import json
from pathlib import Path
from specroad.cli.application import execute, execute_request
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.cli.results import thaw
from specroad.changes.publication_values import PublicationAuthority
from specroad.changes.recovery_values import RecoveryAuthority
from .migration_plans import vector_source
from .migration_transaction import execution_inputs
from .reference01 import encoded

REQUIREMENT = 'spec/requirements/SR-REQ-0001.json'


def case(tmp_path, *, files=None):
    source = vector_source() if files is None else dict(files)
    root = tmp_path/'project'; root.mkdir()
    inputs = tmp_path/'inputs'; inputs.mkdir()
    outputs = tmp_path/'outputs'; outputs.mkdir()
    backup = tmp_path/'backup'; backup.mkdir()
    for path, raw in source.items():
        name=root/path; name.parent.mkdir(parents=True,exist_ok=True);name.write_bytes(raw)
    (inputs/'mapping.json').write_bytes(encoded(execution_inputs(source)))
    options = {'--project':str(root),'--to':'0.2.0','--inputs-root':str(inputs),'--inputs':'mapping.json',
        '--actor-type':'tool','--actor-id':'synthetic-cli-host','--planned-at':'2026-11-04T00:00:00Z',
        '--plan-id':'CP-cli-migration','--request-id':'synthetic:cli-migration',
        '--output-root':str(outputs),'--output':'migration.json'}
    return root, source, options, outputs, backup


def argv(command, options):
    return command.split('.') + [item for key,value in options.items()
        for item in ([key] if value is True else [key,str(value)])]


def invoke(command, options, representation='argv', *, authorize=True, gates=(), authority=None, arguments=None):
    host = authority if authority is not None else PublicationAuthority('synthetic-cli-host','1',lambda request:True) if authorize else None
    builder=InvocationContextBuilder(publication_authority=host,migration_gates=gates,
        recovery_authority=RecoveryAuthority('synthetic-cli-recovery','1',lambda request:True) if authorize else None)
    words=argv(command,options) + list((arguments or {}).values())
    response=(execute(words,context_builder=builder) if representation=='argv'
        else execute_request({'command_id':command,'options':options,'arguments':arguments or {}},context_builder=builder))
    return response.result


def success(result):
    assert result.exit_code==0, (result.command, result.diagnostics, result.details)
    return thaw(result.result)


def planned(data, representation='argv'):
    root, source, options, outputs, backup = data
    result=success(invoke('migrate.plan',options,representation))
    report=result['planning']
    apply={'--project':str(root),'--to':'0.2.0','--plan-root':str(outputs),'--plan':'migration.json',
        '--expected-plan-sha256':report['change_plan']['change_plan_sha256'],
        '--expected-inputs-sha256':report['inputs_sha256'],
        '--expected-report-sha256':result['plan_file']['sha256'],
        '--backup-root':str(backup),'--backup':'source.zip','--transaction-id':'synthetic-cli-transition'}
    return result, apply


def verified(apply_options, outcome, representation='argv', *, gates=()):
    options={**apply_options,'--expected-backup-sha256':outcome['backup']['file']['sha256']}
    return success(invoke('migrate.verify',options,representation,gates=gates))


def restore(root, output, *, representation='argv'):
    bundled=success(invoke('bundle.create',{'--project':str(root),'--scope':'project','--output-root':str(output),'--output':'current.zip'},representation))
    raw=(root/REQUIREMENT).read_bytes();(root/REQUIREMENT).write_bytes(b'broken synthetic mutable artifact')
    planning={'--project':str(root),'--source-root':str(output),'--from':'current.zip',
        '--source-kind':'project_bundle','--dry-run':True,'--output-root':str(output),'--output':'restore.json'}
    result=success(invoke('recover.restore',planning,representation))
    options={'--project':str(root),'--plan-root':str(output),'--plan':'restore.json',
        '--expected-target-root':result['restore_plan']['expected_target_root'],
        '--actor-type':'tool','--actor-id':'synthetic-cli-restorer','--request-id':'synthetic:restore'}
    restored=success(invoke('recover.restore',options,representation))
    assert restored['execution']['result']=='restored'
    assert (root/REQUIREMENT).read_bytes()==raw
    return bundled, restored
