"""Native completed receipt lineage, separate from current model qualification."""
from hashlib import sha256

from ..bundles._receipts import completed_receipts, receipt_path
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ..changes._common import _artifact
from .values import require


def receipt_history(files, project_id):
    from ._recovery_receipt_history import recovery_receipts
    recovered = recovery_receipts(files, project_id)
    originals = {p: raw for p, raw in files.items() if receipt_path(p)}
    successful = {p: raw for p, raw in originals.items() if p not in recovered}
    return {**originals, **recovered}, completed_receipts(successful, project_id)


def check_receipt_targets(journals, target):
    # Follow only exact before/after byte bindings of complete native writes.
    # Timestamps and transaction-name order never establish publication order.
    edges = {}
    for journal in journals:
        for item in journal.data['files']:
            if item['existed_before']:
                edges.setdefault(item['path'], {}).setdefault(
                    (item['before_size'], item['before_sha256']), set()).add(
                    (item['after_size'], item['after_sha256']))
    for journal in journals:
        # A complete inventory binds the original transaction, not perpetual
        # membership of every unchanged file in all later Restore targets.
        # Only actual successful writes can establish a new published revision.
        operations = journal.data['authoring_binding']['operations']
        for entry in journal.data['files']:
            row = {'path': entry['path'], 'size': entry['after_size'],
                   'sha256': entry['after_sha256']}
            path = row['path']
            raw = target.get(path)
            require(raw is not None, 'restore_published_identity_missing', path=path, exit_code=6)
            wanted = (len(raw), sha256(raw).hexdigest())
            pending = [(row['size'], row['sha256'])]; visited = set()
            while pending:
                state = pending.pop()
                if state == wanted:
                    break
                if state in visited:
                    continue
                visited.add(state)
                pending.extend(edges.get(path, {}).get(state, ()))
            else:
                # A later fully qualified source may legitimately contain a
                # newer mutable revision without retaining all old effects.
                # Use explicit native operation guards, never timestamps or
                # a guessed revision from a current file as historical proof.
                try:
                    candidate = parse_json_object(raw)
                    identity = _artifact(candidate, '')
                except ModelError:
                    require(False, 'restore_receipt_history_conflict', path=path, exit_code=6)
                from ._history import protected_record
                require(not protected_record(candidate),
                        'restore_receipt_history_conflict', path=path, exit_code=6)
                relevant = [op for op in operations if identity.id in
                    (op.get('target'), op.get('source'), op.get('artifact', {}).get('id'))]
                revisions = [op['expected_revision'] + 1 for op in relevant if 'expected_revision' in op]
                revisions.extend(1 for op in relevant if op['op'] == 'create')
                require(revisions and candidate['revision'] > max(revisions),
                        'restore_receipt_history_conflict', path=path, exit_code=6)
