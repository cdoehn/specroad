"""Complete live authoring inputs and immutable historical identity reservations.

Filesystem observations are rechecked through publication. Historical bytes
reserve identities; they never supply authority or a positive review decision.
"""
from hashlib import sha256
from ..model.errors import ModelError
from ..model.identities import IdentityInventory
from ..model.relation_identity import RelationInventory, relation_identity
from ..model.identity_values import artifact_identity
from ..model.canonical import canonical_json_bytes
from ..changes.target_model import TargetModel
from ..changes.receipt_values import request_receipt_path, transaction_receipt_path
from ..security.resource_access import opened_resource, directory_entries
from ..storage.json_syntax import parse_json_object
from ..archive.objects import SnapshotObject
from ..bundles._receipt_snapshot import ReceiptSnapshot
from ..bundles._project_snapshot import _archive_paths, _previous_manifest
from ._inspection_snapshot import InspectionSnapshot, InspectionChanged


def _history(value, artifacts, relations, approved):
    """Conservative reservation of native identities in passive historical data."""
    pending = [value]
    while pending:
        item = pending.pop()
        if type(item) is list:
            pending.extend(item)
        elif type(item) is dict:
            if 'artifact_type' in item and 'id' in item:
                try:
                    identity = artifact_identity(item)
                except ModelError:
                    pass
                else:
                    artifacts.add(identity.id)
                    if item.get('maturity') == 'approved':
                        approved.add(identity.id)
            if 'relation_id' in item:
                try:
                    identity = relation_identity(item)
                except ModelError:
                    pass
                else:
                    relations.add(identity.id)
            from ..model.relation_values import RelationIdentity
            for key in ('parent_relation_id', 'relation_id'):
                if key in item:
                    try:
                        relations.add(RelationIdentity(item[key], 'random128-v1').id)
                    except ModelError:
                        pass
            pending.extend(item.values())


class AuthoringSources:
    def __init__(self, root):
        self.snapshot = InspectionSnapshot(root, None, include_archive_objects=True,
                                           include_plan_sources=True)
        self.source = self.snapshot.source
        self.marker = _previous_manifest(self.source)
        self.receipts = ReceiptSnapshot(self.source, imported_manifest=self.marker)
        self.archive_paths = _archive_paths(self.source)
        self.archives = {}
        for path in self.archive_paths:
            raw = self.source.read_normative(path, referenced_payloads=self.archive_paths)
            if SnapshotObject(raw).reference.path != path:
                raise ModelError('authoring_archive_binding')
            self.archives[path] = raw
        old_ids, old_relations, approved = set(), set(), set()
        # Verified receipt groups include their original operations. Byte-bound
        # Markdown operations retain their source projections as originals too.
        history = [*self.receipts.payloads.values(), *self.archives.values()]
        for raw in history:
            try:
                value = parse_json_object(raw)
            except ModelError:
                try:
                    from ..storage.plan_markdown import parse_plan
                    value = [p.data for p in parse_plan(raw).projections]
                except ModelError:
                    continue  # Attachment/non-model archive: no artifact identity.
            _history(value, old_ids, old_relations, approved)
            stack = [value]
            while stack:
                item = stack.pop()
                if type(item) is dict:
                    if item.get('op') == 'plan_edit':
                        from ..changes.plan_source_operation import sources
                        for side in ('before', 'after'):
                            for source in sources(item, side):
                                _history([p.data for p in source.projections], old_ids, old_relations, approved)
                    stack.extend(item.values())
                elif type(item) is list:
                    stack.extend(item)
        model = self.snapshot.model
        prefix = model.configuration.id_prefix
        if any(i.split('-')[0] != prefix for i in old_ids):
            raise ModelError('authoring_history_project_mismatch')
        self.model = TargetModel(model.configuration_bytes, model.binding, model.documents,
            profile=model.profile, resource_files=model.resource_files,
            attachments=model.attachment_descriptors, language_packages=model.language_packages,
            plan_sources=model.plan_sources, reserved_artifact_ids=sorted(old_ids),
            reserved_relation_ids=sorted(old_relations), previously_approved_ids=sorted(approved))
        from ..changes.force_history import model_provenance
        self.model = model_provenance(self.model, self.receipts.journals)
        from ..migration.model_inputs import records
        current = records(self.model)
        self.identities = IdentityInventory(prefix, {r.identity.id for r in current}, old_ids, set())
        self.relations = RelationInventory({edge.identity.id for r in current for edge in r.relations},
                                          old_relations, set())
        self.packages = tuple(d for d in self.snapshot.raw if d not in self.model.source_files)
        self.verify_current()

    def verify_current(self):
        self.snapshot.verify_current()
        self.verify_history()
        self.receipts.verify_current()

    def verify_history(self, *, transaction_id=None, request_id=None, new_archives=None):
        """Allow only this writer's new receipts, never a foreign extra record."""
        source = self.source
        current_archives = set(_archive_paths(source))
        new_archives = {} if new_archives is None else dict(new_archives)
        if (not set(self.archive_paths) <= current_archives <= set(self.archive_paths) | set(new_archives)
                or _previous_manifest(source) != self.marker):
            raise InspectionChanged('authoring_history_inventory_changed')
        for path, raw in self.archives.items():
            if source.read_normative(path, referenced_payloads=self.archive_paths) != raw:
                raise InspectionChanged('authoring_archive_changed', path=path)
        for path in current_archives - set(self.archive_paths):
            if source.read_normative(path, referenced_payloads=tuple(current_archives)) != new_archives[path]:
                raise InspectionChanged('authoring_archive_changed', path=path)
        allowed = set()
        if transaction_id is not None:
            allowed.add(transaction_receipt_path(transaction_id).rsplit('/', 1)[0])
        if request_id is not None:
            allowed.add(request_receipt_path(request_id))
        for path, original in self.receipts.records.items():
            with opened_resource(source.boundary, path) as (_, info):
                if ((info.st_dev, info.st_ino), source.boundary.read_bytes(path)) != original:
                    raise InspectionChanged('authoring_receipt_changed', path=path)
        for path, original in self.receipts.directories.items():
            with opened_resource(source.boundary, path, directory=True, missing_ok=original is None) as (fd, info):
                if fd is None:
                    continue
                entries = tuple(e for e in directory_entries(source.boundary, path)
                                if path + '/' + e[0] not in allowed)
                if (original is None and entries) or (original is not None and
                        ((info.st_dev, info.st_ino), entries) != original):
                    raise InspectionChanged('authoring_receipt_inventory_changed', path=path)
        source.check_current()
