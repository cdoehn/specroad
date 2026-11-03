"""Pure full-turn/source and readonly command evidence checks."""
import json
import shlex
from .errors import ControlError


def safe_command(command):
    """A tiny semantic allowlist, NOT a shell sandbox or a substring check."""
    if not isinstance(command, str) or len(command) > 4096:
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    if len(words) == 3 and words[0] in ("/bin/bash", "/bin/sh", "bash", "sh") and words[1] in ("-c", "-lc"):
        command = words[2]
    # Only the actual cwd probes seen in the incident; no variables, redirects,
    # command substitution, wrappers, arbitrary git aliases, or background work.
    for part in command.replace("&&", "\n").splitlines():
        if part.strip() not in ("pwd", "pwd -P", "git rev-parse --show-toplevel"):
            return False
    return bool(command.strip())


def source_message(item, source):
    content = item.get("content")
    if not isinstance(content, list):
        return False
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "text" or not isinstance(part.get("text"), str):
            continue
        lines = part["text"].splitlines()
        if len(lines) < 2 or not lines[0].startswith("Einmaliger SpecRoad-Entwicklungsdurchlauf N,"):
            continue
        try:
            value = json.loads(lines[1])
        except ValueError:
            continue
        if isinstance(value, dict) and all(value.get(k) == source[k] for k in ("sha256", "binding", "run_id")):
            return True
    return False


def prove_readonly_turn(turn, source):
    items = turn.get("items")
    if turn.get("itemsTruncated") or turn.get("itemsNextCursor"):
        raise ControlError("retry_items_unproven", "Truncated turn items do not prove safe replay.")
    if not isinstance(items, list) or not items or len(items) > 4096:
        raise ControlError("retry_items_unproven", "Full matching turn items are required for a safe retry.")
    has_source = False
    identities = set()
    for item in items:
        if not isinstance(item, dict):
            raise ControlError("retry_items_unproven", "Unrecognized turn item.")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id or item_id in identities:
            raise ControlError("retry_items_unproven", "Every full turn item needs a unique identity.")
        identities.add(item_id)
        kind = item.get("type")
        if kind == "userMessage":
            if has_source or not source_message(item, source):
                raise ControlError("retry_source_unproven", "Extra or unmatched user input cannot authorize replay.")
            has_source = True
        elif kind in ("agentMessage", "reasoning"):
            pass
        elif kind == "commandExecution" and safe_command(item.get("command")) and item.get("status") == "completed" and item.get("exitCode") == 0:
            pass
        else:
            raise ControlError("retry_effects_unproven", "Tool work or an unknown item prevents automatic replay.")
    if not has_source:
        raise ControlError("retry_source_unproven", "The failed turn must contain this exact bound development request.")
