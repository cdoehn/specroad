"""Trusted distribution providers referring to the actual validator resources."""
from dataclasses import dataclass
from types import MappingProxyType

from .artifact_types import artifact_types
from .artifact_schemas import artifact_common_schema
from .domain_schemas import DOMAIN_TYPES, domain_schema
from .record_schemas import RECORD_TYPES, record_schema
from .configuration_schema import SCHEMA_ID, configuration_json_schema
from .versions import SCHEMA_VERSION, PROJECT_SCHEMA_VERSIONS, PLAN_SCHEMA_VERSION, PLAN_TYPES
from .schema_identity import (RESULT_IDS, CHANGE_PLAN_FAMILY, CHANGE_PLAN_ID,
                              CHANGE_PLAN_VERSION, identity_metadata)


@dataclass(frozen=True)
class SchemaProvider:
    category: str
    version: str
    family: str
    key: object


def providers_for(registry):
    providers = {}
    for entry in artifact_types():
        providers[entry.schema_id] = SchemaProvider("artifact", entry.schema_version, "common", entry.artifact_type)
    for kind in DOMAIN_TYPES:
        providers["urn:specroad:schema:" + SCHEMA_VERSION + ":artifact-domain:" + kind] = SchemaProvider("artifact", SCHEMA_VERSION, "domain", kind)
    for kind in RECORD_TYPES:
        providers["urn:specroad:schema:" + SCHEMA_VERSION + ":artifact-record:" + kind] = SchemaProvider("artifact", SCHEMA_VERSION, "record", kind)
    for version in PROJECT_SCHEMA_VERSIONS:
        providers["urn:specroad:schema:" + version + ":project-configuration"] = SchemaProvider("configuration", version, "configuration", version)
    for kind in sorted(PLAN_TYPES):
        providers["urn:specroad:schema:" + PLAN_SCHEMA_VERSION + ":artifact-plan:" + kind] = SchemaProvider("artifact", PLAN_SCHEMA_VERSION, "plan", kind)
    providers[CHANGE_PLAN_ID] = SchemaProvider("exchange", CHANGE_PLAN_VERSION, CHANGE_PLAN_FAMILY, None)
    providers['urn:specroad:schema:1.3.0:change-plan'] = SchemaProvider('exchange', '1.3.0', CHANGE_PLAN_FAMILY, None)
    providers['urn:specroad:schema:1.4.0:change-plan'] = SchemaProvider('exchange', '1.4.0', CHANGE_PLAN_FAMILY, None)
    providers['urn:specroad:schema:1.5.0:change-plan'] = SchemaProvider('exchange', '1.5.0', CHANGE_PLAN_FAMILY, None)
    for schema_id in RESULT_IDS:
        version, category, _ = identity_metadata(schema_id)
        providers[schema_id] = SchemaProvider(category, version, "result", schema_id)
    for command in registry.commands:
        schema_id = "urn:specroad:schema:1.0.0:request:" + command.command_id
        providers[schema_id] = SchemaProvider("request", "1.0.0", "request", command.command_id)
    return MappingProxyType(providers)


def provider_document(provider, registry):
    """Load one bounded trusted factory, without a directory scan or URL fetch."""
    family, key = provider.family, provider.key
    if family == "common":
        return artifact_common_schema(key)
    if family == "domain":
        return domain_schema(key)
    if family == "record":
        return record_schema(key)
    if family == "configuration":
        return configuration_json_schema(key)
    if family == "plan":
        from .plan_schemas import plan_schema
        return plan_schema(key)
    if family == CHANGE_PLAN_FAMILY:
        from ..changes.schema import change_plan_schema
        return change_plan_schema(version=provider.version)
    if family == "result":
        from ..cli.result_schemas import result_json_schema
        return result_json_schema(key)
    from ..cli.request_schema import request_schema
    return request_schema(registry.resolve(key))
