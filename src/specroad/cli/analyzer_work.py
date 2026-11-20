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


def _can_finish(current, call):
    _, request, _ = checked(current)
    if request is None: return False
    # Account for the retained request, every analyzer's full report and journal
    # candidates. This is a conservative soft-budget decision, not host capacity.
    retained = sum(len(raw) for raw in current.objects.values()) + len(current.raw)
    bound = retained + len(request.canonical_bytes)*(len(request.data['analyzers'])+4)*4
    return bound <= call._policy['effective_budgets']['memory']['value']


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
        storage_unavailable = False
        while current.as_dict()['state']!='completed':
            if pause and not storage_unavailable:
                try:
                    _publish_chain(store,chain)
                except OSError as error:
                    if not _can_finish(current,call):
                        raise OperationFailure(FailureKind.ENVIRONMENT,'analyzer_checkpoint_unavailable',
                            details={'errno':error.errno,'safe_completion_available':False}) from error
                    storage_unavailable=True
                else:
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
    details = {}
    if manifest.as_dict()['command_id'] == 'analyzer.run':
        from ..analyzers.packages import ReportPackage
        from ..analyzers.language_policy import execution_outcome
        details = execution_outcome(ReportPackage(encoded(payload)).reports,
                                    fail_on=invocation.resolved.values['fail_on'])
        # The retained native Work completion remains authoritative. An outcome
        # disagreement is a binding failure, never a regenerated completion.
        require(code == details.pop('exit_code'), 'analyzer_work_outcome_mismatch', exit_code=6)
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
