"""R-02/R-03 exact normative metadata vectors through the actual native writer."""
import json
import pytest
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.changes.receipt_values import transaction_receipt_path
from specroad.changes.write_guard_values import validate_transaction
from support.merge_publication import seed, setup, apply, normative
from support.merge_target import replace


@pytest.mark.parametrize('combined', [False, True], ids=['adopt-seven', 'combine-three-seven'])
def test_exact_three_seven_vector_reaches_disk_receipt_and_idempotent_retry(tmp_path, combined):
    files = seed(tmp_path / 'seed')
    path = next(p for p in files if p.startswith('spec/goals/'))
    base = json.loads(files[path])
    base.update(revision=1, updated_at='2026-01-01T00:00:00Z')
    files[path] = jcs(base)
    ours = replace(files, 'goal', title='Ours', revision=3, updated_at='2026-02-01T00:00:00Z') if combined else files
    theirs = replace(files, 'goal', statement='Theirs', revision=7, updated_at='2026-03-01T00:00:00Z')
    root, plan, args, target = setup(tmp_path, variants=[files, ours, theirs],
                                   fields={'planned_at': '2026-04-01T00:00:00Z'})
    result = apply(root, plan, args)
    actual = json.loads((root / path).read_bytes())
    assert actual['revision'] == (8 if combined else 7)
    assert actual['updated_at'] == ('2026-03-01T00:00:00.000001Z' if combined else '2026-03-01T00:00:00Z')
    assert actual['created_at'] == base['created_at'] and actual['created_by'] == base['created_by']
    assert actual['title'] == ('Ours' if combined else base['title']) and actual['statement'] == 'Theirs'
    if not combined: assert (root / path).read_bytes() == theirs[path]
    assert normative(root) == target.files
    assert result['write_state'] == 'committed' and result['current_target_verified']
    receipt = (root / transaction_receipt_path(args['transaction_id'])).read_bytes()
    record = validate_transaction(receipt)
    assert any(row['path'] == path for row in record['files'])
    before = normative(root)
    retry = apply(root, plan, args)
    assert retry['replayed'] and normative(root) == before
    assert (root / transaction_receipt_path(args['transaction_id'])).read_bytes() == receipt
