"""Current editable Core resource schema version; historical versions stay separate."""

from .._metadata import MODEL_SCHEMA_VERSION as SCHEMA_VERSION

# Capability versions are independent of existing artifact original formats.
PLAN_SCHEMA_VERSION = "0.3.0"
PROJECT_SCHEMA_VERSIONS = (SCHEMA_VERSION, PLAN_SCHEMA_VERSION)
PLAN_TYPES = frozenset({"implementation_plan", "plan_entry"})
