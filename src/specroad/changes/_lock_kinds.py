"""Fixed command-to-lock-kind registry; independent of owner liveness."""
from enum import Enum

class LockKind(str, Enum):
    WRITER = 'writer'
    RECOVERY = 'recovery'
    OPERATIONAL = 'operational'


COMMANDS = {
    LockKind.WRITER: frozenset(('change apply', 'format', 'artifact create', 'artifact update',
        'relation add', 'relation remove', 'relation review', 'lifecycle transition',
        'document create', 'section add', 'section move', 'section remove',
        'block add', 'block update', 'block remove', 'view create', 'evidence record',
        'evidence import', 'baseline create', 'proposal create', 'proposal change',
        'proposal review start', 'proposal review', 'proposal apply', 'import apply',
        'migrate apply', 'merge apply')),
    LockKind.RECOVERY: frozenset(('recover run', 'recover discard', 'recover restore')),
    LockKind.OPERATIONAL: frozenset(('lock recover',)),
}

