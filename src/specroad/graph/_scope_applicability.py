"""One selected configuration policy for a supplied immutable scope inventory.

Seeds, bound query pages and required dependencies share classification and
semantic binding. This value performs no discovery, query evaluation or I/O.
Its cached decisions are local to one resolution, never reused across inputs.
"""
from ..configurations import evaluate_applicability, resolve_configuration
from ..configurations._context import configuration_scope_hash


class ScopeApplicability:
    def __init__(self, configuration_id, records):
        self._effective = (None if configuration_id is None else
                           resolve_configuration(records, configuration_id))
        self._decisions = {}

    @property
    def configuration_id(self):
        return None if self._effective is None else self._effective.configuration_id

    def includes(self, record):
        if self._effective is None:
            return True
        identity = record.identity.id
        if identity not in self._decisions:
            self._decisions[identity] = evaluate_applicability(
                record, self._effective, require_configuration=True).status == 'applicable'
        return self._decisions[identity]

    def configuration_hash(self, project_sha256, *, unconfigured=None):
        if self._effective is None:
            return unconfigured
        return configuration_scope_hash(project_sha256, self._effective.sha256)
