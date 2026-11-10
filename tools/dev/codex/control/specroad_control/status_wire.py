"""Bounded status output shared by every instance's local socket."""
import json


def encoded(reply):
    raw = (json.dumps(reply, allow_nan=False) + "\n").encode()
    if len(raw) > 65536:
        return b'{"ok": false, "error": "status_too_large"}\n'
    return raw
