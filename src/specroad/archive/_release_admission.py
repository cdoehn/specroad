"""One native Readiness adapter for Baseline observation and publication.

Construction is inert so durable receipt replay can precede current admission.
Every assessment binds actual inputs and runs M13 again; no success is cached.
"""
from dataclasses import dataclass

from ..model.errors import ModelError


@dataclass(frozen=True)
class _ReleaseAdmission:
    model: object
    release_id: str
    context: object
    _gates: tuple
    reviews: tuple
    verifier: object

    def assess(self):
        from ..planning.readiness import ReleaseReadinessContext, assess_release_readiness
        if type(self.context) is not ReleaseReadinessContext:
            raise ModelError('typed_release_readiness_context_required')
        owned = self.model.snapshot()
        current = self.context._model.snapshot()
        binding = self.context.data['binding']
        if (owned._sources_sha256 != current._sources_sha256 or owned.binding != current.binding
                or binding['release_id'] != self.release_id):
            raise ModelError('release_baseline_readiness_binding_mismatch')
        return assess_release_readiness(self.context, gates=self._gates,
            blocker_reviews=self.reviews, blocker_verifier=self.verifier)

    def require_ready(self):
        if self.context is None:
            raise ModelError('release_baseline_readiness_required')
        fresh = self.assess()
        if not fresh.data['ready'] or fresh.data['provisional']:
            raise ModelError('release_baseline_readiness_required')
        return fresh
