"""Fixed trusted operation registry: data cannot register, import or call code.

Only the providers listed here exist. Registry entries are immutable and the
public helpers never accept a caller-supplied adapter or writable registry.
"""
from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType
from ..model._schema import validate_builtin
from .errors import ChangePlanError
from ._common import _at, _text, _reference, _generic
from . import _operation_schemas as schemas
from . import _operation_adapters as adapters

@dataclass(frozen=True)
class OperationContract:
    schema_factory: Callable[[], dict]
    validate_payload: Callable[[dict, str], None]
    result_owners: Callable[[dict], tuple[str, ...]]
    workflow: str = "regular"


def _create_owner(value):
    return (value["result_id"],)


def _evidence_owner(value):
    return (value["evidence"]["id"],)


def _review_owners(value):
    return (value["record"]["id"], *(item["target"] for item in value["approval_withdrawals"]))


def _no_owner(value):
    return ()


def _source_owner(value):
    return (value["source"],)


def _target_owner(value):
    return (value["target"],)


_CONTRACTS = MappingProxyType({
    "create": OperationContract(schemas.create_schema, adapters.validate_create, _create_owner, "regular"),
    "update": OperationContract(schemas.update_schema, adapters.validate_update, _target_owner, "regular"),
    "relation_add": OperationContract(schemas.relation_add_schema, adapters.validate_relation_add, _source_owner, "regular"),
    "relation_remove": OperationContract(schemas.relation_remove_schema, adapters.validate_relation_remove, _source_owner, "regular"),
    "transition": OperationContract(schemas.transition_schema, adapters.validate_transition, _target_owner, "regular"),
    "retire": OperationContract(schemas.retire_schema, adapters.validate_retire, _target_owner, "regular"),
    "evidence_record": OperationContract(schemas.evidence_record_schema, adapters.validate_evidence_record, _evidence_owner, "evidence_record"),
    "attachment_add": OperationContract(schemas.attachment_add_schema, adapters.validate_attachment_add, _target_owner, "regular"),
    "attachment_remove": OperationContract(schemas.attachment_remove_schema, adapters.validate_attachment_remove, _target_owner, "regular"),
    "representation_normalize": OperationContract(schemas.representation_normalize_schema, adapters.validate_representation_normalize, _no_owner, "representation_normalize"),
    "relation_review_record": OperationContract(schemas.relation_review_record_schema, adapters.validate_relation_review_record, _review_owners, "relation_review_record"),
    "proposal_control": OperationContract(schemas.proposal_control_schema, adapters.validate_proposal_control, _target_owner, "proposal_control"),
})
OPERATION_TYPES = tuple(_CONTRACTS)


def operation_schema(kind):
    if type(kind) is not str or kind not in _CONTRACTS:
        raise ValueError("Unknown compiled operation kind")
    return _CONTRACTS[kind].schema_factory()


def validate_operation(value, pointer=""):
    if type(value) is not dict or type(value.get("op")) is not str or value["op"] not in _CONTRACTS:
        raise ChangePlanError("unknown_operation", pointer=pointer + "/op")
    kind = value["op"]
    contract = _CONTRACTS[kind]
    _at(pointer, validate_builtin, value, contract.schema_factory())
    if "reason" in value:
        _text(value["reason"], pointer + "/reason")
    for name in ("source", "target"):
        if name in value:
            identity = _reference(value[name], pointer + "/" + name)
            if (name == "source" and kind.startswith("relation_") and kind != "relation_review_record"
                    or name == "target" and kind in ("update", "transition", "retire", "attachment_add", "attachment_remove")):
                _generic(identity, pointer + "/" + name)
    contract.validate_payload(value, pointer)
    return value


def result_owners(value):
    """Use only a previously validated payload; no execution/folding implied."""
    return _CONTRACTS[value["op"]].result_owners(value)


def required_workflow(kind):
    """Return a routing label, never an authentication or authority token."""
    return _CONTRACTS[kind].workflow
