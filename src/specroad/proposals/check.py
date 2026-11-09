"""Isolated Proposal inspection, using native services and no command chaining."""
from dataclasses import replace

from ..authoring._inspection_snapshot import InspectionSnapshot
from ..bundles.errors import BundleError
from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, OperationFailure
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..query._read_errors import read_details, read_failure
from ..security import SafetyViolation
from ..srx.errors import SrxError
from ..storage.project import ProjectSource
from ._validation_input import ProposalInput
from ._validation_result import validation_failure
from .context import ProposalContext, reconstruct_proposal_target
from .project_validation import _preflight
from .scope import specification_manifest
from .validation import validate_proposal
from .values import require
from ._check_workspace import CheckWorkspace
from ._check_services import _specification_files, _qualify, _services
from ._check_report import _now, _initial


def _isolated(snapshot, original, workspace, report, services):
    basis_root = workspace.materialize('basis', snapshot.raw)
    private = InspectionSnapshot(basis_root, None, include_archive_objects=True)
    context = ProposalContext(original, private.model)
    validate_proposal(context)
    target = reconstruct_proposal_target(context)
    # Preserve packages which have native identities but no TargetModel source path.
    extra = {p: raw for p, raw in private.raw.items() if p not in private.model.source_files}
    target_root = workspace.materialize('target', {**extra, **target.source_files})
    actual = InspectionSnapshot(target_root, None, include_archive_objects=True)
    require(actual.model._sources_sha256 == target._sources_sha256,
            'proposal_materialized_target_changed', exit_code=6)
    report['target_model_root_sha256'] = specification_manifest(actual.model).sha256
    report['target_sources_sha256'] = actual.model._sources_sha256
    basis = _qualify(_specification_files(private.model, private.raw), report['checks'], 'basis', services)
    final = _qualify(_specification_files(actual.model, actual.raw), report['checks'], 'target', services)
    _services(basis, final, report)
    workspace.verify()
    private.verify_current()
    actual.verify_current()


def check_proposal_project(root, operand, *, cwd=None, keep_workspace=False, services=None):
    """Return bound observations; no caller-supplied check result grants authority."""
    project = None
    source = snapshot = supplied = context = workspace = None
    report = _initial()
    details = read_details()
    try:
        from ..recovery.services import native_services
        services = native_services(services)
        source = ProjectSource(root)
        project = dict(project_root=str(source.boundary.root), project_id=source.configuration.project_id)
        _preflight(source)
        supplied = ProposalInput(source, operand, cwd)
        try:
            original = supplied.original()
            snapshot = InspectionSnapshot(root, None, include_archive_objects=True)
            context = ProposalContext(original, snapshot.model)
            report.update(observed_status=original.data['proposal_status'], binding=original.binding.data,
                proposal_sha256=original.sha256, context_sha256=context.sha256)
            report['audit'].update(proposal_id=original.data['id'], base=original.data['base'])
            workspace = CheckWorkspace(source.boundary.root, keep_workspace)
            try:
                workspace.create()
                _isolated(snapshot, original, workspace, report, services)
            finally:
                try:
                    workspace.close()
                finally:
                    report['workspace'] = dict(workspace.state)
        finally:
            _preflight(source)
            source.check_current()
            supplied.verify_current()
            if snapshot is not None:
                snapshot.verify_current()
        report.update(passed=True, full_semantic_validation=True,
            eligible_transition='checked' if report['observed_status'] == 'validated' else None)
        result = CommandResult('proposal.check', project=project, details={**details,
            'full_semantic_validation': True, 'validation_scope': 'proposal_specification_basis_and_target'})
    except (ModelError, OperationFailure, SafetyViolation, OSError, SrxError, BundleError) as error:
        result = read_failure('proposal.check', error, project, details)
        observed = validation_failure(None if supplied is None else supplied.raw, context,
            getattr(error, 'reason', None) or 'proposal_check_failed')
        report.update(observed_status=observed['observed_status'], proposal_sha256=observed['proposal_sha256'])
        report['audit']['diagnostics'] = [d.as_dict() for d in result.diagnostics]
        if workspace is not None:
            report['workspace'] = dict(workspace.state)
    report['audit']['diagnostics'] += [d for value in report['checks'].get('validation', {}).values()
        for stage in value['stages'] for d in stage['diagnostics']]
    report['audit']['diagnostics'] += report['checks'].get('lint', {}).get('diagnostics', [])
    report['audit'].update(ended_at=_now(), outcome='passed' if report['passed'] else 'failed')
    report['result_sha256'] = canonical_json_sha256(report)
    validate_result_document('proposal-check-v1', report)
    return replace(result, result=report)


def check_command(invocation):
    return check_proposal_project(invocation.resolved.project_root, invocation.arguments['proposal'],
        cwd=invocation.resolved.working_directory,
        keep_workspace=invocation.options.get('--keep-workspace', False), services=invocation.restore_services)
