"""Semantic deterministic ordering, independent of console presentation."""
import json
from ..result_contract import ResultContractError
from .values import Diagnostic, SEVERITIES

def _optional_key(value):
    return (0, "") if value is None else (1, value)


def diagnostic_key(item):
    if type(item) is not Diagnostic:
        raise ResultContractError("Expected a typed diagnostic")
    pointer = None if item.location is None else item.location.get("pointer")
    return (SEVERITIES.index(item.severity), _optional_key(item.path),
            _optional_key(item.artifact_id), _optional_key(pointer), item.code,
            tuple(-1 if item.location is None or item.location.get(k) is None else item.location[k]
                  for k in ("line", "column", "end_line", "end_column", "byte_offset", "character_offset")),
            item.origin, _optional_key(item.rule_id),
            json.dumps(item.as_dict(), ensure_ascii=True, sort_keys=True, separators=(",", ":")))

