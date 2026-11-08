"""Explicit source acquisition and passive native merge planning, including Work."""
from pathlib import Path
from contextlib import nullcontext

from ..model.errors import ModelError
from ..bundles.errors import BundleError
from ..srx.errors import SrxError
from ..security import ProjectBoundary, SafetyViolation
from ..storage.json_syntax import parse_json_object as parsed
from ..merge.sources import SourceRequest, load_merge_sources
from ..merge.preparation import prepare_merge
from ..work.merge import prepare_merge_work, resume_merge_work, merge_work_result, checked
from ..work.resume import WorkResumeError, _runtime_build
from ..work.root import WorkDirectory
from ..work.checkpoints import CheckpointStore, CheckpointStorageError
from ..work._data_contract import WorkManifestError
from .merge_resolution import _read_file
from .results import CommandResult, FailureKind, OperationFailure


def _result(command, document, code=0):
    if code:
        return CommandResult.failed(command, FailureKind.POLICY, complete=True, result=document)
    return CommandResult(command, result=document)


def planning_command(invocation):
    try:
        options = invocation.options
        if not all('--'+key in options for key in ('base', 'ours', 'theirs', 'history', 'plan-id')):
            raise OperationFailure(FailureKind.USAGE, 'Explicit merge sources, history and plan ID required')
        if ('--resolutions' in options) != ('--expected-plan-sha256' in options):
            raise OperationFailure(FailureKind.USAGE, 'Original resolution bytes and expected hash required together')
        requests = [SourceRequest(options['--'+role], options.get('--'+role+'-kind', 'local'),
                                  options.get('--'+role+'-ref')) for role in ('base', 'ours', 'theirs')]
        if any(not Path(request.root).is_absolute() for request in requests):
            raise OperationFailure(FailureKind.USAGE, 'Absolute merge source roots required')
        history_file = _read_file(options['--history'])
        resolution_file = _read_file(options['--resolutions']) if '--resolutions' in options else None
        sources = load_merge_sources(*requests)
        inputs = {'plan_id': options['--plan-id'], 'history': parsed(history_file[2]),
            'plan_raw': None if resolution_file is None else resolution_file[2],
            'expected_plan_sha256': options.get('--expected-plan-sha256')}
        def current():
            for file in (history_file, resolution_file):
                if file is not None and file[0].read_bytes(file[1]) != file[2]:
                    raise SafetyViolation('Merge preparation input changed')
            for role in ('base', 'ours', 'theirs'):
                getattr(sources, role).verify_current()
        work = ('--work-dir' in options or options.get('--resource-profile') == 'constrained'
                or any(key in options for key in ('--step-cpu-ms', '--step-wall-ms',
                                                  '--cpu-budget-ms', '--wall-budget-ms')))
        if not work:
            document = prepare_merge(sources, **inputs, services=invocation.restore_services)
            current()
            return _result('merge.plan', document,
                           1 if options.get('--fail-on-change') and document['changed'] is True else 0)
        initial = prepare_merge_work(invocation.registry, sources, **inputs,
                                     fail_on_change=options.get('--fail-on-change', False))
        protected = [ProjectBoundary(Path(request.root).parent if request.kind == 'bundle' else request.root)
                     for request in requests]
        protected += [file[0] for file in (history_file, resolution_file) if file is not None]
        location = WorkDirectory(initial, protected_roots=tuple(protected), directory=options.get('--work-dir'))
        store = CheckpointStore(location, initial)
        current()
        with location.for_checkpoint(require_empty=True) as held:
            store._publish_held(held, initial, None)
        # Source observation is sealed now. Future passive work uses these bytes,
        # not mutable paths and not any stored executable host provider.
        manifest = resume_merge_work(store, services=invocation.restore_services)
        from .work_handler import continuation
        return continuation('merge.plan', store, manifest)
    except (ModelError, BundleError, SrxError, SafetyViolation, OSError, WorkResumeError,
            WorkManifestError, CheckpointStorageError) as error:
        code = 7 if isinstance(error, SafetyViolation) else 5 if isinstance(error, OSError) else getattr(error, 'exit_code', 3)
        raise OperationFailure(FailureKind(code), getattr(error, 'reason', 'merge_preparation_invalid')) from error


def work_command(invocation, store, operation):
    from .work_handler import _payload, continuation, absolute
    from ..work._public_errors import work_errors
    @work_errors
    def run():
        options = invocation.options
        if any(key in options for key in ('--force', '--expected-lock-sha256', '--accept-remote-risk',
                '--expected-work-lock-sha256', '--work-recovery-reason', '--project')):
            raise WorkResumeError('merge_work_passive_options_required', exit_code=2)
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
            raise WorkResumeError('merge_work_operation_invalid', exit_code=2)
        manifest = resume_merge_work(store, services=invocation.restore_services)
        if manifest.as_dict()['state'] != 'completed':
            return continuation('work.resume', store, manifest)
        document, code = merge_work_result(store, services=invocation.restore_services)
        return _result('work.resume', {'format_version': 'work-command-v1', 'operation': operation,
                                      'data': document}, code)
    return run()
