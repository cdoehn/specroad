"""Verified normal v2 audit records, without a recovery journal or capability."""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes as jcs
from ..storage.json_syntax import parse_json_object as parsed
from .receipt_values import transaction_receipt_path, completion_marker_path, ReceiptError
from .write_guard_values import validate_transaction, receipt_group, completion, require
from .normal_access import require_normal_access
from .receipt_read import _LegacyCompletionProof


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


class NormalCompletionProof(_LegacyCompletionProof):
    def __init__(self, files, source, transaction_id, *, preflight=None):
        self.files, self.source = files, source
        self.records, self.parents = {}, {}
        self.archive_path = completion_marker_path(transaction_id)
        self.active_raw = None
        self.current_target_verified = preflight is not None
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
            self.live_snapshot = _target_snapshot(source, _expected_target(preflight))
        self.check()

    def check(self):
        require_normal_access(self.source.boundary.root,
                              expected_project_id=self.source.configuration.project_id)
        super().check()
        require_normal_access(self.source.boundary.root,
                              expected_project_id=self.source.configuration.project_id)

    def work_present(self):
        self.check()
        return False

    def result(self):
        self.check()
        return completion(self.write, current=self.current_target_verified)
