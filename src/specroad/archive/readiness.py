"""Read-only Release-Baseline admission through the native M13 provider.

Stored policy bytes are observations, not evaluated Evidence or release approval.
No caller callback, success label or prepared snapshot opens publication here.
"""
from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object


class ReleaseBaselineSelectionConflict(ModelError):
    """An external selection cannot replace the Release's stored selection."""
    exit_code = 6


@dataclass(frozen=True, init=False)
class ReleaseBaselineReadiness:
    """Owned observation; admission rechecks native services, never its flags."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_release_baseline_readiness with actual model bytes')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    def require_ready(self):
        # Detached/forged report bytes cannot replace the actual native inputs.
        if getattr(self, '_context', None) is None:
            raise ModelError('release_baseline_readiness_required')
        fresh = _native_readiness(self._context._model, self.data['release_id'],
            self._context, self._gates, self._reviews, self._verifier)
        if not fresh.data['ready'] or fresh.data['provisional']:
            raise ModelError('release_baseline_readiness_required')
        return fresh

    def __bool__(self):
        raise TypeError('Readiness observations are not release authority')


def _native_readiness(model, release_id, context, gates, reviews, verifier):
    from ..planning.readiness import ReleaseReadinessContext, assess_release_readiness
    if type(context) is not ReleaseReadinessContext:
        raise ModelError('typed_release_readiness_context_required')
    owned = model.snapshot()
    current = context._model.snapshot()
    binding = context.data['binding']
    if (owned._sources_sha256 != current._sources_sha256 or owned.binding != current.binding
            or binding['release_id'] != release_id):
        raise ModelError('release_baseline_readiness_binding_mismatch')
    return assess_release_readiness(context, gates=gates,
        blocker_reviews=reviews, blocker_verifier=verifier)


def assess_release_baseline_readiness(model, *, release_id, evaluation=None,
        readiness_context=None, gates=(), blocker_reviews=(), blocker_verifier=None):
    """Use actual stored selection and all eight gates on one owned input.

    Without explicit native context/services the established unavailable result
    stays closed. No report, callback or success flag substitutes for M13.
    """
    from ._release_selection import bind_stored_release_selection
    selection = bind_stored_release_selection(model, release_id=release_id, evaluation=evaluation)
    value = {'format_version': 'release-baseline-readiness-v1', 'baseline_kind': 'release',
        **selection,
        'readiness_provider_available': False, 'readiness_evaluated': False,
        'stored_evaluation_validated': False, 'ready': False,
        'blockers': ([] if selection['stored_evaluation_present'] else ['stored_release_evaluation_required'])
                    + ['release_readiness_provider_unavailable'],
        'validation_scope': 'stored_release_fields_and_unevaluated_policy_binding',
        'full_validation_passed': False, 'write_authorized': False, 'release_authorized': False}
    if readiness_context is not None:
        # Own caller collections; the native services own their input values.
        from ..planning.release_blockers import blocker_review_inputs
        if type(gates) not in (tuple, list):
            raise ModelError('release_readiness_native_gates_required')
        gates = tuple(gates)
        indexed, _ = blocker_review_inputs(blocker_reviews, blocker_verifier)
        reviews = tuple(indexed[key] for key in sorted(indexed))
        native = _native_readiness(model, release_id, readiness_context,
                                   gates, reviews, blocker_verifier)
        data = native.data
        eligible = selection['stored_evaluation_present'] and data['ready'] and not data['provisional']
        value.update(readiness_provider_available=True, readiness_evaluated=True,
            stored_evaluation_validated=selection['stored_evaluation_present'], ready=eligible,
            provisional=data['provisional'], readiness=data,
            blockers=[] if eligible else ['release_baseline_readiness_required'],
            validation_scope='native_release_readiness_and_stored_selection')
    result = object.__new__(ReleaseBaselineReadiness)
    object.__setattr__(result, '_encoded', canonical_json_bytes(value))
    object.__setattr__(result, '_context', readiness_context)
    if readiness_context is not None:
        object.__setattr__(result, '_gates', tuple(gates))
        object.__setattr__(result, '_reviews', tuple(reviews))
        object.__setattr__(result, '_verifier', blocker_verifier)
    return result
