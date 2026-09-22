"""Original profile bytes and detached values; no CLI or project selection."""
from dataclasses import dataclass
from hashlib import sha256
from ._contract import PROFILE_FORMAT, _fail, _validate_profile
from ..model.canonical import canonical_json_sha256
from ..storage.json_syntax import parse_json_object
from ..graph.relation_obligations import MinimumRelationRule

@dataclass(frozen=True, init=False)
class ProfileResource:
    """Own original bytes and canonical content identity, not trusted authorship."""
    source_bytes: bytes
    profile_id: str
    version: str
    sha256: str
    source_sha256: str

    def __init__(self, raw):
        if type(raw) is not bytes:
            _fail("profile_bytes_required")
        value = parse_json_object(raw)
        _validate_profile(value)
        object.__setattr__(self, "source_bytes", raw)
        object.__setattr__(self, "profile_id", value["profile_id"])
        object.__setattr__(self, "version", value["version"])
        object.__setattr__(self, "sha256", canonical_json_sha256(value))
        object.__setattr__(self, "source_sha256", sha256(raw).hexdigest())

    @property
    def key(self):
        return self.profile_id + "@" + self.version

    @property
    def data(self):
        return parse_json_object(self.source_bytes)

    def binding(self):
        return {"profile_id": self.profile_id, "version": self.version,
                "sha256": self.sha256, "hash_algorithm": "jcs-sha256",
                "profile_format_version": PROFILE_FORMAT}

    def rules(self, family):
        if type(family) is not str or family not in ("relation_rules", "lint_rules"):
            _fail("profile_rule_family_required")
        return tuple({"rule_id": r["rule_id"], "version": r["version"],
                      "sha256": canonical_json_sha256(r), "definition": r}
                     for r in self.data[family])

    def minimum_relation_rules(self):
        return tuple(MinimumRelationRule(**{k:v for k,v in r.items() if k != "version"})
                     for r in self.data["relation_rules"])
