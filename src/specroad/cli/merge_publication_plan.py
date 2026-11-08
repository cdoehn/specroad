"""Read-only handoff from complete preparation to the existing ChangePlan."""
from ..model.errors import ModelError
from ..bundles.errors import BundleError
from ..srx.errors import SrxError
from ..storage.archive import ArchiveError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object as parsed
from ..changes.execution_values import ChangeExecutionError
from ..changes.schema_transition_values import authoring
from ..merge._recorded import capture_sources
from ..merge.preparation import prepare_merge
from ..work.resume import WorkResumeError
from ..work.checkpoints import CheckpointStorageError
from ..work._data_contract import WorkManifestError
from .merge_publication_inputs import (required, require, root_option, live_sources,
    input_file, from_preparation, command_error)
from .results import CommandResult, FailureKind, OperationFailure


def publication_plan_command(invocation):
    options = invocation.options
    try:
        forbidden = {'--fail-on-change', '--resource-profile', '--step-cpu-ms', '--step-wall-ms',
                     '--cpu-budget-ms', '--wall-budget-ms'}
        if forbidden.intersection(options):
            raise OperationFailure(FailureKind.USAGE, 'merge_publication_complete_preparation_required')
        required(options, '--history', '--plan-id', '--change-plan-id', '--actor-type', '--actor-id', '--planned-at')
        root = root_option(options)
        history_raw, history_current = input_file(options['--history'])
        history = parsed(history_raw)
        sources = live_sources(options)
        if '--work-dir' in options:
            if {'--resolutions', '--expected-plan-sha256'}.intersection(options):
                raise OperationFailure(FailureKind.USAGE, 'merge_publication_input_modes_conflict')
            from ..work.open_existing import open_restore_work
            from ..work.merge import checked, merge_work_result
            store = open_restore_work(options['--work-dir'], registry=invocation.registry)
            observed = store.read()
            inputs, _, _, _, _, _ = checked(observed)
            document, _ = merge_work_result(store, services=invocation.restore_services)
            require(inputs['sources'] == capture_sources(sources)
                    and inputs['history'] == history and inputs['plan_id'] == options['--plan-id'],
                    'merge_publication_work_inputs_changed')
            def preparation_current():
                require(store.read().raw == observed.raw, 'merge_publication_work_changed')
        else:
            if ('--resolutions' in options) != ('--expected-plan-sha256' in options):
                raise OperationFailure(FailureKind.USAGE, 'merge_resolution_binding_required')
            raw, preparation_current = (input_file(options['--resolutions']) if '--resolutions' in options
                                         else (None, lambda: None))
            document = prepare_merge(sources, plan_id=options['--plan-id'], history=history,
                plan_raw=raw, expected_plan_sha256=options.get('--expected-plan-sha256'),
                services=invocation.restore_services)
        plan = from_preparation(root, document, sources, history, options, invocation.restore_services)
        authoring(plan)
        history_current(); preparation_current()
        for role in ('base', 'ours', 'theirs'):
            getattr(sources, role).verify_current()
        return CommandResult('merge.plan', result={'format_version': 'merge-publication-plan-v1',
            'change_plan': plan.data, 'change_plan_sha256': plan.sha256,
            'project_writes_performed': False, 'approval_granted': False, 'write_authorized': False})
    except (ModelError, BundleError, SrxError, ArchiveError, SafetyViolation, OSError, ChangeExecutionError,
            WorkResumeError, WorkManifestError, CheckpointStorageError) as error:
        raise command_error(error) from error
