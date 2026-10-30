"""Original terminal recovery receipts, never successful writes or live proof."""
from ..changes._discard_inputs import validate_discard_originals, discard_completion_record
from ..changes._recovery_evidence import EvidenceRecord, _action_fields, evidence_root, rollback_receipt
from ..changes.journal_values import BuildingJournal
from ..changes.staging_values import PreparedJournal
from ..changes.recovery_values import DiscardedJournal, RolledBackJournal
from ..changes.receipt_values import transaction_receipt_path
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from ._codec import file_row
from .values import require


def recovery_receipts(files, project_id):
    retained = {}
    for path, raw in sorted(files.items()):
        if not path.startswith('.specroad/transactions/receipts/') or not path.endswith('/transaction.json'):
            continue
        value = parse_json_object(raw)
        if value.get('format_version') != 'recovery-transaction-receipt-v1':
            continue
        require(value.get('action') in ('discard', 'rollback'), 'restore_recovery_receipt_action_invalid')
        journal_type = DiscardedJournal if value['action'] == 'discard' else RolledBackJournal
        journal = journal_type(canonical_json_bytes(value.get('journal')))
        data = journal.data
        require(data['project_id'] == project_id, 'restore_historical_project_conflict', exit_code=6)
        require(path == transaction_receipt_path(data['transaction_id']),
                'restore_recovery_receipt_path_mismatch', exit_code=6)

        def original(name):
            require(name in files, 'restore_recovery_original_missing', path=name, exit_code=6)
            retained[name] = files[name]
            return EvidenceRecord(name, files[name])

        if value['action'] == 'discard':
            root = data['discard']['audit_path']
            before = original(root + '/journal.before.json')
            state = parse_json_object(before.source_bytes).get('state')
            require(state in ('building', 'prepared'), 'restore_recovery_original_state_invalid')
            source = (BuildingJournal if state == 'building' else PreparedJournal)(before.source_bytes)
            intent = original(root + '/intent.json')
            validate_discard_originals(journal, source, intent)
            completion = discard_completion_record(journal, source, intent)
            require(original(completion.path).source_bytes == completion.source_bytes,
                    'restore_recovery_completion_mismatch', path=completion.path, exit_code=6)
            prefix = root + '/work/'
            work = {p[len(prefix):]: b for p, b in files.items() if p.startswith(prefix)}
            require(work.get('journal.json') == journal.source_bytes,
                    'restore_recovery_original_missing', path=prefix + 'journal.json', exit_code=6)
            # The original intent binds all actual pre-discard work, including
            # short interrupted images. The terminal journal is the sole swap.
            observed = [file_row(p, source.source_bytes if p == 'journal.json' else b)
                        for p, b in sorted(work.items())]
            require(observed == parse_json_object(intent.source_bytes).get('work_files'),
                    'restore_recovery_work_inventory_mismatch', exit_code=6)
            retained.update({prefix + p: b for p, b in work.items()})
            audit = intent
        else:
            audit = original(evidence_root(data['transaction_id']) + '/rollback.json')
            observed = parse_json_object(audit.source_bytes)
            expected = _action_fields(journal, 'rollback')
            require(set(observed) == set(expected) | {'authority_id', 'authority_version'}
                    and all(observed.get(k) == v for k, v in expected.items())
                    and all(type(observed[k]) is str and observed[k].strip()
                            for k in ('authority_id', 'authority_version')),
                    'restore_recovery_audit_mismatch', path=audit.path, exit_code=6)
        require(raw == rollback_receipt(journal, audit, action=value['action']).source_bytes,
                'restore_recovery_receipt_mismatch', path=path, exit_code=6)
        retained[path] = raw
    return retained
