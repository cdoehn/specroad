"""Pure continuation contracts: preserved actions, request identity and guards."""
import hashlib
import json
from pathlib import Path
from .errors import ControlError
from .job_contract import prompt_for, continuation_prompt
from .turn_errors import error_code
from .execution_scope import policy


def sha(document):
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def terminal(live, turn_id, *, history=None):
    turn = live.get('turn') or {}
    if live.get('thread_status') == 'active' or turn.get('status') == 'inProgress':
        raise ControlError('dev_turn_active', 'Existing work is still active; preserve it.')
    if (live.get('thread_status') not in ('idle', 'notLoaded', 'systemError')
            or live.get('latest_turn_id') != turn_id or live.get('background_terminals') != []):
        raise ControlError('continuation_inactive_unproven', 'Exact latest work and empty background terminals are required.')
    if turn.get('id') != turn_id or turn.get('status') != 'failed' or error_code(turn.get('error')) != 'serverOverloaded':
        raise ControlError('retry_terminal_unproven', 'Only the exact terminal overload permits continuation.')
    if history is not None and history != sha(turn):
        raise ControlError('continuation_history_changed', 'The bound failed turn evidence changed.')
    return turn


def prove_items(turn, expected_prompt, config):
    items = turn.get('items')
    if (turn.get('itemsView') != 'full' or turn.get('itemsTruncated') or turn.get('itemsNextCursor')
            or not isinstance(items, list) or not 1 <= len(items) <= 4096):
        raise ControlError('retry_items_unproven', 'A complete exact action list is required.')
    identities, user_count = set(), 0
    for item in items:
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id']
                or item['id'] in identities or item.get('truncated') or item.get('hasMore')):
            raise ControlError('retry_items_unproven', 'Duplicate, truncated or malformed action evidence.')
        identities.add(item['id'])
        kind = item.get('type')
        if kind == 'userMessage':
            content = item.get('content')
            if (not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict)
                    or content[0].get('type') != 'text' or content[0].get('text') != expected_prompt
                    or content[0].get('text_elements', []) != []
                    or set(content[0]) - {'type', 'text', 'text_elements'}):
                raise ControlError('retry_source_unproven', 'Only the exact controller request may be continued.')
            user_count += 1
        elif kind == 'agentMessage' and item.get('questions'):
            raise ControlError('continuation_input_pending', 'Outstanding questions require user input.')
        elif kind in ('agentMessage', 'reasoning', 'contextCompaction', 'plan'):
            pass
        elif kind == 'commandExecution':
            if (item.get('status') not in ('completed', 'failed') or type(item.get('exitCode')) is not int
                    or not isinstance(item.get('command'), str) or not item['command']
                    or item.get('source') not in ('agent', 'unifiedExecStartup', 'unifiedExecInteraction')
                    or not within(item.get('cwd'), config.repository)):
                raise ControlError('continuation_actions_unproven', 'Every command must have a terminal exit in the Dev workspace.')
        elif kind == 'fileChange':
            changes = item.get('changes')
            if (item.get('status') != 'completed' or not isinstance(changes, list) or not changes
                    or any(not isinstance(change, dict) or not (
                        within(change.get('path'), config.repository)
                        or within(change.get('path'), config.exchange)) for change in changes)):
                raise ControlError('continuation_actions_unproven', 'Only completed local file operations may be continued.')
        else:
            raise ControlError('continuation_actions_unproven', 'Unknown, delegated or external tools require review.')
    if user_count != 1:
        raise ControlError('retry_source_unproven', 'Exactly one bound controller request is required.')


def within(value, root):
    if not isinstance(value, str) or not value or '\0' in value:
        return False
    path = Path(value)
    if not path.is_absolute():
        return False
    try:
        return path.resolve().is_relative_to(root.resolve())
    except (OSError, ValueError, RuntimeError):
        return False


def request_prompt(attempt, source):
    """Keep the original request stable even when its Result moves to Archive."""
    facts = attempt.get('request_source')
    if (not isinstance(facts, dict) or set(facts) != {'path', 'sha256', 'binding', 'run_id'}
            or any(facts[key] != source[key] for key in ('sha256', 'binding', 'run_id'))
            or not isinstance(facts['path'], str) or not Path(facts['path']).is_absolute()):
        raise ControlError('continuation_dispatch_unproven', 'The exact original source request is required.')
    previous = attempt.get('continuation')
    if previous is not None:
        try:
            from .retry_ledger import validate_mode
            if not isinstance(previous, dict):
                raise ValueError
            validate_mode(previous, source['sha256'])
            if previous['mode'] != 'continuation' or previous['thread_id'] != attempt['thread_id']:
                raise ValueError
        except (KeyError, ValueError, TypeError):
            raise ControlError('continuation_dispatch_unproven', 'The preceding continuation must remain bound.') from None
    # json_write sorts nested keys. Generate the same byte-exact request both
    # before publication and after reloading the immutable Attempt receipt.
    canonical = json.loads(json.dumps(facts, sort_keys=True))
    selected = attempt.get('request_contract')
    return continuation_prompt(canonical, previous, selected) if previous else prompt_for(canonical, selected)
