"""Verified passive Force history, never positive model/review evidence."""
from dataclasses import dataclass
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs
from ..storage.json_syntax import parse_json_object as parsed
from .write_guard_values import require
from .receipt_values import completion_marker_path
from . import force_receipts


@dataclass(frozen=True)
class ForceAudit:
    source_bytes: bytes

    @property
    def data(self):
        write = parsed(self.source_bytes)['write']; marker = write['marker']
        return dict(format_version='force-historical-audit-v1',
            **{k: marker[k] for k in ('project_id', 'transaction_id', 'request_id', 'plan_sha256',
                'base_model_root_sha256', 'target_model_root_sha256')},
            **{k: write[k] for k in ('actor', 'planned_at', 'change_plan_id', 'files', 'target_inventory', 'force')},
            authoring_binding=dict(command_id=marker['command_id'], actor=write['actor'],
                planned_at=write['planned_at'], operations=write['operations'],
                operation_sequence_sha256=write['operations_sha256']),
            receipts=parsed(force_receipts.receipt_group(write)[completion_marker_path(marker['transaction_id'])])['receipts'],
            validation=write['validation'], approval_granted=False, write_authorized=False)

    def __bool__(self):
        raise TypeError('Force execution history is not approval or authority')


def read_force_group(files, project_id):
    paths = [p for p in files if p.endswith('/transaction.json')]
    require(len(paths) == 1, 'force_completion_group_required')
    raw = files[paths[0]]
    write = force_receipts.validate_transaction(raw)
    require(write['marker']['project_id'] == project_id and files == force_receipts.receipt_group(write),
        'force_completion_changed', exit_code=6)
    return ForceAudit(raw)


def _edges(journal):
    from .normal_completion import NormalAudit
    from ..migration.receipts import HistoricalMigrationJournal
    if type(journal) in (NormalAudit, ForceAudit):
        for row in journal.data['files']:
            yield row['path'], (None if row['before'] is None else (row['before']['size'], row['before']['sha256'])), (None if row['after'] is None else (row['after']['size'], row['after']['sha256']))
    elif type(journal) is HistoricalMigrationJournal:
        op = journal.plan.data['operations'][0]
        before = {r['path']: (r['size'], r['sha256']) for r in op['source_files']}
        after = {r['path']: (r['size'], r['sha256']) for r in op['target_files']}
        for row in op['changes']:
            yield row['path'], before.get(row['path']), after.get(row['path'])
    else:
        for row in journal.data['files']:
            yield row['path'], (None if not row['existed_before'] else (row['before_size'], row['before_sha256'])), (None if row['after_sha256'] is None else (row['after_size'], row['after_sha256']))


def provenance(journals, files):
    """Track exact observed byte succession, not clocks or file-name order."""
    edges = {}
    for journal in journals:
        for path, old, new in _edges(journal):
            edges.setdefault(path, {}).setdefault(old, set()).add(new)
    rows = []
    for journal in journals:
        if type(journal) is not ForceAudit:
            continue
        data = journal.data
        if not data['force']['used']:
            continue
        for effect in data['files']:
            after = effect['after']
            path = effect['path']; raw = files.get(path)
            current = None if raw is None else (len(raw), sha256(raw).hexdigest())
            initial = None if after is None else (after['size'], after['sha256'])
            pending = [initial]; seen = set()
            while pending:
                value = pending.pop()
                if value == current:
                    rows.append(dict(path=path, current_sha256=None if raw is None else sha256(raw).hexdigest(),
                        transaction_id=data['transaction_id'], plan_sha256=data['plan_sha256'],
                        force=data['force'], validation_status=data['validation']['validation_status'],
                        approval_granted=False))
                    break
                if value in seen: continue
                seen.add(value)
                pending.extend(edges.get(path, {}).get(value, ()))
    return sorted(rows, key=lambda r: (r['path'], r['transaction_id']))


def model_provenance(model, journals):
    rows = provenance(journals, model.source_files)
    if not rows:
        return model
    from .target_model import TargetModel
    return TargetModel(model.configuration_bytes, model.binding, model.documents,
        profile=model.profile, resource_files=model.resource_files, attachments=model.attachment_descriptors,
        language_packages=model.language_packages, plan_sources=model.plan_sources,
        force_provenance=rows, **model.reservations)
