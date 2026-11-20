"""Pure fixed-decimal values with no reliance on ambient Decimal state."""
from decimal import Context, Decimal, ROUND_HALF_EVEN
import math
import re

from ._values import require


SCALE = 10 ** 12


QUANTUM = Decimal('0.000000000001')


def format_units(value):
    return f'{value // SCALE}.{value % SCALE:012d}'


def score_units(value):
    require(type(value) in (int, float) and 0 <= value <= 1 and math.isfinite(value),
            'invalid_backend_output', exit_code=5)
    # Supply every context field: neither getcontext() nor DefaultContext may
    # alter the published decimal, its tie-breaking, or a decision boundary.
    context = Context(prec=32, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
                      capitals=1, clamp=0, flags=[], traps=[])
    quantized = context.quantize(Decimal(str(value)), QUANTUM)
    return int(format(quantized, '.12f').replace('.', ''))


def parse_threshold(value, name):
    require(type(value) is str and re.fullmatch(
        r'[+-]?(?:[0-9]+(?:\.[0-9]{0,12})?|\.[0-9]{1,12})', value) is not None,
        'analyzer_' + name, exit_code=2)
    decimal = Decimal(value)
    require(0 <= decimal <= 1, 'analyzer_' + name, exit_code=2)
    # A valid threshold is already exact at twelve places; no context arithmetic.
    return int(format(decimal, '.12f').replace('.', ''))


def normalized_total_is_valid(ranked):
    """Check consistency with the pinned backend's binary32 normalization.

    Its 142 columns include two disjoint alias pairs (sr and uz). Positive
    reduction, division and at most one alias fold per output give a relative
    bound gamma_143 = 143 / (2**24 - 143). Add half a decimal unit per row
    and one unit covering binary32 subnormal rounding. This is an arithmetic
    error bound, not a confidence tolerance; the published scores never change.
    """
    rounds = 143
    denominator = (1 << 24) - rounds
    error = abs(sum(score for _, score in ranked) - SCALE)
    return 2 * error * denominator <= (
        2 * SCALE * rounds + (len(ranked) + 2) * denominator)
