"""Explicit synthetic identity/history inputs; no completed import or approval."""
from specroad.exchange import ExternalIdentity
from support.relations import external

TIME = "2026-09-01T18:00:00.123Z"
MAPPING = "example:requirements@1.0.0"
LOCAL = {"statement": "local", "extra": [True, None, 1]}
SOURCE = {"statement": "external", "extra": [True, None, 1]}
PAYLOAD = b' {"statement": "external", "extra": [true, null, 1]}\n'


def history(**changes):
    arguments = dict(mapping_id=MAPPING, imported_projection=LOCAL,
                     source_projection=SOURCE, source_payload=PAYLOAD, imported_at=TIME)
    arguments.update(changes)
    return ExternalIdentity(external(external_revision="007",
        extensions={"vendor.opaque": {"original": [None, "e\u0301", "東京"]}})).with_import_history(**arguments)
