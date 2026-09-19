"""Explicit duration-bound comparison, not natural language understanding."""
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from .comparison_values import ComparisonResult


# Comparison of explicit upper/lower duration bounds is separate from text
# comparison. The caller's profile supplies bound semantics; none are guessed.
def _duration_seconds(value):
    from fractions import Fraction
    import re
    from ..model.requirement_duration import RequirementDuration
    duration = RequirementDuration(value)
    data = duration.data
    if type(data) is dict:
        units = {'s': Fraction(1), 'ms': Fraction(1, 1000), 'us': Fraction(1, 10**6),
                 'ns': Fraction(1, 10**9), 'min': Fraction(60), 'h': Fraction(3600),
                 'd': Fraction(86400), 'wk': Fraction(604800)}
        factor = units.get(data['unit'])
        return None if factor is None else Fraction(str(data['value'])) * factor
    # Time-only designators have fixed units. Calendar/day/week context is
    # intentionally not guessed from ISO dates, timezones or locale.
    match = re.fullmatch(r'PT(?:(\d+(?:[.,]\d+)?)H)?(?:(\d+(?:[.,]\d+)?)M)?(?:(\d+(?:[.,]\d+)?)S)?', data)
    if match is None:
        return None
    return sum((Fraction(part.replace(',', '.')) * factor
                for part, factor in zip(match.groups(), (3600, 60, 1)) if part is not None), Fraction(0))


def compare_duration_bounds(before, after, *, bound):
    """Only explicit duration values AND an explicit bound direction justify this.

    This is not installed as a heuristic in field_diff. Calendar durations and
    unsupported unit conversions remain timing_changed, with no order claim.
    """
    if type(bound) is not str or bound not in ('maximum', 'minimum'):
        raise ModelError('explicit_timing_bound_required')
    left, right = _duration_seconds(before), _duration_seconds(after)
    changed = canonical_json_bytes(before) != canonical_json_bytes(after)
    comparable = left is not None and right is not None
    order = (right > left) - (right < left) if comparable else None
    if not changed:
        kind = 'unchanged'
    elif order == 0:
        kind = 'timing_equivalent'
    elif order is None:
        kind = 'timing_changed'
    else:
        tightened = (order < 0) if bound == 'maximum' else (order > 0)
        kind = 'timing_tightened' if tightened else 'timing_relaxed'
    return ComparisonResult({'comparison_version': 'duration-bound-diff-v1',
        'before': before, 'after': after, 'bound': bound, 'category': kind,
        'value_changed': changed, 'comparable': comparable, 'order': order,
        'interpretation': 'explicit_caller_bound', 'write_authorized': False})
