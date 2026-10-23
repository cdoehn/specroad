"""Explicit synthetic artifact candidates; no external parser or import receipt."""
from specroad.exchange import ExternalIdentity, prepare_import_plan
from specroad.mappings import ExchangeMapping
from specroad.model.canonical import canonical_json_bytes
from support.exchange_mappings import mapping_value
from support.folds import goal
from support.targets import ACTOR, TIME, POLICY, SCOPE

BASE = "Initial supplier goal."
EXTERNAL = "Updated supplier goal."
LOCAL = "Local author goal."
PAYLOAD = b"explicit supplier payload\r\n"


def mapping(**changes):
    return ExchangeMapping(canonical_json_bytes(mapping_value(
        types=[{"external_type": "Goal", "artifact_type": "goal"}],
        fields=[{"external_type": "Goal", "external_field": "Text", "target_field": "statement", "value_map": None}],
        relations=[], hierarchies=[], **changes)))


def identity(key="external-1", **changes):
    return {"source_system": "supplier", "source_document": "explicit-document",
            "external_id": key, "external_revision": "1", **changes}


def candidate(text=EXTERNAL, *, number=0, new=False, key="external-1"):
    template = goal(number, created_at=TIME, updated_at=TIME, created_by=ACTOR, updated_by=ACTOR)
    return {"identity": identity(key), "external_type": "Goal", "fields": {"Text": text},
            "new_artifact": template if new else None}


def imported(*, local=BASE, source=BASE, number=0, key="external-1", **changes):
    history = ExternalIdentity(identity(key)).with_import_history(mapping_id=mapping().key,
        imported_projection={"artifact_type": "goal", "statement": BASE},
        source_projection={"artifact_type": "goal", "statement": source},
        source_payload=b"previous input", imported_at="2026-01-01T00:00:00Z")
    return goal(number, statement=local, external_identities=[history.data], **changes)


def prepare(model, candidates, *, resource=None, **changes):
    resource = resource or mapping()
    args = dict(input_format="reqif", input_bytes=PAYLOAD, mapping_resources=[resource],
        mapping_key=resource.key, mapping_sha256=resource.sha256, strategy="update_if_unchanged",
        change_plan_id="CP-import-explicit", request_id="import-request-explicit", actor=ACTOR,
        planned_at=TIME, scope_descriptor=SCOPE, metadata_policy_version="change-metadata-v1", policy=POLICY)
    args.update(changes)
    return prepare_import_plan(model, candidates, **args)
