"""Stable Proposal change identities, independent of positions and display numbers."""
import secrets

from ..model.identity_tokens import decode128, encode128
from .values import ProposalError, require


def change_id(value):
    require(type(value) is str and value.startswith('CHG-'),
            'proposal_change_id_required', pointer='/change_id')
    decode128(value[4:])
    return value


def allocate_change_id(existing):
    """Reserve against the explicit sequence; no project read or publication."""
    used = frozenset(existing)
    while True:
        try:
            identity = 'CHG-' + encode128(secrets.token_bytes(16))
        except OSError as error:
            raise ProposalError('proposal_change_entropy_unavailable', exit_code=5) from error
        if identity not in used:
            return identity
