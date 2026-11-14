"""Shared typed operator policy, independent of runtime files and ledgers."""
from dataclasses import replace
from .budget_limits import valid_limit
from .errors import ControlError

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
