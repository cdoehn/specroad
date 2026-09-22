"""Private SRX components; no host or project execution."""

from .errors import SrxError
from ._json_values import json_type
from .operators import OPERATOR_FIELDS, SUPPORTED_OPERATORS, UNARY_OPERATORS, BINARY_OPERATORS, QUANTIFIER_OPERATORS

LANGUAGE = "srx"
VERSION = "1.0"
CONTEXT_NAMES = ("artifact", "configuration", "project", "relations")


def _rule_id(rule_id):
    if type(rule_id) is not str or not rule_id.strip():
        raise SrxError("rule_id_required", rule_id=None, expected="nonempty string",
                       actual=json_type(rule_id))
    try:
        rule_id.encode("utf-8")
    except UnicodeError:
        raise SrxError("invalid_rule_id", rule_id=None, expected="Unicode string",
                       actual="string") from None
    return rule_id


def _exact_fields(value, names, *, rule_id, pointer, subject="expression"):
    if type(value) is not dict:
        raise SrxError("object_required", rule_id=rule_id, pointer=pointer,
                       expected="object", actual=json_type(value), subject=subject)
    if any(type(key) is not str for key in value):
        raise SrxError("non_string_key", rule_id=rule_id, pointer=pointer,
                       expected="string key", actual="non_string", subject=subject)
    if set(value) != set(names):
        raise SrxError("invalid_fields", rule_id=rule_id, pointer=pointer,
                       expected="closed object", actual="object", subject=subject)


def _validate_document(data, rule_id, *, structure_limits=None):
    _exact_fields(data, ("language", "version", "expression"), rule_id=rule_id, pointer="")
    if type(data["language"]) is not str or data["language"] != LANGUAGE:
        raise SrxError("unsupported_language", rule_id=rule_id, pointer="/language",
                       expected="srx", actual=json_type(data["language"]))
    if type(data["version"]) is not str or data["version"] != VERSION:
        raise SrxError("unsupported_version", rule_id=rule_id, pointer="/version",
                       expected="1.0", actual=json_type(data["version"]))
    return _validate_expression(data["expression"], rule_id, structure_limits=structure_limits)


def _validate_expression(expression, rule_id, *, structure_limits=None):
    """Check the entire executable AST, including runtime-skipped branches.

    Iterator frames keep the frontier proportional to depth, not the width of
    an untrusted args array. Shared occurrences count individually; true cycles
    fail before traversal or JSON cloning can loop.
    """
    from .fields import checked_selector
    from .graph_validation import GRAPH_OPERATORS, validate_graph_node
    from .resource_policy import StructureLimits, SrxResourcePolicyError
    from ._resource_accounting import StructureCounter
    limits = StructureLimits() if structure_limits is None else structure_limits
    if type(limits) is not StructureLimits:
        raise SrxResourcePolicyError(rule_id=rule_id, pointer="/structure")
    counter = StructureCounter(limits, rule_id)
    work = [(iter(((expression, "/expression", False, 1),)), None)]
    while work:
        iterator, owner = work[-1]
        try:
            node, at, item_in_scope, depth = next(iterator)
        except StopIteration:
            work.pop()
            if owner is not None:
                counter.leave(owner)
            continue
        if type(node) is not dict:
            raise SrxError("object_required", rule_id=rule_id, pointer=at,
                           expected="expression object", actual=json_type(node))
        counter.enter(node, at, depth)
        # Do not hash arbitrary user keys, compare foreign strings, or invoke
        # conversion hooks while validating an as-yet-unsnapshotted program.
        if any(type(key) is not str for key in node):
            raise SrxError("non_string_key", rule_id=rule_id, pointer=at,
                           expected="string key", actual="non_string")
        op = node.get("op")
        if type(op) is not str or op not in SUPPORTED_OPERATORS:
            raise SrxError("unsupported_operator", rule_id=rule_id, pointer=at+"/op",
                           expected="supported operator", actual=json_type(op))
        if op in GRAPH_OPERATORS:
            validate_graph_node(node, rule_id=rule_id, at=at)
            children = ((node["where"], at+"/where", item_in_scope, depth+1),) if op == "reachable" else ()
        else:
            _exact_fields(node, OPERATOR_FIELDS[op], rule_id=rule_id, pointer=at)
            if op == "literal":
                children = ()  # Literal JSON is data, not executable AST.
            elif op == "field":
                checked_selector(node["context"], node["pointer"], rule_id=rule_id, at=at,
                                 item_in_scope=item_in_scope)
                children = ()
            elif op in QUANTIFIER_OPERATORS:
                children = ((node["array"], at+"/array", item_in_scope, depth+1),
                            (node["where"], at+"/where", True, depth+1))
            elif op in UNARY_OPERATORS:
                children = ((node["arg"], at+"/arg", item_in_scope, depth+1),)
            else:
                args = node["args"]
                if type(args) is not list:
                    raise SrxError("arguments_array_required", rule_id=rule_id, pointer=at+"/args",
                                   expected="array of expressions", actual=json_type(args))
                if op in BINARY_OPERATORS and len(args) != 2:
                    raise SrxError("binary_arity", rule_id=rule_id, pointer=at+"/args",
                                   expected="exactly two expressions", actual="array")
                # Bind parent fields now, not later through a loop closure.
                children = _argument_children(args, at, item_in_scope, depth)
        counter.hold(node)
        work.append((iter(children), id(node)))
    return counter.observation()


def _argument_children(args, at, item_in_scope, depth):
    for index, arg in enumerate(args):
        yield arg, at+"/args/"+str(index), item_in_scope, depth+1


def _validate_context(data, rule_id):
    _exact_fields(data, CONTEXT_NAMES, rule_id=rule_id, pointer="", subject="context")
    for name in ("artifact", "project"):
        if type(data[name]) is not dict:
            raise SrxError("context_object_required", rule_id=rule_id, pointer="/"+name,
                           expected="object", actual=json_type(data[name]), subject="context")
    if type(data["relations"]) not in (dict, list):
        raise SrxError("relations_view_required", rule_id=rule_id, pointer="/relations",
                       expected="object or array", actual=json_type(data["relations"]), subject="context")
    configuration = data["configuration"]
    if configuration is not None:
        _exact_fields(configuration, ("configuration_id", "effective_values"),
                      rule_id=rule_id, pointer="/configuration", subject="context")
        if type(configuration["configuration_id"]) is not str or not configuration["configuration_id"].strip():
            raise SrxError("configuration_id_required", rule_id=rule_id,
                           pointer="/configuration/configuration_id", expected="nonempty string",
                           actual=json_type(configuration["configuration_id"]), subject="context")
        if type(configuration["effective_values"]) is not dict:
            raise SrxError("effective_values_required", rule_id=rule_id,
                           pointer="/configuration/effective_values", expected="object",
                           actual=json_type(configuration["effective_values"]), subject="context")


