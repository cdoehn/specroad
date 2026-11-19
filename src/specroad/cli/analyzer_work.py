"""Analyzer Work routing and explicit output publication through native guards."""
from contextlib import nullcontext
from pathlib import Path

from ..analyzers._values import require, encoded
from ..analyzers.files import publish
from ..work.analyzer import (prepare_analyzer_work, protected_paths, checked,
    resume_analyzer_work, outcome)
from ..work.root import WorkDirectory
from ..work.checkpoints import CheckpointStore, CheckpointStorageError
from ..work._data_contract import WorkManifestError
from ..work.resume import WorkResumeError, _runtime_build
from .results import CommandResult, FailureKind, OperationFailure


def _store(initial, options, cwd):
    requested = options.get('--work-dir')
    if requested is not None:
        from ..analyzers.files import canonical_path
        requested = str(canonical_path(requested, cwd))
    location = WorkDirectory(initial, protected_roots=(), protected_paths=protected_paths(initial), directory=requested)
    return CheckpointStore(location, initial)


def _pause(call, edge='end'):
    from ..runtime.control_points import PhaseBoundary
    return call.control(PhaseBoundary('work_unit',edge))['soft_budget_exceeded']


def _publish_chain(store, chain):
    with store._location.for_checkpoint(require_empty=True) as held:
        for manifest in chain:
            store._publish_held(held,manifest,store._pointer(held))


def start(invocation):
    from ..runtime.consumption import WorkConsumption
    from ..work.analyzer import advance
    from .work_handler import continuation
    own_call = invocation.consumption_call is None
    call = WorkConsumption().begin() if own_call else invocation.consumption_call
    try:
        initial = prepare_analyzer_work(invocation)
        store = _store(initial,invocation.options,invocation.resolved.working_directory)
        current, chain = initial, [initial]
        known = set(initial.objects)
        call.account_bytes('memory',len(initial.raw)+sum(len(raw) for raw in initial.objects.values()))
        pause = _pause(call,'start')
        while current.as_dict()['state']!='completed':
            if pause:
                _publish_chain(store,chain)
                return continuation(invocation.command.command_id,store,current)
            current=advance(current);chain.append(current)
            call.account_bytes('memory',len(current.raw)+sum(len(raw) for digest,raw in current.objects.items() if digest not in known))
            known.update(current.objects)
            pause=_pause(call)
        return deliver(invocation,current)
    except (CheckpointStorageError, WorkManifestError, WorkResumeError) as error:
        raise OperationFailure(FailureKind(getattr(error,'exit_code',6)),
            getattr(error,'reason','analyzer_work_invalid')) from error
    finally:
        if own_call: call.finish()


def deliver(invocation, manifest):
    payload, code = outcome(manifest)
    control, _, _ = checked(manifest)
    details = ({'execution_complete':False,'all_languages_confirmed':False,'gate_passed':False}
               if manifest.as_dict()['command_id']=='analyzer.run' else {})
    if control['output'] is not None:
        details['publication'] = publish(encoded(payload), control['output'],
            root=None if control['project'] is None else Path(control['project']),
            output_root=control['output_root'], cwd=control['cwd'], check_inputs=lambda: None)
    if invocation.command.command_id == 'work.resume':
        payload = dict(format_version='work-command-v1',operation='resume',data=payload)
    return (CommandResult.failed(invocation.command.command_id,FailureKind(code),complete=True,result=payload,details=details)
        if code else CommandResult(invocation.command.command_id,result=payload,details=details))


def work_command(invocation, store, operation):
    from .work_handler import _payload, continuation, absolute
    from ..work._public_errors import work_errors
    @work_errors
    def run():
        options = invocation.options
        require('--project' not in options, 'analyzer_work_project_override', exit_code=2)
        if operation == 'export':
            from ..work.package_publication import publish_work_package
            checked(store.read())
            output = absolute(options['--output'])
            return _payload(operation,publish_work_package(store,output_root=output.parent,output=output.name))
        if operation == 'cancel':
            from ..work.control import _cancel
            return _payload(operation,_cancel(store,options['--reason'],_runtime_build(),checked,lambda current:nullcontext()))
        require(operation == 'resume', 'analyzer_work_operation', exit_code=2)
        from ..runtime.consumption import WorkConsumption
        own_call = invocation.consumption_call is None
        call = WorkConsumption().begin() if own_call else invocation.consumption_call
        try:
            current = store.read()
            while current.as_dict()['state'] != 'completed':
                current = resume_analyzer_work(store)
                if current.as_dict()['state'] != 'completed' and _pause(call):
                    return continuation('work.resume',store,current)
            return deliver(invocation,current)
        finally:
            if own_call: call.finish()
    try:
        return run()
    except (WorkManifestError, WorkResumeError) as error:
        raise OperationFailure(FailureKind(getattr(error,'exit_code',3)),getattr(error,'reason','analyzer_work_invalid')) from error
