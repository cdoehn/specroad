"""Exact numeric decision fixtures from specification Appendix U.3."""
from pathlib import Path
import json
from .srx import roots, binary, literal, run


def vectors():
    return json.loads((Path(__file__).resolve().parents[1]/'fixtures/srx_numeric_v1.json').read_text(encoding='utf-8'))['vectors']


def calculate(op, left, right, precision=34):
    context=roots()
    context['project']['srx_policy']={'numeric_policy_version':'srx-decimal-v1','decimal_precision':precision}
    return run(binary(op,literal(left),literal(right)),context=context)


# Shared hostile process-default fixture; all caller state is restored.
from contextlib import contextmanager
from decimal import (Context, DefaultContext, ROUND_UP, ROUND_FLOOR, Inexact,
                     localcontext)

def context_state(c):
    return (c.prec, c.rounding, c.Emin, c.Emax, c.capitals, c.clamp,
            dict(c.traps), dict(c.flags))


@contextmanager
def changed_defaults():
    saved=DefaultContext.copy()
    try:
        DefaultContext.prec=1;DefaultContext.rounding=ROUND_UP
        DefaultContext.Emin=-1;DefaultContext.Emax=1
        DefaultContext.traps[Inexact]=True
        DefaultContext.flags[Inexact]=True
        with localcontext(Context(prec=1,rounding=ROUND_FLOOR,Emin=-1,Emax=1)) as current:
            current.traps[Inexact]=True;current.flags[Inexact]=True
            yield current
    finally:
        for field_name in ('prec','rounding','Emin','Emax','capitals','clamp'):
            setattr(DefaultContext,field_name,getattr(saved,field_name))
        DefaultContext.traps.update(saved.traps);DefaultContext.flags.update(saved.flags)


