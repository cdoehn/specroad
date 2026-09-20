"""Own immutable JSON snapshots; no user conversion hooks or I/O.

Container values become tagged tuples. Iterative construction/materialization
also keeps deeply nested literal data independent of the Python call stack.
This is a value snapshot, not a hash, schema validator or parser budget policy.
"""

from dataclasses import dataclass
import math
from .errors import SrxError


def json_type(value):
    kind = type(value)
    if value is None:
        return "null"
    if kind is bool:
        return "boolean"
    if kind in (int, float):
        return "number"
    if kind is str:
        return "string"
    if kind is list:
        return "array"
    if kind is dict:
        return "object"
    return "non_json"


def child_pointer(parent, key):
    return parent + "/" + key.replace("~", "~0").replace("/", "~1")


def _freeze(value, rule_id, pointer, subject):
    active = set()
    values = []
    work = [("visit", value, pointer)]
    while work:
        action, current, at = work.pop()
        if action == "finish":
            kind, identity, keys, count = current
            children = values[-count:] if count else []
            if count:
                del values[-count:]
            contents = tuple(zip(keys, children)) if kind == "object" else tuple(children)
            values.append((kind, contents))
            active.remove(identity)
            continue
        kind = json_type(current)
        if kind == "non_json":
            raise SrxError("non_json_value", rule_id=rule_id, pointer=at,
                           expected="JSON", actual=kind, subject=subject)
        if kind == "number" and type(current) is float and not math.isfinite(current):
            raise SrxError("non_finite_number", rule_id=rule_id, pointer=at,
                           expected="finite number", actual="number", subject=subject)
        if kind == "string":
            try:
                current.encode("utf-8")
            except UnicodeError:
                raise SrxError("invalid_unicode", rule_id=rule_id, pointer=at,
                               expected="Unicode scalar string", actual=kind,
                               subject=subject) from None
        if kind not in ("object", "array"):
            values.append((kind, current))
            continue
        identity = id(current)
        if identity in active:
            raise SrxError("cyclic_json_value", rule_id=rule_id, pointer=at,
                           expected="acyclic JSON", actual=kind, subject=subject)
        active.add(identity)
        if kind == "object":
            keys = tuple(current)
            for key in keys:
                if type(key) is not str:
                    raise SrxError("non_string_key", rule_id=rule_id, pointer=at,
                                   expected="string key", actual=json_type(key), subject=subject)
                try:
                    key.encode("utf-8")
                except UnicodeError:
                    raise SrxError("invalid_unicode", rule_id=rule_id, pointer=at,
                                   expected="Unicode scalar key", actual="string", subject=subject) from None
            children = [(current[key], child_pointer(at, key)) for key in keys]
        else:
            keys = ()
            children = [(item, at + "/" + str(index)) for index, item in enumerate(current)]
        work.append(("finish", (kind, identity, keys, len(children)), at))
        work.extend(("visit", item, path) for item, path in reversed(children))
    return values[0]


def _thaw(tree):
    holder = [None]
    work = [(tree, holder, 0)]
    while work:
        (kind, contents), parent, key = work.pop()
        if kind == "object":
            value = {}
            # Insert in the stored order; processing order has no field semantics.
            for name, _ in contents:
                value[name] = None
            work.extend((child, value, name) for name, child in reversed(contents))
        elif kind == "array":
            value = [None] * len(contents)
            work.extend((child, value, index) for index, child in reversed(tuple(enumerate(contents))))
        else:
            value = contents
        parent[key] = value
    return holder[0]


@dataclass(frozen=True, init=False)
class JsonSnapshot:
    _tree: tuple

    def __init__(self, value, *, rule_id, pointer="", subject="expression"):
        object.__setattr__(self, "_tree", _freeze(value, rule_id, pointer, subject))

    @property
    def data(self):
        return _thaw(self._tree)
