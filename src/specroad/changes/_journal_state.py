"""The building-state invariant, not an executable prepared/commit transition."""
from .journal_values import JournalError
STATES = ('building', 'prepared', 'committing', 'committed', 'rolling_back', 'rolled_back', 'corrupt')


def require_building(state, published_count):
    if state not in STATES:
        raise JournalError('invalid_journal_state')
    if state != 'building':
        raise JournalError('journal_state_not_supported_by_building_codec')
    if type(published_count) is not int or published_count != 0:
        raise JournalError('building_has_publications')
