"""RFC-6901 syntax, shared by plan validation and isolated patch execution."""
import re
from .errors import ChangePlanError

def _pointer(value, pointer):
    if type(value) is not str or (value and not value.startswith("/")) or re.search(r"~(?![01])", value):
        raise ChangePlanError("invalid_json_pointer", pointer=pointer)
    return [p.replace("~1", "/").replace("~0", "~") for p in value.split("/")[1:]]
