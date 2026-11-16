"""Verified normal v2 audit records, without a recovery journal or capability."""
from dataclasses import dataclass
from itertools import islice
import os

from ..model.canonical import canonical_json_bytes as jcs
from ..storage.json_syntax import parse_json_object as parsed
from .receipt_values import transaction_receipt_path, completion_marker_path, ReceiptError
from .write_guard_values import validate_transaction, receipt_group, completion, require
from .normal_access import require_normal_access
from ._completion_records import CompletionRecords


@dataclass(frozen=True)
class NormalAudit:
    source_bytes: bytes

    @property
    def data(self):
        return parsed(self.source_bytes)

    def __bool__(self):
        raise TypeError('Historical audit data is not write authorization')


def audit(write):
    """Project only recorded facts for the existing domain retry adapters."""
    marker = write['marker']
    refs = parsed(receipt_group(write)[completion_marker_path(marker['transaction_id'])])['receipts']
    return NormalAudit(jcs(dict(format_version='normal-write-audit-v1',
        **{k: marker[k] for k in ('project_id', 'transaction_id', 'request_id',
            'plan_sha256', 'base_model_root_sha256', 'target_model_root_sha256')},
        **{k: write[k] for k in ('actor', 'planned_at', 'change_plan_id', 'files', 'target_inventory')},
        authoring_binding=dict(command_id=marker['command_id'], actor=write['actor'],
            planned_at=write['planned_at'], operations=write['operations'],
            operation_sequence_sha256=write['operations_sha256']), receipts=refs)))


def read_normal_group(files, project_id):
    """Validate exactly one complete canonical group, preserving its bytes."""
    paths = [p for p in files if p.endswith('/transaction.json')]
    require(len(paths) == 1, 'write_completion_group_required')
    write = validate_transaction(files[paths[0]])
    require(write['marker']['project_id'] == project_id, 'write_completion_binding', exit_code=6)
    require(files == receipt_group(write), 'write_completion_changed', exit_code=6)
    return write


class NormalCompletionProof(CompletionRecords):
    def __init__(self, files, source, transaction_id, *, preflight=None):
        super().__init__(files, source)
        self.archive_path = completion_marker_path(transaction_id)
        self.active_raw = None
        self.expected = self.live_snapshot = None
        require_normal_access(source.boundary.root, expected_project_id=source.configuration.project_id)
        raw = self.read(transaction_receipt_path(transaction_id))
        if raw != jcs(parsed(raw)):
            raise ReceiptError('write_completion_changed', exit_code=6)
        write = validate_transaction(raw)
        require(write['marker']['project_id'] == source.configuration.project_id
            and write['marker']['transaction_id'] == transaction_id, 'write_completion_binding', exit_code=6)
        group = receipt_group(write)
        for path, expected in group.items():
            require(self.read(path) == expected, 'write_completion_changed', exit_code=6)
        self.receipt_paths = [p for p in group if p != self.archive_path]
        self.archived_raw = group[self.archive_path]
        self.write = write
        self.journal = audit(write)
        if preflight is not None:
            from .publication_values import PublicationPreflight
            require(type(preflight) is PublicationPreflight, 'publication_preflight_required', exit_code=2)
            require(preflight._model.binding.root_identity == source.boundary._root_identity
                and preflight._model.binding.project_id == source.configuration.project_id,
                'completion_project_binding_mismatch', exit_code=6)
            require(preflight.request.plan.sha256 == write['marker']['plan_sha256'],
                    'write_completion_plan_changed', exit_code=6)
            # Reading historical receipts alone never certifies current targets.
            from .receipt_finalization import _target_snapshot
            from .receipt_read import _expected_target
            from .write_guard_values import inventory, metadata
            self.expected = _expected_target(preflight)
            plan = preflight.request.plan.data
            before = {**preflight._model.source_files,
                      **{d.path: d.content for d in preflight._package_files}}
            effects = [{'path': p, 'before': metadata(before[p]) if p in before else None,
                        'after': metadata(self.expected[p]) if p in self.expected else None}
                       for p in sorted(before.keys() | self.expected.keys())
                       if before.get(p) != self.expected.get(p)]
            require(write['target_inventory'] == inventory(self.expected) and write['files'] == effects
                and write['actor'] == plan['actor'] and write['planned_at'] == plan['planned_at']
                and write['operations'] == plan['operations']
                and write['change_plan_id'] == plan['change_plan_id']
                and write['marker']['request_id'] == plan['request_id']
                and write['marker']['base_model_root_sha256'] == plan['base']['model_root_sha256']
                and write['marker']['target_model_root_sha256'] == plan['expected_result']['model_root_sha256'],
                'completion_request_binding_mismatch', exit_code=6)
            self.live_snapshot = _target_snapshot(source, self.expected)
        self.check()

    def read(self, path, *, optional=False):
        records, parents = dict(self.records), dict(self.parents)
        raw = super().read(path, optional=optional)
        require(all(self.parents.get(p) == value for p, value in parents.items())
            and all(self.records.get(p) == value for p, value in records.items()),
            'completion_proof_changed', exit_code=6)
        return raw

    def _namespace(self):
        parts = tuple(self.archive_path.split('/')[:-1])
        with self.files.directory(parts) as directory:
            require(directory is not None, 'write_completion_missing')
            # A complete transaction has exactly these two files. Stop as soon
            # as an extra entry proves that the namespace no longer matches.
            with os.scandir(directory) as entries:
                names = {entry.name for entry in islice(entries, 3)}
            require(names == {'transaction.json', 'committed.json'},
                    'write_completion_namespace_changed', exit_code=6)

    def check(self):
        require_normal_access(self.source.boundary.root,
                              expected_project_id=self.source.configuration.project_id)
        self._namespace()
        super().check()
        if self.expected is not None:
            from .receipt_finalization import _target_snapshot
            require(_target_snapshot(self.source, self.expected) == self.live_snapshot,
                    'completion_target_identity_changed', exit_code=6)
        self._namespace()
        require_normal_access(self.source.boundary.root,
                              expected_project_id=self.source.configuration.project_id)

    def work_present(self):
        self.check()
        return False

    def result(self):
        self.check()
        return completion(self.write, current=self.expected is not None)
