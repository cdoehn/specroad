"""Exact decimal roundtrip boundary, not an arithmetic or JCS writer engine."""

from decimal import Decimal, DecimalException
import math

from .errors import ModelError


def number_from_token(token, *, pointer=""):
    """Reject input precision that Python's binary64 conversion would discard.

    Compare decimal spellings, not the full binary expansion of values such as
    0.1. No ambient Decimal arithmetic context is used or modified. Integers
    retain their JSON integer type after the same decimal roundtrip check.
    """
    try:
        decimal = Decimal(token)
        number = float(token)
        if not decimal.is_finite() or not math.isfinite(number):
            raise ModelError("nonfinite_number", pointer=pointer)
        if Decimal(str(number)) != decimal:
            raise ModelError("number_roundtrip_loss", pointer=pointer)
        return number if any(marker in token for marker in ".eE") else int(token)
    except ModelError:
        raise
    except (ValueError, OverflowError, DecimalException) as error:
        raise ModelError("unsupported_number", pointer=pointer) from error
