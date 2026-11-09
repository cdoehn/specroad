"""Small machine-readable journal records; never emit prompts or tool output."""
import json
import math
import sys
import re
import time

FIELDS = {"source_sha256", "turn_id", "thread_status", "turn_status", "codex_error",
          "codex_will_retry", "decision", "reason", "retry_attempt", "retry_at", "retry_mode",
          "event_limit", "queued_events", "rpc_method", "rpc_code", "limit_bytes", "announced_bytes", "wait_seconds", "error", "transport", "retry_blocked_reason", "overload_check_at"}


def record(event, **values):
    result = {"event": event, "timestamp": time.time()}
    for key, value in values.items():
        if key not in FIELDS:
            continue
        if value is None or type(value) in (bool, int):
            result[key] = value
        elif type(value) is float and math.isfinite(value):
            result[key] = value
        elif isinstance(value, str):
            # Only identifiers and our own fixed error codes, not server prose.
            result[key] = re.sub(r"[^a-zA-Z0-9_.:/-]", "_", value)[:160]
    if values.get("codex_error") == "serverOverloaded":
        result["message"] = "Selected model is at capacity"
    print(json.dumps(result, allow_nan=False), file=sys.stderr, flush=True)
    return result
