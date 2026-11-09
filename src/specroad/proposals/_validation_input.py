"""Explicit Proposal file/ID boundary with owned bytes and final reread."""
from pathlib import Path

from ..authoring._inspection_snapshot import InspectionChanged
from ..cli.results import FailureKind, OperationFailure
from ..model.identity_values import artifact_identity
from ..model.paths import artifact_path
from ..security import ProjectBoundary, SafetyViolation
from ..storage.json_syntax import parse_json_object
from .values import ProposalOriginal, require


class ProposalInput:
    def __init__(self, source, operand, cwd):
        if type(operand) is not str or not operand or operand == '-':
            raise OperationFailure(FailureKind.USAGE, 'proposal_file_or_id_required')
        if any(ord(char) < 32 or ord(char) == 127 for char in operand):
            raise SafetyViolation('Unsafe Proposal input path')
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
