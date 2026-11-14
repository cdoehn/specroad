"""Local operator policy; existing request contracts and counters are immutable."""
from dataclasses import replace
from hashlib import sha256

from .budget_limits import valid_limit
from .config import load, parse, render
from .errors import ControlError
from .local import json_read, lock, read_private, write_private
from .toml_compat import tomllib

FIELDS = ('clarification_allowed', 'clarification_limit', 'correction_limit')


def values(config):
    return {name: getattr(config, name) for name in FIELDS}


def validate_values(data):
    if (type(data) is not dict or set(data) - set(FIELDS)
            or any(type(value) is not bool if name == 'clarification_allowed'
                   else not valid_limit(value) for name, value in data.items())):
        raise ControlError('invalid_budget_policy', 'Use a Boolean clarification choice and positive integer budgets.')
    return dict(data)


def configured(config, overrides):
    return replace(config, **validate_values(overrides))


def cycle_overrides(paths):
    from .cycle_state import active_cycle
    cycle = active_cycle(paths)
    if cycle is None:
        return {}
    return validate_values(cycle.get('overrides', {}))


def snapshot(paths, *, allow_deferred=True):
    """One coherent policy snapshot; concurrent external edits are not guessed."""
    try:
        raw = read_private(paths.config)
        config = load(paths, allow_deferred=allow_deferred)
        if read_private(paths.config) != raw:
            raise ControlError('configuration_changed', 'Configuration changed while reading; retry the command.')
    except FileNotFoundError:
        raise ControlError('config_missing', 'Configuration is missing; no default identity is inferred.') from None
    return config, raw


def status(paths):
    config, raw = snapshot(paths)
    overrides = cycle_overrides(paths)
    return {'configured': values(config), 'configured_sha256': sha256(raw).hexdigest(), 'overrides': overrides,
            'effective': values(configured(config, overrides)),
            'applies_to': 'new_requests_and_new_budget_sequences', 'existing_counters_preserved': True}


def configure(paths, **changes):
    changes = validate_values({key: value for key, value in changes.items() if value is not None})
    if not changes:
        return status(paths)
    with lock(paths.state / 'operation.lock'):
        old, original = snapshot(paths, allow_deferred=False)
        new = configured(old, changes)
        candidate = render(new).encode()
        parse(tomllib.loads(candidate.decode()), paths)
        if read_private(paths.config) != original:
            raise ControlError('configuration_changed', 'Configuration changed before saving; existing bytes are preserved.')
        write_private(paths.config, candidate)
    # A notification wakes an idle worker; it neither starts one nor resumes pause.
    from .ipc import request
    try:
        request(paths, 'policy-changed')
        notice = 'notified'
    except ControlError as exc:
        notice = exc.code  # Durable configuration is still saved, never report rollback.
    return {**status(paths), 'saved': True, 'worker_notification': notice,
            'service_started': False, 'model_called': False}


def refresh(engine):
    """Only between ticks. A running turn keeps its immutable persisted contract."""
    from .cycle_state import pending
    try:
        raw = read_private(engine.paths.config)
    except FileNotFoundError:
        raise ControlError('config_missing', 'The running configuration is missing; preserve existing requests.') from None
    base = engine._policy_base
    if raw != engine._policy_raw:
        current, raw = snapshot(engine.paths)
        if replace(base, **values(current)) != current:
            raise ControlError('runtime_configuration_changed', 'Identity or transport changes require a controlled restart.')
        base = current
    # A new explicit start ignores stale/corrupt old cycle pointers and overrides.
    overrides = {} if pending(engine.paths) is not None else cycle_overrides(engine.paths)
    if raw != engine._policy_raw or overrides != engine._policy_overrides:
        engine.config = configured(base, overrides)
    engine._policy_base, engine._policy_raw = base, raw
    engine._policy_overrides = overrides
    engine.update(budget_policy={'configured': values(base), 'overrides': overrides,
                                'effective': values(engine.config)})
