"""Resource budgets, distinct from any active Codex turn duration."""
import json
from .errors import ControlError

MAX_LINE = 2 * 1024 * 1024
MAX_RESPONSE = 32 * 1024 * 1024
MAX_LOG = 64 * 1024 * 1024
MAX_PENDING_BYTES = 8 * 1024 * 1024
MAX_HISTORY_BYTES = 32 * 1024 * 1024
MAX_TURN_PAGES = 20
TURN_PAGE_SIZE = 50
MAX_TURN_ITEMS = 4096
MAX_ITEM_PAGES = 128
ITEM_PAGE_SIZE = 50
MAX_CURSOR_BYTES = 8192


def json_size(value):
    try:
        return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ControlError("codex_turn_history_invalid", "Invalid structured Codex evidence.") from None
