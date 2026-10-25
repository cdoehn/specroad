"""Fixed E.3 kind/scope matrix shared by creation and manifest readers.

This is a pure value contract, safe for the project-free CLI registry. Native
ScopeDescriptor validation still owns selector shapes; closure, payload and
receipt checks remain separate. A matching row grants no project authority.
"""
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class BundleKindScope:
    bundle_kind: str
    scope_kinds: tuple[str, ...]
    boundary_policy: str
    read_only: bool
    configuration_allowed: bool
    idempotency_scopes: tuple[str, ...]

    def matches_scope(self, descriptor):
        """Match an already validated native descriptor without repairing it."""
        return (descriptor['scope_kind'] in self.scope_kinds
                and descriptor['boundary_policy'] == self.boundary_policy
                and (self.configuration_allowed
                     or (descriptor['selector'] == {}
                         and descriptor['configuration_id'] is None)))

    def creation_fields(self):
        """Current providers' explicit fields; receipt eligibility is separate.

        Project creation checks an empty receipt history before using portable;
        the codec also admits an explicitly declared local_only project.
        """
        return {'bundle_kind': self.bundle_kind, 'read_only': self.read_only,
                'idempotency_scope': self.idempotency_scopes[0]}


PROJECT = BundleKindScope('project', ('project',), 'closed', False, False,
                         ('portable', 'local_only'))
PARTIAL = BundleKindScope('partial', ('document', 'release'), 'partial', True, True,
                         ('local_only',))
KINDS = MappingProxyType({row.bundle_kind: row for row in (PROJECT, PARTIAL)})
SCOPE_KINDS = tuple(scope for row in KINDS.values() for scope in row.scope_kinds)
IDEMPOTENCY_SCOPES = tuple(dict.fromkeys(
    scope for row in KINDS.values() for scope in row.idempotency_scopes))
