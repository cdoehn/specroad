"""Correlate immutable attempt facts, live Codex state and Dev workspace guards."""
from .errors import ControlError
from .local import json_read
from .workspace import fingerprint
from .turn_errors import error_code
from .readonly_evidence import prove_readonly_turn


def load_failure(directory, config, source, *, legacy=False):
    """New attempts always have explicit failure and source receipts."""
    failure = json_read(directory / "failure.json")
    attempt = json_read(directory / "attempt.json")
    turn = json_read(directory / "turn.json")
    if failure is None and legacy and turn and attempt is None:
        from .legacy_failure import from_events
        failure = from_events(directory / "events.jsonl", config.session_id, turn.get("turn_id"))
    if not failure or (not attempt and not legacy) or not turn:
        raise ControlError("retry_evidence_missing", "No complete terminal failure evidence for this attempt.")
    if ((attempt is not None and (attempt.get("source_sha256") != source["sha256"] or attempt.get("thread_id") != config.session_id))
            or turn.get("thread_id") != config.session_id or failure.get("thread_id") != config.session_id
            or failure.get("turn_id") != turn.get("turn_id") or not isinstance(turn.get("turn_id"), str)
            or not turn["turn_id"] or len(turn["turn_id"]) > 160):
        raise ControlError("retry_evidence_invalid", "Failure evidence does not match the configured thread and source.")
    if failure.get("turn_status") != "failed" or failure.get("codex_error") != "serverOverloaded" or failure.get("codex_will_retry") is not False:
        raise ControlError("retry_not_transient", "Only a confirmed terminal overload without an internal retry is eligible.")
    return failure


def proof(config, codex, directory, source, *, legacy=False, guard=None):
    failure = load_failure(directory, config, source, legacy=legacy)
    completed = json_read(directory / "protocol-completion.json")
    if completed is not None:
        raise ControlError("retry_completion_conflict", "A completion record exists; recover it instead of retrying.")
    live = codex.inspect_turn(failure["turn_id"])
    if live.get("thread_status") == "active" or (live.get("turn") or {}).get("status") == "inProgress":
        raise ControlError("dev_turn_active", "Codex still reports active work; no replacement is allowed.")
    if live.get("thread_status") not in ("idle", "notLoaded"):
        raise ControlError("retry_status_unknown", "The live thread must be verifiably inactive.")
    turn = live.get("turn") or {}
    if turn.get("id") != failure["turn_id"] or turn.get("status") != "failed" or error_code(turn.get("error")) != "serverOverloaded":
        raise ControlError("retry_terminal_unproven", "The exact failed turn is not confirmed by the daemon.")
    prove_readonly_turn(turn, source)
    current = fingerprint(config.repository)
    attempt = json_read(directory / "attempt.json")
    if attempt is not None:
        if 'request_contract' in attempt:
            from .job_contract import contract
            selected = contract(attempt['request_contract'])
            if selected['version'] in (2, 3, 4):
                from .continuation_evidence import request_prompt
                expected = request_prompt(attempt, source)
                users = [item for item in turn['items'] if item['type'] == 'userMessage']
                content = users[0]['content']
                if (len(content) != 1 or content[0].get('type') != 'text'
                        or content[0].get('text') != expected
                        or content[0].get('text_elements', []) != []
                        or set(content[0]) - {'type', 'text', 'text_elements'}):
                    raise ControlError('retry_source_unproven', 'The versioned decision authority must match the exact request.')
        previous = attempt.get("workspace_sha256")
        if previous is None:
            raise ControlError("retry_workspace_unproven", "The original attempt has no trustworthy workspace baseline.")
        if previous != current:
            raise ControlError("retry_workspace_changed", "Dev files or staged state changed since the failed attempt.")
    elif not legacy:
        raise ControlError("retry_workspace_unproven", "A baseline is required for an automatic retry.")
    if guard is not None and guard != current:
        raise ControlError("retry_workspace_changed", "Dev state changed during the waiting period.")
    return {**failure, "workspace_sha256": current, "legacy": attempt is None}
