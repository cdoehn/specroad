"""Project parser observations without guessing unavailable source locations."""
from ..model.errors import ModelError
from ..result_contract import ResultContractError
from .values import Diagnostic

def from_model_error(error, *, artifact_id=None, source=None, code=None, origin="core_rule", rule_id=None):
    """Preserve observed pointers and coordinates, never recover IDs from broken JSON.

    JSON syntax offsets count codepoints; UTF-8 decoding offsets count bytes.
    Supplying the exact original source permits converting the other coordinate.
    No source bytes or excerpts are copied into the human message.
    """
    if not isinstance(error, ModelError):
        raise ResultContractError("Expected a model error")
    if source is not None and type(source) is not bytes:
        raise ResultContractError("Source must be bytes")
    location = {"pointer": error.pointer, "line": error.line, "column": error.column,
                "byte_offset": None, "character_offset": None}
    position = error.position
    if position is not None:
        if type(position) is not int or position < 0:
            raise ResultContractError("Invalid observed source offset")
        if error.reason == "invalid_utf8":
            location["byte_offset"] = position
            if source is not None:
                if position > len(source):
                    raise ResultContractError("Source does not contain observed position")
                try:
                    prefix = source[:position].decode("utf-8")
                except UnicodeError as exc:
                    raise ResultContractError("Invalid source prefix") from exc
                location["character_offset"] = len(prefix)
                location["line"] = prefix.count("\n") + 1
                location["column"] = len(prefix.rsplit("\n", 1)[-1]) + 1
        elif error.reason == "invalid_json":
            location["character_offset"] = position
            if source is not None:
                try:
                    text = source.decode("utf-8")
                except UnicodeError as exc:
                    raise ResultContractError("Source is not UTF-8") from exc
                if position > len(text):
                    raise ResultContractError("Source does not contain observed position")
                prefix = text[:position]
                observed_line = prefix.count("\n") + 1
                observed_column = len(prefix.rsplit("\n", 1)[-1]) + 1
                if ((error.line is not None and error.line != observed_line) or
                        (error.column is not None and error.column != observed_column)):
                    raise ResultContractError("Source coordinates contradict the observed position")
                location["line"] = observed_line
                location["column"] = observed_column
                location["byte_offset"] = len(prefix.encode("utf-8"))
    if code is None:
        code = "SRV001" if error.reason in ("invalid_json", "invalid_utf8", "duplicate_key", "invalid_unicode", "object_required") else "SRV002"
    return Diagnostic(code, "error", "parse" if code == "SRV001" else "model",
        "Project data does not satisfy its declared contract.", origin=origin,
        rule_id=rule_id, artifact_id=artifact_id, path=error.path, location=location,
        rationale=error.reason, remediation="Inspect the indicated source without changing unrelated data.")

