"""Static RFC-6901 JSON Pointer access to supplied values only.

    This is not a filesystem path, URI resolver, JSONPath or object attribute API.
"""

from .errors import SrxError
from ._json_values import json_type
from .types import MISSING


def parse_pointer(pointer, *, rule_id, at="/expression/pointer"):
    if type(pointer) is not str:
        raise SrxError("pointer_string_required", rule_id=rule_id, pointer=at,
                       expected="static JSON Pointer string", actual=json_type(pointer))
    try:
        pointer.encode("utf-8")
    except UnicodeError:
        raise SrxError("invalid_unicode", rule_id=rule_id, pointer=at,
                       expected="Unicode scalar string", actual="string") from None
    if pointer == "":
        return ()
    if not pointer.startswith("/"):
        raise SrxError("invalid_pointer", rule_id=rule_id, pointer=at,
                       expected="RFC-6901 JSON Pointer", actual="string")
    tokens = []
    for part in pointer[1:].split("/"):
        index = 0
        while index < len(part):
            if part[index] == "~":
                if index + 1 == len(part) or part[index + 1] not in "01":
                    raise SrxError("invalid_pointer_escape", rule_id=rule_id, pointer=at,
                                   expected="~0 or ~1 escape", actual="string")
                index += 1
            index += 1
        token = part.replace("~1", "/").replace("~0", "~")
        # Explicit SpecRoad restriction (SR-REQ-0518), beyond plain RFC 6901.
        if token in (".", ".."):
            raise SrxError("relative_pointer_segment", rule_id=rule_id, pointer=at,
                           expected="non-relative field token", actual="string")
        tokens.append(token)
    return tuple(tokens)


def resolve_tokens(root, tokens, *, rule_id, at="/expression/pointer"):
    """Walk already validated, own JSON data. A non-existing path is Missing."""
    current = root
    for token in tokens:
        if type(current) is dict:
            if token not in current:
                return MISSING
            current = current[token]
        elif type(current) is list:
            if token == "-":
                return MISSING
            if not (token == "0" or (token and "1" <= token[0] <= "9"
                    and all("0" <= char <= "9" for char in token))):
                raise SrxError("invalid_array_index", rule_id=rule_id, pointer=at,
                               expected="zero or unsigned decimal index without leading zero", actual="string")
            # Compare decimal length first: no unbounded int conversion.
            length = str(len(current))
            if len(token) > len(length) or (len(token) == len(length) and token >= length):
                return MISSING
            current = current[int(token)]
        else:
            return MISSING
    return current
