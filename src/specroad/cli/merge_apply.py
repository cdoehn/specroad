"""Public Merge-Apply: existing native receipt, source, backup and writer gates."""
from pathlib import Path

from ..model.errors import ModelError
from ..bundles.errors import BundleError
from ..srx.errors import SrxError
from ..storage.archive import ArchiveError
from ..security import SafetyViolation
from ..changes.values import ChangePlan
from ..changes.execution_values import ChangeExecutionError
from ..changes.publication_values import PublicationAuthority
from ..changes.schema_transition_values import authoring
from ..changes._journal_codec import _transaction
from ..changes._lock_files import LockFiles
from ..changes.schema_transition_recovery import historical_request
from ..storage.operational_preflight import observe_operational_preflight
from ..merge.publication import apply_merge_publication
from .merge_publication_inputs import (required, require, root_option, live_sources,
    input_file, revalidate, command_error)
from .results import CommandResult, FailureKind, OperationFailure


def _historical(root, plan):
    with LockFiles(root) as files:
        require(observe_operational_preflight(files.boundary)['consistency_state'] == 'consistent',
                'merge_publication_recovery_required')
        project_id = plan.data['operations'][0]['inputs']['sources']['ours']['binding']['project_id']
        return historical_request(files, plan, project_id)


def _backup(root, plan, sources, options):
    from ..migration._backup_source import _observe
    from ..documents._export_targets import _output_boundary
    from ..merge.publication_target import recheck_plan
    from ..merge.publication_backup import prepare_merge_backup, create_merge_backup, verify_merge_backup
    files, source, current = _observe(root)
    recheck_plan(plan, files)
    expected = prepare_merge_backup(files)
    external = _output_boundary(options['--backup-root'], source)
    for role in ('base', 'ours', 'theirs'):
        item = getattr(sources, role)
        location = Path(item.source_root)
        if item.kind != 'bundle' and (external.root == location or location in external.root.parents):
            raise SafetyViolation('Merge backup must be outside all live project sources')
    name = options['--backup']
    try:
        raw = external.read_bytes(name)
    except FileNotFoundError:
        return create_merge_backup(root, plan.source_bytes, expected_plan_sha256=plan.sha256,
            output_root=options['--backup-root'], output=name)
    require(raw == expected.source_bytes, 'merge_backup_existing_changed')
    checked = verify_merge_backup(raw, expected_sha256=expected.sha256,
        expected_source_files_sha256=expected.manifest['source_files_sha256'])
    current()
    require(external.read_bytes(name) == raw, 'merge_backup_existing_changed')
    return {'file': {'path': str(external.root/name), 'size': len(raw), 'sha256': checked.sha256},
        'output_root': str(external.root), 'source_files_sha256': checked.manifest['source_files_sha256'],
        'backup_verified': True, 'approval_granted': False, 'write_authorized': False}


def apply_command(invocation):
    options = invocation.options
    try:
        required(options, '--expected-plan-sha256')
        root = root_option(options)
        raw, plan_current = input_file(invocation.arguments['merge_plan'])
        plan = ChangePlan(raw)
        require(plan.data.get('metadata_policy_version') == 'merge-metadata-v1'
                and plan.sha256 == options['--expected-plan-sha256'], 'merge_publication_plan_binding')
        authoring(plan)
        dry_run = options.get('--dry-run', False)
        if not dry_run and type(invocation.publication_authority) is not PublicationAuthority:
            raise OperationFailure(FailureKind.USAGE, 'merge_publication_explicit_authority_required')
        historical = None if dry_run else _historical(root, plan)
        if historical is not None:
            plan_current()
            # Native complete receipt was proved before touching live source or backup paths.
            outcome = historical
        else:
            if not dry_run:
                required(options, '--backup-root', '--backup', '--transaction-id')
                _transaction(options['--transaction-id'])
            sources = live_sources(options)
            revalidate(root, plan, sources, invocation.restore_services)
            plan_current()
            if dry_run:
                outcome = None
            else:
                backup = _backup(root, plan, sources, options)
                plan_current()
                descriptor = {**backup['file'], 'output_root': backup['output_root'],
                              'source_files_sha256': backup['source_files_sha256']}
                outcome = apply_merge_publication(root, raw, expected_plan_sha256=plan.sha256,
                    sources=sources, transaction_id=options['--transaction-id'], backup_descriptor=descriptor,
                    authority=invocation.publication_authority, services=invocation.restore_services)
        return CommandResult('merge.apply', result={'format_version': 'merge-apply-command-v1',
            'mode': 'dry_run' if dry_run else 'apply', 'change_plan_sha256': plan.sha256,
            'execution': outcome, 'project_writes_performed': outcome is not None and not outcome['replayed'],
            'approval_granted': False, 'write_authorized': False})
    except (ModelError, BundleError, SrxError, ArchiveError, SafetyViolation, OSError, ChangeExecutionError) as error:
        raise command_error(error) from error
