"""Public passive Proposal Work routing; Apply remains a separate native writer."""
from contextlib import nullcontext

from ..bundles.errors import BundleError
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..srx.errors import SrxError
from ..work.proposal import prepare_proposal_work, resume_proposal_work, proposal_work_result, checked
from ..work.resume import WorkResumeError, _runtime_build
from ..work.root import WorkDirectory
from ..work.checkpoints import CheckpointStore, CheckpointStorageError
from ..work._data_contract import WorkManifestError
from .results import CommandResult, FailureKind, OperationFailure


def check_command(invocation):
    from ..proposals.check import check_command as direct
    options = invocation.options
    work = ('--work-dir' in options or options.get('--resource-profile') == 'constrained'
            or any(key in options for key in ('--step-cpu-ms', '--step-wall-ms',
                                               '--cpu-budget-ms', '--wall-budget-ms')))
    if not work:
        return direct(invocation)
    if options.get('--keep-workspace'):
        raise OperationFailure(FailureKind.USAGE, 'proposal_work_debug_workspace_incompatible')
    try:
        initial, protected = prepare_proposal_work(invocation.registry,
            invocation.resolved.project_root, invocation.arguments['proposal'],
            cwd=invocation.resolved.working_directory)
        location = WorkDirectory(initial, protected_roots=protected, directory=options.get('--work-dir'))
        store = CheckpointStore(location, initial)
        with location.for_checkpoint(require_empty=True) as held:
            store._publish_held(held, initial, None)
        current = resume_proposal_work(store, services=invocation.restore_services)
        from .work_handler import continuation
        return continuation('proposal.check', store, current)
    except (ModelError, BundleError, SrxError, SafetyViolation, OSError, WorkResumeError,
            WorkManifestError, CheckpointStorageError) as error:
        code = 7 if isinstance(error, SafetyViolation) else 5 if isinstance(error, OSError) else getattr(error, 'exit_code', 3)
        raise OperationFailure(FailureKind(code), getattr(error, 'reason', 'proposal_work_invalid')) from error


def work_command(invocation, store, operation):
    from .work_handler import _payload, continuation, absolute
    from ..work._public_errors import work_errors
    @work_errors
    def run():
        options = invocation.options
        if any(key in options for key in ('--force', '--expected-lock-sha256', '--accept-remote-risk',
                '--expected-work-lock-sha256', '--work-recovery-reason', '--project')):
            raise WorkResumeError('proposal_work_passive_options_required', exit_code=2)
        if operation == 'export':
            from ..work.package_publication import publish_work_package
            checked(store.read())
            output = absolute(options['--output'])
            return _payload(operation, publish_work_package(store, output_root=output.parent, output=output.name))
        if operation == 'cancel':
            from ..work.control import _cancel
            return _payload(operation, _cancel(store, options['--reason'], _runtime_build(), checked,
                                               lambda current: nullcontext()))
        if operation != 'resume':
            raise WorkResumeError('proposal_work_operation_invalid', exit_code=2)
        current = resume_proposal_work(store, services=invocation.restore_services)
        if current.as_dict()['state'] != 'completed':
            return continuation('work.resume', store, current)
        document, code = proposal_work_result(store, services=invocation.restore_services)
        payload = {'format_version': 'work-command-v1', 'operation': operation, 'data': document}
        return (CommandResult.failed('work.resume', FailureKind(code), complete=True, result=payload) if code
                else CommandResult('work.resume', result=payload))
    return run()
