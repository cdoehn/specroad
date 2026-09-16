"""Human JSON encoding only; never use these bytes as a JCS hash projection.

Validation, source-role decisions and integrity checks belong to the caller.
The stable ordering here is Unicode codepoint order, unlike JCS UTF-16 order.
"""

import json


def encode_normal_form(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False,
                       sort_keys=True, indent=2) + "\n").encode("utf-8")
