"""Shared Proposal errors, independent of original parsing and content hashing."""
from ..model.errors import ModelError


class ProposalError(ModelError):
    def __init__(self, reason, *, path=None, pointer='', exit_code=3):
        super().__init__(reason, path=path, pointer=pointer)
        self.exit_code = exit_code


def require(condition, reason, *, path=None, pointer='', exit_code=3):
    if not condition:
        raise ProposalError(reason, path=path, pointer=pointer, exit_code=exit_code)
