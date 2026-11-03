"""Installed project opt-in for the explicit successor authorization only."""
from .apply_reconcile_proof import member
from .local import decode_object
from .errors import ControlError

PATH = 'verification/clarification_authorization.json'
CAPABILITY = {'format_version': 1, 'decision_rule': 'SPECROAD-DECISION-1',
              'decision_contract_version': 4, 'authorization_mode': 'explicit_successor',
              'budget_policy': 'preserve'}


def require_support(result):
    raw = member(result, 'base/' + PATH)
    value = decode_object(raw)
    if (len(raw) > 4096 or set(value) != set(CAPABILITY)
            or any(type(value[k]) is not type(expected) or value[k] != expected for k, expected in CAPABILITY.items())):
        raise ControlError('clarification_authorization_rejected', 'The verified project does not opt into explicit successor authorization.')
