"""Read an explicit Proposal and a live basis; no implicit stdin or writes."""
from pathlib import Path
from dataclasses import replace

from ..bundles.errors import BundleError
from ..srx.errors import SrxError
from ..diagnostics import from_model_error

from ..authoring._inspection_snapshot import InspectionSnapshot, InspectionChanged
from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..model.errors import ModelError
from ..model.identity_values import artifact_identity
from ..model.paths import artifact_path
from ..query._read_errors import read_details, read_failure
from ..runtime.preflight import require_project_read_preflight
from ..security import ProjectBoundary, SafetyViolation
from ..storage.json_syntax import parse_json_object
from ..storage.preflight_metadata import MetadataPhases
from ..storage.project import ProjectSource
from .context import ProposalContext
from .values import ProposalOriginal, require
from .validation import validate_proposal


def _preflight(source):
    require_project_read_preflight(source.boundary, source.configuration_bytes, MetadataPhases())


class _ProposalInput:
    def __init__(self, source, operand, cwd):
        if type(operand) is not str or not operand or operand == '-':
            raise OperationFailure(FailureKind.USAGE, 'proposal_file_or_id_required')
        root = source.boundary.root
        prefix = source.configuration.id_prefix
        self.requested_id = None
        if '/' not in operand and '\\' not in operand and '-PROP-' in operand:
            self.requested_id = operand
            path = root / artifact_path('proposal', operand, prefix)
        else:
            path = Path(operand)
            if not path.is_absolute():
                path = Path.cwd() / path if cwd is None else Path(cwd) / path
            path = path.absolute()
        self.boundary = ProjectBoundary(path.parent)
        if self.boundary.root != path.parent:
            raise SafetyViolation('Canonical Proposal input parent required')
        self.path = path
        self.raw = self.boundary.read_bytes(path.name)
        self.root = root
        self.prefix = prefix

    def original(self):
        value = parse_json_object(self.raw, path=str(self.path))
        identity = artifact_identity(value)
        require(identity.artifact_type == 'proposal', 'proposal_identity_required')
        require(identity.id_prefix == self.prefix, 'proposal_project_prefix_mismatch')
        canonical_path = artifact_path('proposal', identity.id, self.prefix)
        if self.requested_id is not None:
            require(identity.id == self.requested_id, 'proposal_input_identity_mismatch')
        if self.path.is_relative_to(self.root):
            require(self.path.relative_to(self.root).as_posix() == canonical_path,
                    'proposal_managed_path_mismatch')
        return ProposalOriginal(self.raw, path=canonical_path)

    def verify_current(self):
        try:
            raw = self.boundary.read_bytes(self.path.name)
        except FileNotFoundError as error:
            raise InspectionChanged('proposal_input_disappeared') from error
        if raw != self.raw:
            raise InspectionChanged('proposal_input_changed')


def validate_proposal_project(root, operand, *, cwd=None):
    project = None
    source = snapshot = supplied = None
    details = read_details()
    try:
        source = ProjectSource(root)
        project = dict(project_root=str(source.boundary.root), project_id=source.configuration.project_id)
        _preflight(source)
        supplied = _ProposalInput(source, operand, cwd)
        try:
            original = supplied.original()
            snapshot = InspectionSnapshot(root, None)
            report = validate_proposal(ProposalContext(original, snapshot.model))
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
        return result


def validate_command(invocation):
    return validate_proposal_project(invocation.resolved.project_root, invocation.arguments['proposal'],
                                     cwd=invocation.resolved.working_directory)
