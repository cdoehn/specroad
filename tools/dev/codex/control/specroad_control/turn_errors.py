"""Codex failure classification; no I/O, retries, or model invocation."""
def error_code(error):
    if not isinstance(error, dict):
        return None
    value = error.get("codexErrorInfo")
    if isinstance(value, str):
        return value if value.isascii() and value.isalnum() and len(value) <= 80 else "other"
    if isinstance(value, dict) and len(value) == 1:
        key = next(iter(value))
        return key if key.isascii() and key.isalnum() and len(key) <= 80 else "other"
    return None


def failure_details(turn, notification=None):
    notification = notification if isinstance(notification, dict) else {}
    if turn.get("status") == "completed" and not turn.get("error"):
        return {"turn_status": "completed", "codex_error": None, "codex_will_retry": None}
    if error_code(turn.get("error")) and error_code(notification.get("error")) and error_code(turn.get("error")) != error_code(notification.get("error")):
        return {"turn_status": turn.get("status"), "codex_error": "conflicting_error_codes", "codex_will_retry": None}
    return {"turn_status": turn.get("status"),
            "codex_error": error_code(turn.get("error")) or error_code(notification.get("error")),
            "codex_will_retry": notification.get("willRetry") if type(notification.get("willRetry")) is bool else None}
