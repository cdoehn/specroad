"""Immutable composed values and failures; no selection or merge policy."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from .errors import ProfileError
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from ..graph.relation_obligations import MinimumRelationRule

COMPOSITION_VERSION = "profile-composition-v1"

class ProfileCompositionError(ProfileError):
    """A failed composition has no effective model or hash to continue with."""
    code = "SRV142"
    exit_code = 3

    def __init__(self, reason, *, pointer="", profiles=(), rule_id=None):
        super().__init__(reason, pointer=pointer)
        self.profiles = tuple(profiles)
        self.rule_id = rule_id

    def diagnostic(self):
        return {**super().diagnostic(), "code": self.code, "exit_code": self.exit_code,
                "severity": "error", "profiles": list(self.profiles), "rule_id": self.rule_id,
                "effective_profile_available": False}


def _error(reason, pointer="", profiles=(), rule_id=None):
    raise ProfileCompositionError(reason, pointer=pointer, profiles=profiles, rule_id=rule_id)


@dataclass(frozen=True, init=False)
class EffectiveProfile:
    """Own the entire materialized composition; never certify a model or author."""
    _encoded: bytes
    selection_source: str

    def __init__(self, *args, **kwargs):
        raise TypeError("Use compose_profiles with explicit resources")

    @classmethod
    def _create(cls, value, source):
        result = object.__new__(cls)
        object.__setattr__(result, "_encoded", canonical_json_bytes(value))
        object.__setattr__(result, "selection_source", source)
        return result

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def profile_chain(self):
        return tuple(p["profile_id"] + "@" + p["version"] for p in self.data["profiles"])

    def binding(self):
        return {"composition_version": COMPOSITION_VERSION, "sha256": self.sha256,
                "hash_algorithm": "jcs-sha256"}

    def minimum_relation_rules(self):
        return tuple(MinimumRelationRule(**{k: v for k, v in r.items() if k != "version"})
                     for r in self.data["merge"]["relation_rules"])

    def severity_for(self, rule_id, default):
        if type(rule_id) is not str or type(default) is not str or default not in ("error", "warning", "info"):
            _error("profile_severity_arguments_required")
        merged = self.data["merge"]
        chosen = merged["severity_overrides"].get(rule_id, default)
        levels = {"info": 0, "warning": 1, "error": 2}
        floor = merged["minimum_severities"].get(rule_id, "info")
        return max((chosen, floor), key=levels.get)



