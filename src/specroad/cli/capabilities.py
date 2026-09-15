"""Project-free capabilities of the current distribution and active registry.

The semantic payload is deterministic. Host observations never join it, and
an existing serializer is not mistaken for a format accepted by a command.
"""

from .results import FORMAT_VERSION
from .self_description import DESCRIPTION_VERSION, describe_command

CAPABILITIES_VERSION = "1.0.0"


def capabilities(registry):
    from ..runtime.identity import version_info
    identity = version_info()
    commands = []
    output_formats = set()
    for command in sorted(registry.commands, key=lambda item: item.command_id):
        descriptor = describe_command(registry, command.command_id)
        formats = descriptor["stdout"]["formats"]
        output_formats.update(formats)
        commands.append({"command_id": command.command_id, "words": list(command.words),
            "aliases": [list(route) for route in sorted(command.aliases)],
            "command_class": command.command_class.value,
            "preflight_profile": command.preflight_profile.value,
            "output_formats": formats, "result_schema": command.protocol.result_schema,
            "continuation_supported": command.protocol.work.continuation_supported})
    semantic = {
        "program_version": identity["program_version"],
        "distribution": {key: identity[key] for key in ("distribution_kind", "build_id", "build_sha256", "build_hash_scope")},
        "capability_ids": sorted(["cli." + cmd["command_id"] for cmd in commands] + ["python.structured-request"]),
        "commands": commands,
        "command_groups": sorted({cmd["command_id"].split(".")[0] for cmd in commands}),
        "command_classes": sorted({cmd["command_class"] for cmd in commands}),
        "output_formats": sorted(output_formats),
        "exchange_formats": [],
        "supported_versions": {"schema": identity["supported_schema_versions"], "srx": [], "proposal": [],
            "json_envelope": [FORMAT_VERSION], "command_description": [DESCRIPTION_VERSION],
            "capabilities": [CAPABILITIES_VERSION]},
        "python_support": identity["python_support"],
        "work": {"engine_available": False, "checkpoint_algorithms": [], "budget_policy_version": None},
    }
    return {"format_version": CAPABILITIES_VERSION, "semantic": semantic,
            "runtime": {"interpreter": identity["runtime"],
                        "limits": {"process_address_space_bytes": None, "process_cpu_seconds": None,
                                   "host_memory_bytes": None, "host_cpu_quota": None,
                                   "status": "not_probed"}}}
