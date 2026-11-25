"""Observed source bytes and conservative native identity reservations.

An invalid semantic model is not replaced by a forged valid TargetModel.
Commands which need one retain an explicit unavailable finding; raw byte
operations remain available for a precisely named unprojectable resource.
"""
from types import SimpleNamespace
from ..model.errors import ModelError
from ..bundles.errors import BundleError
from ..model.identities import IdentityInventory, allocate_artifact_identity
from ..model.relation_identity import RelationInventory, allocate_relation_identity
from ..changes.force_projection import _records
from ..changes.force_domain_gates import record_denial
from ..changes.write_guard_values import require


class ForceSources:
    def __init__(self, root, before, history, configuration, decisions, original):
        self.root, self.before, self.history = root, dict(before), dict(history)
        self.configuration = configuration
        self.records = _records(before)
        self.source = SimpleNamespace(configuration=configuration)
        self.native = None
        self.model = None
        try:
            from .project_sources import AuthoringSources
            self.native = AuthoringSources(root)
            self.model = self.native.model
        except (ModelError, BundleError) as error:
            record_denial(decisions, error, operation=original['command_id'], subject='project', requested=original)
        old_ids, old_relations, approved = set(), set(), set()
        from .project_sources import _history
        from ..storage.json_syntax import parse_json_object
        for path, raw in {**before, **history}.items():
            try:
                value = parse_json_object(raw)
            except ModelError:
                if path.endswith('.md'):
                    try:
                        from ..storage.plan_markdown import parse_plan
                        value = [p.data for p in parse_plan(raw, path=path).projections]
                    except ModelError:
                        continue
                else:
                    continue
            _history(value, old_ids, old_relations, approved)
        self.identities = IdentityInventory(configuration.id_prefix, set(self.records), old_ids, set())
        self.relations = RelationInventory(set(), old_relations, set())

    def artifact(self, identity):
        rows = self.records.get(identity, [])
        require(len(rows) == 1, 'force_target_missing_or_ambiguous', exit_code=3)
        return rows[0]

    def allocate(self, kind):
        allocated = allocate_artifact_identity(kind, self.identities)
        self.identities = allocated.inventory
        return allocated.identity

    def relation(self):
        allocated = allocate_relation_identity(self.relations)
        self.relations = allocated.inventory
        return allocated.identity

    def verify_current(self):
        from ..changes._lock_files import LockFiles
        from ..changes._schema_transition_io import project_files
        from ..bundles._receipts import receipt_path
        with LockFiles(self.root) as files:
            actual, _, _ = project_files(files)
        require({p: b for p, b in actual.items() if not p.startswith('.specroad/')} == self.before
            and {p: b for p, b in actual.items() if receipt_path(p)} == self.history,
            'force_observed_source_changed', exit_code=6)
