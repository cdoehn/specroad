"""Correlate private dispatch receipts with live continuation evidence."""
from .errors import ControlError
from .local import json_read
from .retry_proof import load_failure
from .workspace import fingerprint
from .config import digest
from .execution_scope import execution_directory
from .continuation_evidence import sha, policy, terminal, prove_items, within, request_prompt


def receipts(config, directory, source):
    failure = load_failure(directory, config, source)
    attempt = json_read(directory / 'attempt.json')
    dispatch = json_read(directory / 'dispatch.json')
    expected = request_prompt(attempt, source)
    try:
        digest(attempt['workspace_sha256'])
        if type(attempt.get('number')) is not int or not 0 <= attempt['number'] <= 8:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ControlError('continuation_dispatch_unproven', 'Original dispatch baseline and number are required.') from None
    wanted = {'thread_id': config.session_id, 'turn_id': failure['turn_id'],
              'prompt_sha256': sha(expected), **policy(config)}
    cwd = str(execution_directory(config))
    modern = {**wanted, 'cwd': cwd}
    legacy = (config.access_mode == 'workspace-write'
              and cwd == str(config.repository) and dispatch == wanted)
    if (config.transport != 'app-server-proxy' or attempt.get('workspace_sha256') is None
            or not dispatch or not (dispatch == modern or legacy)):
        raise ControlError('continuation_dispatch_unproven', 'Continuation requires its exact original cwd and access policy receipt.')
    if json_read(directory / 'protocol-completion.json') is not None:
        raise ControlError('retry_completion_conflict', 'Existing successful output must be recovered instead.')
    return failure, attempt, dispatch, expected


def proof(config, codex, directory, source, *, saved=None):
    failure, attempt, dispatch, expected = receipts(config, directory, source)
    if not callable(getattr(codex, 'inspect_continuation', None)):
        raise ControlError('continuation_inactive_unproven', 'Complete continuation observation is unavailable.')
    turn = terminal(codex.inspect_continuation(failure['turn_id']), failure['turn_id'],
                    history=saved['history_sha256'] if saved else None)
    prove_items(turn, expected, config)
    current = fingerprint(config.repository)
    evidence = {**failure, 'workspace_sha256': current, 'history_sha256': sha(turn),
                'source_sha256': source['sha256'], 'attempt_sha256': sha(attempt),
                'dispatch_sha256': sha(dispatch), 'mode': 'continuation', 'legacy': False}
    if saved is not None and evidence != saved:
        raise ControlError('continuation_checkpoint_changed', 'Preserved work or failure receipts changed during backoff.')
    return evidence
