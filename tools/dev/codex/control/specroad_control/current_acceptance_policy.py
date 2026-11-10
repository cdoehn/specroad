"""Pure operator selection and typed reset capability, shared by receipt checks."""
from .errors import ControlError
from .job_contract import new_contract
from .local import decode_object

RESET_PATH = 'verification/current_acceptance_reset.json'
RESET_CAPABILITY = {'format_version': 1, 'decision_contract_version': 4,
    'authorization_mode': 'explicit_current', 'budget_policy': 'explicit_operator_reset',
    'clarification_limit': 3, 'receipt_version': 2, 'history_policy': 'preserve'}



def selection(previous, output_kind, clarification, mode, *, reset_budget=False):
    if type(reset_budget) is not bool or (reset_budget and (clarification is not True or previous['version'] != 4)):
        raise ValueError('An explicit V4 operator reset requires clarification authority')
    # A published clarification may not yet have reached inherit_contract.
    # Charge it once when archiving that source, never silently restore it.
    debit = int(mode == 'successor' and (output_kind == 'spec_clarification'
        or output_kind == 'patch_ready_with_clarification' and not previous.get('clarification_continuation')))
    remaining = previous['clarifications_remaining'] - debit
    if remaining < 0 or clarification and remaining == 0 and not reset_budget:
        raise ValueError('No unspent clarification budget')
    return new_contract(3 if reset_budget else remaining, version=4,
        allowed=clarification or mode == 'same_ready' and previous['clarification_allowed'])



def require_reset_marker(raw):
    marker = decode_object(raw)
    if (len(raw) > 4096 or set(marker) != set(RESET_CAPABILITY)
            or any(type(marker[k]) is not type(v) or marker[k] != v for k, v in RESET_CAPABILITY.items())):
        raise ControlError('current_acceptance_rejected', 'The tested current Result must opt into an explicit operator budget reset.')
