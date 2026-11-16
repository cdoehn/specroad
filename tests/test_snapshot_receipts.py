"""Real v2 snapshot receipts retain read-only qualification and closed bindings."""
import json
import pytest

from specroad.changes.receipt_values import RequestReceipt, request_receipt_path
from specroad.model.canonical import canonical_json_bytes
from specroad.qualification.project import project_bytes
from specroad.qualification.receipts import receipt_history, check_receipt_targets
from specroad.qualification.errors import QualificationError
from support.read_only import inventory, no_write_attempts
from test_snapshot_guard import scenario, FAILURES


def bytes_in(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('kind', ['migration', 'merge'])
def test_current_snapshot_with_real_v2_receipts_is_natively_qualified(tmp_path, kind):
    root, source, plan, args, target, apply = scenario(tmp_path, kind)
    apply(root, plan, args)
    request = RequestReceipt((root/request_receipt_path(plan.data['request_id'])).read_bytes())
    assert request.data['format_version'] == 'request-receipt-v2'
    assert request.data['result_object']['published_paths'] == sorted(
        row['path'] for row in plan.data['operations'][0]['changes'])
    before = inventory(root)
    with no_write_attempts():
        model, digest = project_bytes(bytes_in(root))
    assert digest == plan.data['expected_result']['model_root_sha256']
    assert inventory(root) == before


@pytest.mark.parametrize('damage', ['resurrect_deleted', 'remove_written', 'replace_registry'])
def test_native_receipt_lineage_rejects_unproven_target_images(tmp_path, damage):
    root, source, plan, args, target, apply = scenario(tmp_path, 'migration')
    apply(root, plan, args)
    current = bytes_in(root)
    _, journals = receipt_history(current, json.loads(target['specroad.json'])['project_id'])
    with no_write_attempts():
        check_receipt_targets(journals, current)
    changed = dict(current)
    if damage == 'resurrect_deleted':
        path = next(p for p in source if p not in target)
        changed[path] = source[path]
    elif damage == 'remove_written':
        path = next(p for p in target if p.startswith('spec/') and target[p] != source.get(p))
        changed.pop(path)
    else:
        path = json.loads(target['specroad.json'])['language_registry']['path']
        changed[path] += b'changed after receipt'
    before = inventory(root)
    with no_write_attempts(), pytest.raises(QualificationError):
        check_receipt_targets(journals, changed)
    assert inventory(root) == before


@pytest.mark.parametrize('path', [
    '.specroad/write-state/pending.json', '../escape.json', '/absolute.json',
    'unmanaged/foreign.json', 'profiles/language-data/unbound.txt',
])
def test_request_path_claim_cannot_replace_native_snapshot_proof(tmp_path, path):
    root, source, plan, args, target, apply = scenario(tmp_path, 'migration')
    apply(root, plan, args)
    receipt = root/request_receipt_path(plan.data['request_id'])
    value = json.loads(receipt.read_bytes())
    value['result_object']['published_paths'] = [path]
    receipt.write_bytes(canonical_json_bytes(value))
    before = inventory(root)
    if path != 'profiles/language-data/unbound.txt':
        with pytest.raises(FAILURES): RequestReceipt(receipt.read_bytes())
    with no_write_attempts(), pytest.raises(FAILURES):
        apply(root, plan, args)
    assert inventory(root) == before
