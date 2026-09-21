"""Private SRX components; no host or project execution."""

from .errors import SrxError
from ._json_values import json_type

LANGUAGE = "srx"
VERSION = "1.0"
SUPPORTED_OPERATORS = ("literal", "field", "exists")
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
    if set(value) != set(names):
        raise SrxError("invalid_fields", rule_id=rule_id, pointer=pointer,
                       expected="closed object", actual="object", subject=subject)


def _validate_document(data, rule_id):
    _exact_fields(data, ("language", "version", "expression"), rule_id=rule_id, pointer="")
    if data["language"] != LANGUAGE:
        raise SrxError("unsupported_language", rule_id=rule_id, pointer="/language",
                       expected="srx", actual=json_type(data["language"]))
    if data["version"] != VERSION:
        raise SrxError("unsupported_version", rule_id=rule_id, pointer="/version",
                       expected="1.0", actual=json_type(data["version"]))
    _validate_expression(data["expression"], rule_id)


def _validate_expression(expression, rule_id):
    from .fields import parse_pointer
    work = [(expression, "/expression")]
    while work:
        node, at = work.pop()
        if type(node) is not dict:
            raise SrxError("object_required", rule_id=rule_id, pointer=at,
                           expected="expression object", actual=json_type(node))
        op = node.get("op")
        if type(op) is not str or op not in SUPPORTED_OPERATORS:
            raise SrxError("unsupported_operator", rule_id=rule_id, pointer=at+"/op",
                           expected="supported operator", actual=json_type(op))
        if op == "literal":
            _exact_fields(node, ("op", "value"), rule_id=rule_id, pointer=at)
        elif op == "field":
            _exact_fields(node, ("op", "context", "pointer"), rule_id=rule_id, pointer=at)
            if type(node["context"]) is not str or node["context"] not in CONTEXT_NAMES:
                raise SrxError("unknown_context", rule_id=rule_id, pointer=at+"/context",
                               expected="explicit named context root", actual=json_type(node["context"]))
            parse_pointer(node["pointer"], rule_id=rule_id, at=at+"/pointer")
        else:
            _exact_fields(node, ("op", "arg"), rule_id=rule_id, pointer=at)
            work.append((node["arg"], at+"/arg"))


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


