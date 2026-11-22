"""Adversarial evidence and filesystem boundaries, never presentation assertions."""
from copy import deepcopy
import os

import pytest

from reviews import reviewlib as review
from test_repository_reviews import module_value, record, store


def replacement(module, old, *, verdict='accept', number=2):
    value = record(module, number=number, verdict=verdict, note='Rechecked the original evidence')
    value['decisions'][0]['supersedes'] = [old['id']]
    return value


def test_personal_supersession_resolves_objection_but_retains_both_records():
    m = module_value()
    old = record(m, verdict='correct', note='Check the meaning')
    new = replacement(m, old)
    value = review.assess(m, [new, old])
    assert value['accepted'] == 1
    rows = value['items'][0]['reviews']
    assert len(rows) == 2
    assert {r['review_id']: r['superseded'] for r in rows} == {old['id']: True, new['id']: False}
    assert old['decisions'][0]['verdict'] == 'correct'


def test_superseding_one_reviewer_never_removes_another_objection():
    m = module_value()
    old = record(m, verdict='reject', note='First concern')
    other = record(m, email='other@example.test', number=3, verdict='reject', note='Independent concern')
    value = review.assess(m, [old, other, replacement(m, old)])
    assert value['items'][0]['status'] == 'changes_requested'


@pytest.mark.parametrize('fault', ['other-person', 'self', 'missing', 'same-time', 'backward-time', 'different-item', 'different-hash', 'duplicate-link'])
def test_invalid_supersession_is_never_a_pass(fault):
    m = module_value()
    old = record(m)
    new = replacement(m, old)
    if fault == 'other-person':
        new['reviewer']['email'] = 'someone-else@example.test'
    elif fault == 'self':
        new['decisions'][0]['supersedes'] = [new['id']]
    elif fault == 'missing':
        new['decisions'][0]['supersedes'] = [record(m, number=3)['id']]
    elif fault == 'same-time':
        new['created_at'] = old['created_at']
    elif fault == 'backward-time':
        new['created_at'] = '2026-11-19T01:00:00Z'
    elif fault == 'different-item':
        old = record(m, item=1, note='Evidence')
    elif fault == 'different-hash':
        old['decisions'][0]['item_sha256'] = '0' * 64
    else:
        new['decisions'][0]['supersedes'] *= 2
    with pytest.raises(review.ReviewError):
        review.assess(m, [old, new])


def test_supersession_chain_can_withdraw_a_previous_approval():
    m = module_value()
    first = record(m)
    second = replacement(m, first)
    last = replacement(m, second, number=3, verdict='reject')
    value = review.assess(m, [last, first, second])
    assert value['items'][0]['status'] == 'changes_requested'
    assert value['items'][0]['approvals'] == 0
    assert len(value['items'][0]['reviews']) == 3


@pytest.mark.parametrize('path,value', [
    (('format_version',), True), (('minimum_reviewers',), True), (('minimum_reviewers',), 0),
    (('minimum_reviewers',), 101), (('id',), '../outside'), (('id',), 'UPPER'),
    (('items', 0, 'section'), []), (('items', 0, 'required_note'), 1),
    (('items', 0, 'text'), '\ud800'), (('items', 0, 'metadata'), {'field': {}}),
    (('sections', 0, 'id'), '../part'), (('criteria',), ['Same', 'Same']),
    (('source', 'kind'), None), (('items',), []), (('sections',), []),
])
def test_module_contract_is_closed_and_strict(path, value):
    module = module_value()
    owner = module
    for part in path[:-1]:
        owner = owner[part]
    owner[path[-1]] = value
    with pytest.raises(review.ReviewError):
        review.validate_module(module)


@pytest.mark.parametrize('path,value', [
    (('format_version',), 1.0), (('id',), 'not-uuid'), (('reviewer', 'name'), ''),
    (('reviewer', 'email'), 'missing-at'), (('reviewer', 'email'), 'a@b.test\nInjected'),
    (('created_at',), '2026-99-99T00:00:00Z'), (('created_at',), '2026-11-20T00:00:00+00:00'),
    (('module_sha256',), 'A' * 64), (('decisions', 0, 'verdict'), 'approve'),
    (('decisions', 0, 'proposed_text'), 'Unrequested replacement'),
    (('decisions', 0, 'supersedes'), ['not-uuid']), (('attestations',), []),
])
def test_malformed_evidence_is_rejected(path, value):
    m = module_value()
    r = record(m)
    owner = r
    for part in path[:-1]:
        owner = owner[part]
    owner[path[-1]] = value
    with pytest.raises(review.ReviewError):
        review.assess(m, [r])


def test_duplicate_records_and_duplicate_decisions_are_errors():
    m = module_value()
    r = record(m)
    with pytest.raises(review.ReviewError):
        review.assess(m, [r, deepcopy(r)])
    r['decisions'] += deepcopy(r['decisions'])
    with pytest.raises(review.ReviewError):
        review.assess(m, [r])


@pytest.mark.parametrize('fault', ['unknown-key', 'duplicate-item', 'duplicate-section', 'empty-section'])
def test_ambiguous_module_inventory_is_rejected(fault):
    m = module_value()
    if fault == 'unknown-key':
        m['execute'] = 'arbitrary code'
    elif fault == 'duplicate-item':
        m['items'] += deepcopy(m['items'])
    elif fault == 'duplicate-section':
        m['sections'] += deepcopy(m['sections'])
    else:
        m['sections'].append(dict(id='empty', title='Empty', attestation='Not reviewed'))
    with pytest.raises(review.ReviewError):
        review.assess(m, [])


def test_deleted_item_evidence_is_retained_as_stale():
    m = module_value()
    r = record(m)
    m['items'] = m['items'][1:]
    m['sections'] = m['sections'][1:]
    value = review.assess(m, [r])
    assert value['accepted'] == 0 and len(value['stale']) == 1


def test_record_path_and_module_identity_must_match(tmp_path):
    m = module_value()
    r = record(m)
    root = store(tmp_path / 'reviews', m, [r])
    path = root / 'results/example' / (r['id'] + '.json')
    path.rename(path.with_name('arbitrary.json'))
    with pytest.raises(review.ReviewError):
        review.load_repository(root)


@pytest.mark.parametrize('kind', ['hardlink', 'fifo', 'linked-parent', 'oversized'])
def test_unsafe_file_inputs_are_refused_without_consuming_streams(tmp_path, kind):
    p = tmp_path / 'input.json'
    p.write_bytes(b'{}')
    if kind == 'hardlink':
        os.link(p, tmp_path / 'alias')
    elif kind == 'fifo':
        p.unlink()
        os.mkfifo(p)
    elif kind == 'linked-parent':
        (tmp_path / 'alias').symlink_to(tmp_path, target_is_directory=True)
        p = tmp_path / 'alias/input.json'
    else:
        with p.open('wb') as stream:
            stream.truncate(review.MAX_BYTES + 1)
    with pytest.raises(review.ReviewError):
        review.read_file(p)


def test_summary_publication_failure_preserves_old_bytes_and_cleans_temp(tmp_path, monkeypatch):
    root = store(tmp_path / 'reviews', module_value())
    (root / 'README.md').write_bytes(b'previous version')
    def fail_replace(*args):
        raise OSError('Injected before atomic replacement')
    monkeypatch.setattr(os, 'replace', fail_replace)
    with pytest.raises(OSError):
        review.run(root, 'summary')
    assert (root / 'README.md').read_bytes() == b'previous version'
    assert not list(root.glob('.summary-*'))


def test_malformed_input_can_never_clear_old_summary(tmp_path):
    root = store(tmp_path / 'reviews', module_value())
    (root / 'README.md').write_bytes(b'previous version')
    (root / 'results/unknown').mkdir()
    with pytest.raises(review.ReviewError):
        review.run(root, 'summary')
    assert (root / 'README.md').read_bytes() == b'previous version'


def test_source_binding_rejects_linked_review_tree(tmp_path):
    from verification_support.identity import source_identity
    from verification_support.common import CatalogError
    from dev.test_hosts.snapshot import inventory
    for name in ('src/specroad', 'tests', 'tools', 'verification'):
        (tmp_path / name).mkdir(parents=True)
    (tmp_path / 'pyproject.toml').write_text('')
    (tmp_path / 'reviews').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(CatalogError):
        source_identity(tmp_path)
    with pytest.raises(ValueError):
        inventory(tmp_path)
