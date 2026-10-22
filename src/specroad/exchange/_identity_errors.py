"""Structured import identity diagnostics shared by values and lookup."""
from ..model.errors import ModelError


class ImportIdentityError(ModelError):
    exit_code = 3

    @property
    def code(self):
        collisions = ("duplicate_artifact_id", "duplicate_relation_id", "duplicate_external_identity",
                      "duplicate_external_artifact_identity", "duplicate_external_relation_identity")
        return "SRV147" if self.reason in collisions else "SRV090"

    def diagnostic(self):
        return {**super().diagnostic(), "code": self.code, "exit_code": self.exit_code}


def _error(error, *, path=None, prefix="", strip=""):
    pointer = error.pointer
    if strip and pointer.startswith(strip):
        pointer = pointer[len(strip):]
    # A malformed JSON member name must not make the diagnostic itself invalid
    # UTF-8. Keep the safe caller location, without echoing the invalid member.
    try:
        pointer.encode("utf-8")
    except UnicodeError:
        pointer = ""
    return ImportIdentityError(error.reason, path=path if path is not None else error.path,
        pointer=prefix + pointer, position=error.position, line=error.line,
        column=error.column, highest_supported=error.highest_supported)
