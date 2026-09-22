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
