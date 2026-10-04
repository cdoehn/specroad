"""Project-free capabilities of the current distribution and active registry.

The semantic payload is deterministic. Host observations never join it, and
an existing serializer is not mistaken for a format accepted by a command.
The ``python.`` and ``cli.`` capability namespaces distinguish public library
support from executable registry commands. Model/SRX versions describe the
existing Core validators/evaluator, not the presence of a command or a schema ID.
"""

from .._metadata import PYTHON_CAPABILITY_IDS, SUPPORTED_SRX_VERSIONS
from .results import FORMAT_VERSION
from .self_description import (DESCRIPTION_VERSION, command_surface,
                               output_formats, published_contract)

CAPABILITIES_VERSION = "1.0.0"


def capabilities(registry):
    from ..runtime.identity import version_info
    from ..runtime.limits import current_limits
    identity = version_info()
    commands = []
    active_formats = set()
    for command in sorted(registry.commands, key=lambda item: item.command_id):
        command, protocol = published_contract(registry, command.command_id)
        formats = output_formats(command)
        active_formats.update(formats)
        commands.append({**command_surface(command),
            "output_formats": formats, "result_schema": protocol.result_schema,
            "continuation_supported": protocol.work.continuation_supported})
    semantic = {
        "program_version": identity["program_version"],
        "distribution": {key: identity[key] for key in ("distribution_kind", "build_id", "build_sha256", "build_hash_scope")},
        "capability_ids": sorted(["cli." + cmd["command_id"] for cmd in commands] +
                                 list(PYTHON_CAPABILITY_IDS)),
        "commands": commands,
        "command_groups": sorted({cmd["command_id"].split(".")[0] for cmd in commands}),
        "command_classes": sorted({cmd["command_class"] for cmd in commands}),
        "output_formats": sorted(active_formats),
        "exchange_formats": [],
        "supported_versions": {"schema": identity["supported_schema_versions"],
            "srx": list(SUPPORTED_SRX_VERSIONS), "proposal": [],
            "json_envelope": [FORMAT_VERSION], "command_description": [DESCRIPTION_VERSION],
            "capabilities": [CAPABILITIES_VERSION]},
        "python_support": identity["python_support"],
        "work": {"engine_available": False, "checkpoint_algorithms": [], "budget_policy_version": None},
    }
    return {"format_version": CAPABILITIES_VERSION, "semantic": semantic,
            "runtime": {"interpreter": identity["runtime"],
                        "limits": current_limits()}}
