"""Read an explicit Proposal and a live basis; no implicit stdin or writes."""
from dataclasses import replace

from ..bundles.errors import BundleError
from ..srx.errors import SrxError
from ..diagnostics import from_model_error

from ..authoring._inspection_snapshot import InspectionSnapshot
from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, OperationFailure
from ..model.errors import ModelError
from ..query._read_errors import read_details, read_failure
from ..runtime.preflight import require_project_read_preflight
from ..security import SafetyViolation
from ..storage.preflight_metadata import MetadataPhases
from ..storage.project import ProjectSource
from .context import ProposalContext
from ._validation_input import ProposalInput
from .validation import validate_proposal
from ._validation_result import validation_failure


def _preflight(source):
    require_project_read_preflight(source.boundary, source.configuration_bytes, MetadataPhases())


def validate_proposal_project(root, operand, *, cwd=None):
    project = None
    source = snapshot = supplied = None
    context = None
    details = read_details()
    try:
        source = ProjectSource(root)
        project = dict(project_root=str(source.boundary.root), project_id=source.configuration.project_id)
        _preflight(source)
        supplied = ProposalInput(source, operand, cwd)
        try:
            original = supplied.original()
            snapshot = InspectionSnapshot(root, None)
            context = ProposalContext(original, snapshot.model)
            report = validate_proposal(context)
        finally:
            # Invalid inputs receive the same final safety/currentness checks.
            _preflight(source)
            source.check_current()
            supplied.verify_current()
            if snapshot is not None:
                snapshot.verify_current()
        payload = report.data
        validate_result_document('proposal-validation-v1', payload)
        return CommandResult('proposal.validate', result=payload, project=project, details=details)
    except (ModelError, OperationFailure, SafetyViolation, OSError, SrxError, BundleError) as error:
        result = read_failure('proposal.validate', error, project, details)
        if isinstance(error, ModelError):
            result = replace(result, diagnostics=(from_model_error(error, code=getattr(error, 'code', None)),))
        payload = validation_failure(None if supplied is None else supplied.raw, context,
            getattr(error, 'reason', None) or (str(error) if isinstance(error, OperationFailure)
                                             else 'proposal_input_unavailable'))
        validate_result_document('proposal-validation-v1', payload)
        return replace(result, result=payload)


def validate_command(invocation):
    return validate_proposal_project(invocation.resolved.project_root, invocation.arguments['proposal'],
                                     cwd=invocation.resolved.working_directory)
