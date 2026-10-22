"""Owned passive exchange resources; no external system or import is simulated."""
from specroad.mappings import ExchangeMapping, ExternalIdentityRegistry, select_mapping
from support.artifacts import artifact_bytes


def mapping_value(**changes):
    value = {"schema_version": "0.2.0", "mapping_format_version": "exchange-mapping-v1",
        "mapping_id": "example:requirements", "mapping_version": "1.0.0", "source_format": "reqif",
        "types": [{"external_type": "Requirement", "artifact_type": "requirement"}],
        "fields": [
            {"external_type": "Requirement", "external_field": "Text", "target_field": "statement", "value_map": None},
            {"external_type": "Requirement", "external_field": "Language", "target_field": "language", "value_map": None},
            {"external_type": "Requirement", "external_field": "Force", "target_field": "normative_force",
             "value_map": [{"external_value": "Mandatory", "target_value": "shall"}]},
            {"external_type": "Requirement", "external_field": "Extra", "target_field": "extensions", "value_map": None}],
        "relations": [{"external_type": "Derivation", "relation_type": "derived_from", "direction": "forward"}],
        "hierarchies": [{"external_type": "DocumentTree", "relation_type": "contains", "direction": "parent_to_child"}],
        "extensions": {"example.notes": {"url": "https://unused.invalid/mapping", "text": "passive"}}}
    value.update(changes)
    return value


def fields_value():
    return {"Text": "The device shall report errors.", "Language": "en", "Force": "Mandatory",
            "Extra": {"example.metadata": {"nullable": None, "values": [True, 1, "1"]}},
            "Unmapped": {"original": [None, "external data"]}}


def selected(value=None):
    resource = ExchangeMapping(artifact_bytes(mapping_value() if value is None else value))
    return select_mapping([resource], key=resource.key, expected_sha256=resource.sha256)


def entry_value(**changes):
    value = {"object_class": "type", "source_system": "supplier", "source_document": "document-a",
             "external_id": "same-id", "external_revision": None,
             "data": {"source": "file:///unused", "nested": [None, {"flag": True}]},
             "extensions": {"example.raw": "import os; os.system('never run')"}}
    value.update(changes)
    return value


def registry_value(mapping, **changes):
    value = {"schema_version": "0.2.0", "mapping_format_version": "external-identity-registry-v1",
        "mapping_id": "example:registry", "mapping_version": "1.0.0", "mapping": mapping.binding(),
        "entries": [entry_value(object_class=kind) for kind in ("type", "hierarchy", "relation", "metadata")],
        "extensions": {}}
    value.update(changes)
    return value


def registry(mapping, **changes):
    return ExternalIdentityRegistry(artifact_bytes(registry_value(mapping, **changes)))
