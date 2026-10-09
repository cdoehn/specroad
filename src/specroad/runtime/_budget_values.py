"""Internal values separating operational selection from semantic constraints."""
from dataclasses import dataclass

from .resource_profiles import profile_targets


@dataclass(frozen=True)
class RuntimeResourceOptions:
    """Validated profile selection and owned, ordered operational overrides."""
    profile: str
    source: str
    overrides: tuple[tuple[str, int, str], ...]

    def report(self):
        result = profile_targets(self.profile, source=self.source)
        for metric, value, origin in self.overrides:
            result['effective_budgets'][metric].update(value=value, origin=origin)
        return result


@dataclass(frozen=True)
class SemanticResourceConstraints:
    """Owned scope and safety projections, without runtime profile options."""
    scope: dict
    safety_or_format: dict

    def classes(self):
        return {'semantic_scope': self.scope,
                'hard_safety_or_format': self.safety_or_format}
