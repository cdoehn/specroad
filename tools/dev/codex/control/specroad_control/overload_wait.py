"""Observe completion of known work without repeating it or spending retry budget."""
from copy import deepcopy
from . import continuation
from .errors import ControlError
from .workspace import fingerprint

INTERVAL = 30
SETTLE_SECONDS = 120
# Only these fields of initially unfinished commands may evolve. Identity,
# command, cwd, source, processId and every other action stay bound.
COMMAND_PROGRESS = {'status', 'exitCode', 'aggregatedOutput', 'durationMs'}


def background_identity(item):
    """Codex metrics vary during a command; only its four fixed fields identify it."""
    keys = ('processId', 'itemId', 'command', 'cwd')
    if (not isinstance(item, dict)
            or any(not isinstance(item.get(key), str) or not item[key] for key in keys)):
        raise ControlError('overload_background_unproven', 'Background work needs process, item, command and cwd.')
    return {key: item[key] for key in keys}


def observe(config, codex, directory, source, number, *, saved=None):
    failure, attempt, dispatch, expected = continuation.receipts(config, directory, source)
    if attempt['number'] != number:
        raise ControlError('continuation_dispatch_unproven', 'The failed attempt number must match the ledger.')
    if not callable(getattr(codex, 'inspect_overload_wait', None)):
        raise ControlError('overload_observation_unavailable', 'Complete waiting observation is unavailable.')
    workspace = fingerprint(config.repository)
    live = codex.inspect_overload_wait(failure['turn_id'])
    # A nonempty background inventory permits observation only, never dispatch.
    turn = continuation.terminal({**live, 'background_terminals': []}, failure['turn_id'])
    background = live.get('background_terminals')
    if not isinstance(background, list) or len(background) > 128:
        raise ControlError('overload_background_unproven', 'A complete background inventory is required.')
    background = [background_identity(item) for item in background]
    if len({item['processId'] for item in background}) != len(background):
        raise ControlError('overload_background_unproven', 'Duplicate background process identity.')
    provisional = deepcopy(turn)
    pending = []
    for item in provisional.get('items', []):
        if isinstance(item, dict) and item.get('type') == 'commandExecution' and item.get('status') == 'inProgress':
            if item.get('exitCode') is not None:
                raise ControlError('continuation_actions_unproven', 'A running command cannot already have an exit.')
            pending.append(item.get('id'))
            item.update(status='completed', exitCode=0)
    # This validates *all* other actions and the exact request, including command
    # provenance. The provisional exit is never stored or used to allow dispatch.
    continuation.prove_items(provisional, expected, config)
    if fingerprint(config.repository) != workspace:
        raise ControlError('overload_workspace_changed', 'Workspace changed during observation.')
    initial_pending = saved['evidence']['pending'] if saved else sorted(pending)
    by_id = {item['id']: item for item in turn['items']}
    for terminal in background:
        item = by_id.get(terminal['itemId'], {})
        if (terminal['itemId'] not in initial_pending
                or any(terminal[key] != item.get(key) for key in ('command', 'cwd'))
                or item.get('processId') not in (None, terminal['processId'])):
            raise ControlError('overload_background_unproven', 'Background work does not match the owned pending command.')
    normalized = deepcopy(turn)
    for item in normalized['items']:
        if item['id'] in initial_pending:
            for key in COMMAND_PROGRESS:
                item.pop(key, None)
    evidence = {'failure': failure, 'attempt_sha256': continuation.sha(attempt),
                'dispatch_sha256': continuation.sha(dispatch), 'source_sha256': source['sha256'],
                'number': number, 'workspace_sha256': workspace, 'pending': initial_pending,
                'history_sha256': continuation.sha(normalized)}
    completed = {item['id']: continuation.sha(item) for item in turn['items']
                 if item['id'] in initial_pending and item.get('status') in ('completed', 'failed')}
    terminals = sorted(continuation.sha(item) for item in background)
    progress = {'completed': completed, 'terminals': terminals, 'history_sha256': continuation.sha(turn)}
    if saved:
        previous = saved['progress']
        if (evidence != saved['evidence'] or not set(pending) <= set(initial_pending)
                or any(completed.get(key) != value for key, value in previous['completed'].items())
                or not set(terminals) <= set(previous['terminals'])):
            raise ControlError('overload_checkpoint_changed', 'Bound actions, background work or workspace changed.')
    elif not pending and background:
        raise ControlError('overload_background_unproven', 'Background work without a known pending command is not attributable.')
    return evidence, progress, not pending and not background


def next_observation(progress, ready, now, since):
    """A live terminal has no timeout; vanished terminals need prompt exit evidence."""
    if progress['terminals']:
        return now + INTERVAL, None
    if ready:
        return now, since
    since = now if since is None else since
    if now >= since + SETTLE_SECONDS:
        raise ControlError('overload_completion_unproven', 'Background ended but command exit evidence did not settle.')
    return min(now + INTERVAL, since + SETTLE_SECONDS), since
