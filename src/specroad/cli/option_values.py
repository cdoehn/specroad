"""Pure normalized CLI/policy values and provenance, independent of file I/O.

Profile and variant engines supply already resolved OptionLayer objects. This
module never imports those engines and cannot activate optional analyzers.
"""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .contracts import CommandUsageError


CORE_PROFILE = "core@0.2.0"


class OptionResolutionError(CommandUsageError):
    def __init__(self, message: str, exit_code: int = 2, *, details=None):
        super().__init__(message)
        self.exit_code = exit_code
        self.details = details


@dataclass(frozen=True)
class OptionOrigin:
    source: str
    value: object


@dataclass(frozen=True)
class ResolvedOptions:
    project_root: Path | None
    project_source: str | None
    values: Mapping[str, object]
    history: Mapping[str, tuple[OptionOrigin, ...]]
    preflight: Mapping | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "history", MappingProxyType({key: tuple(value) for key, value in self.history.items()}))
        if self.preflight is not None:
            from .results import freeze
            object.__setattr__(self, "preflight", freeze(self.preflight))

    @property
    def origins(self) -> Mapping[str, str]:
        return MappingProxyType({key: changes[-1].source for key, changes in self.history.items()})


@dataclass(frozen=True)
class OptionLayer:
    """Already resolved policy values, supplied by a future profile/variant engine.

This adapter does not load, activate or validate the selected profile resources.
Unknown values are rejected rather than pretending their policy was applied.
"""
    label: str
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        _text(self.label, "layer label")
        if not isinstance(self.values, Mapping):
            raise OptionResolutionError("Layer values must be a mapping")
        checked = {}
        for name, value in self.values.items():
            if name != "fail_on":
                raise OptionResolutionError("Unsupported policy-layer value")
            checked[name] = _threshold(value)
        object.__setattr__(self, "values", MappingProxyType(checked))


def _text(value, name):
    if not isinstance(value, str) or not value or "\0" in value:
        raise OptionResolutionError("Invalid " + name)
    return value


def _profiles(value) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise OptionResolutionError("Profiles must be an ordered list")
    result = [CORE_PROFILE]
    for item in value:
        _text(item, "profile selector")
        if item in {"core", CORE_PROFILE}:
            continue
        if item.startswith("core@"):
            raise OptionResolutionError("The Core profile version is fixed by this distribution")
        result.append(item)
    return tuple(result)


def _threshold(value):
    if not isinstance(value, str) or value not in {"error", "warning"}:
        raise OptionResolutionError("Invalid failure threshold")
    return value


def _validate_layers(profile_layers, configuration_layer):
    if not isinstance(profile_layers, (tuple, list)) or not all(isinstance(layer, OptionLayer) for layer in profile_layers):
        raise OptionResolutionError("Invalid profile-policy layers")
    if configuration_layer is not None and not isinstance(configuration_layer, OptionLayer):
        raise OptionResolutionError("Invalid configuration-policy layer")


def _compose_values(project, explicit_options, profile_layers, configuration_layer):
    values = {"profiles": (CORE_PROFILE,), "configuration": None, "fail_on": "error",
              "strict": False, "core_lint_optional": False}
    history = {name: [OptionOrigin("default", value)] for name, value in values.items()}

    def assign(name, value, origin):
        values[name] = value
        history[name].append(OptionOrigin(origin, value))

    if "profiles" in project:
        assign("profiles", _profiles(project["profiles"]), "project")
    policy = project.get("validation_policy", {})
    if not isinstance(policy, dict):
        raise OptionResolutionError("validation_policy must be an object")
    if "fail_on" in policy:
        assign("fail_on", _threshold(policy["fail_on"]), "project")
    for layer in profile_layers:
        for name, value in layer.values.items():
            assign(name, value, "profile:" + layer.label)
    if configuration_layer is not None:
        for name, value in configuration_layer.values.items():
            assign(name, value, "configuration:" + configuration_layer.label)
    if "--profile" in explicit_options:
        assign("profiles", _profiles(explicit_options["--profile"]), "cli")
    if "--configuration" in explicit_options:
        assign("configuration", _text(explicit_options["--configuration"], "configuration selector"), "cli")
    if "--fail-on" in explicit_options:
        assign("fail_on", _threshold(explicit_options["--fail-on"]), "cli")
    if "--strict" in explicit_options:
        if explicit_options["--strict"] is not True:
            raise OptionResolutionError("strict must be a boolean flag")
        assign("strict", True, "cli")
        assign("fail_on", "warning", "cli:strict")
        assign("core_lint_optional", True, "cli:strict")
    return values, history


def policy_exit_code(severities, resolved: ResolvedOptions) -> int:
    """Assess only known diagnostics; strict never starts analysis or hides work."""
    threshold = _threshold(resolved.values["fail_on"])
    failed = False
    for severity in severities:
        if not isinstance(severity, str) or severity not in {"error", "warning", "info"}:
            raise OptionResolutionError("Unknown diagnostic severity")
        failed = failed or severity == "error" or (threshold == "warning" and severity == "warning")
    return 1 if failed else 0
