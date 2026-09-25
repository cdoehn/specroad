"""Value-only Change Plan errors; never include submitted source values."""
from ..model.errors import ModelError


class ChangePlanError(ModelError):
    code = "SRV070"
    exit_code = 3

    def __init__(self, reason, *, pointer="", code="SRV070", path=None):
        super().__init__(reason, pointer=pointer, path=path)
        self.code = code

    def diagnostic(self):
        return {**super().diagnostic(), "code": self.code, "exit_code": self.exit_code}
