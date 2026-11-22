"""Review JSON, independent coverage oracles and real owned file effects; no UI tests."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from reviews import reviewlib as review


def module_value():
    return dict(format_version=1, id='example', title='Synthetic acceptance', purpose='Test evidence only',
        source=dict(kind='synthetic', reference='owned test', note='Not a real human review'),
        minimum_reviewers=1, criteria=['Check the original.'],
        sections=[dict(id='one', title='Part one', attestation='I can review this part.'),
                  dict(id='two', title='Part two', attestation='I can review the other part.')],
        items=[dict(id='a', section='one', title='First', text='Original Ω text', criteria=[], required_note=False, metadata={}),
               dict(id='b', section='two', title='Second', text='Another original', criteria=['Check provenance.'],
                    required_note=True, metadata={'kind': 'synthetic'})])


def independent_hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()).hexdigest()


def binding(module, item):
    return independent_hash(dict(format_version=1, module_id=module['id'], title=module['title'], purpose=module['purpose'],
        source=module['source'], minimum_reviewers=module['minimum_reviewers'], criteria=module['criteria'],
        section=next(s for s in module['sections'] if s['id'] == item['section']), item=item))


def record(module, *, item=0, email='reviewer@example.test', verdict='accept', note='', number=1):
    selected = module['items'][item]
    return dict(format_version=1, id=str(uuid.UUID(int=number)), module_id=module['id'],
        module_sha256=independent_hash(module), reviewer=dict(name='Synthetic Reviewer', email=email),
        created_at=f'2026-11-20T12:00:{number:02d}Z', publication_consent=True, personal_review=True,
        attestations=[selected['section']], decisions=[dict(item_id=selected['id'], item_sha256=binding(module, selected),
            verdict=verdict, note=note, proposed_text='')])


def store(root, module, records=()):
    (root / 'modules').mkdir(parents=True)
    (root / 'results' / module['id']).mkdir(parents=True)
    (root / 'modules' / (module['id'] + '.json')).write_bytes(review.canonical(module))
    for item in records:
        (root / 'results' / module['id'] / (item['id'] + '.json')).write_bytes(review.canonical(item))
    return root


def test_initially_open_with_no_invented_human_or_release_evidence():
    m = module_value()
    result = review.assess(m, [])
    assert (result['total'], result['accepted'], result['open']) == (2, 0, 2)
    assert not result['review_coverage_complete'] and not result['release_accepted']
    assert result['stale'] == []
    assert all(row['status'] == 'pending' and row['reviews'] == [] for row in result['items'])


def test_multiple_reviewers_and_partial_reviews_remain_independent():
    m = module_value()
    r = [record(m), record(m, email='second@example.test', number=2)]
    before = deepcopy(r)
    value = review.assess(m, r)
    assert value['accepted'] == 1 and value['open'] == 1
    assert value['items'][0]['approvals'] == 2 and len(value['items'][0]['reviews']) == 2
    assert r == before


def test_same_email_cannot_fill_two_reviewer_quorum():
    m = module_value()
    m['minimum_reviewers'] = 2
    value = review.assess(m, [record(m), record(m, email='REVIEWER@example.test', number=2)])
    assert value['items'][0]['approvals'] == 1 and value['accepted'] == 0


@pytest.mark.parametrize('verdict', ['reject', 'correct'])
def test_one_unresolved_objection_keeps_item_open(verdict):
    m = module_value()
    value = review.assess(m, [record(m), record(m, email='second@example.test', number=2, verdict=verdict, note='Concrete issue')])
    assert value['items'][0]['status'] == 'changes_requested' and value['accepted'] == 0


def test_complete_review_coverage_never_invents_release_acceptance():
    m = module_value()
    value = review.assess(m, [record(m), record(m, item=1, number=2, note='Explicit evidence')])
    assert value['review_coverage_complete'] and value['accepted'] == 2 and value['open'] == 0
    assert value['release_accepted'] is False


@pytest.mark.parametrize('change', ['text', 'criteria', 'source', 'attestation', 'minimum_reviewers'])
def test_changed_subject_or_criteria_makes_evidence_stale(change):
    m = module_value()
    r = record(m)
    if change == 'text':
        m['items'][0]['text'] += '!'
    elif change == 'criteria':
        m['criteria'].append('One more requirement.')
    elif change == 'source':
        m['source']['reference'] = 'Changed provenance'
    elif change == 'attestation':
        m['sections'][0]['attestation'] += ' Also check the evidence.'
    else:
        m['minimum_reviewers'] = 2
    value = review.assess(m, [r])
    assert value['accepted'] == 0 and value['stale'] == [dict(review_id=r['id'], item_id='a')]


def test_unrelated_item_change_retains_exact_unchanged_item_evidence():
    m = module_value()
    r = record(m)
    m['items'][1]['text'] += '!'
    value = review.assess(m, [r])
    assert value['accepted'] == 1 and value['stale'] == []
    assert value['module_sha256'] != r['module_sha256']


@pytest.mark.parametrize('field', ['publication_consent', 'personal_review'])
@pytest.mark.parametrize('value', [False, 1, None, 'true'])
def test_personal_confirmations_are_explicit_true_booleans(field, value):
    m = module_value()
    r = record(m)
    r[field] = value
    with pytest.raises(review.ReviewError):
        review.assess(m, [r])


def test_section_competence_and_required_note_cannot_be_omitted():
    m = module_value()
    r = record(m)
    r['attestations'] = ['two']
    with pytest.raises(review.ReviewError):
        review.assess(m, [r])
    with pytest.raises(review.ReviewError):
        review.assess(m, [record(m, item=1)])


def test_second_module_needs_only_data_and_results_are_separate(tmp_path):
    m = module_value()
    root = store(tmp_path / 'reviews', m, [record(m)])
    second = deepcopy(m)
    second['id'] = 'another-acceptance'
    (root / 'modules/another-acceptance.json').write_bytes(review.canonical(second))
    modules, reports = review.load_repository(root)
    assert set(modules) == {'example', 'another-acceptance'}
    assert {r['module_id']: r['accepted'] for r in reports} == {'example': 1, 'another-acceptance': 0}
    with pytest.raises(review.ReviewError):
        review.assess(second, [record(m)])


@pytest.mark.parametrize('raw', [b'{"id":1,"id":2}', b'{"nested":{"a":1,"a":2}}', b'NaN', b'Infinity', b'\xff'])
def test_strict_json_input(raw):
    with pytest.raises(review.ReviewError):
        review.decode(raw)


@pytest.mark.parametrize('location', ['module', 'results', 'summary'])
def test_linked_inputs_or_output_cannot_read_or_replace_foreign_file(tmp_path, location):
    root = store(tmp_path / 'reviews', module_value())
    outside = tmp_path / 'outside'
    outside.write_text('Unchanged foreign bytes')
    if location == 'module':
        target = root / 'modules/example.json'
        target.unlink()
        target.symlink_to(outside)
    elif location == 'results':
        (root / 'results/example').rmdir()
        (root / 'results/example').symlink_to(tmp_path, target_is_directory=True)
    else:
        (root / 'README.md').symlink_to(outside)
    with pytest.raises(review.ReviewError):
        review.run(root, 'summary')
    assert outside.read_text() == 'Unchanged foreign bytes'


def test_malformed_result_preserves_existing_summary_and_all_input_bytes(tmp_path):
    m = module_value()
    r = record(m)
    root = store(tmp_path / 'reviews', m, [r])
    (root / 'README.md').write_bytes(b'Previous valid report')
    path = root / 'results/example' / (r['id'] + '.json')
    path.write_bytes(b'{broken')
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    with pytest.raises(review.ReviewError):
        review.run(root, 'summary')
    assert before == {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_cli_works_without_installed_specroad_and_only_changes_summary(tmp_path):
    m = module_value()
    root = store(tmp_path / 'reviews', m, [record(m)])
    source = Path(__file__).resolve().parents[1] / 'reviews'
    for path in source.glob('*.py'):
        (root / path.name).write_bytes(path.read_bytes())
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    command = [sys.executable, '-I', '-B', str(root / 'manage.py')]
    valid = subprocess.run(command + ['validate'], capture_output=True, check=True)
    assert json.loads(valid.stdout)['modules'][0]['accepted'] == 1
    assert not (root / 'README.md').exists()
    value = subprocess.run(command + ['summary'], capture_output=True, check=True)
    assert json.loads(value.stdout)['valid']
    assert (root / 'README.md').is_file()
    assert all((root / p).read_bytes() == raw for p, raw in before.items())
    assert {p.relative_to(root) for p in root.rglob('*') if p.is_file()} == set(before) | {Path('README.md')}


def test_first_module_preserves_all_candidate_text_bytes_and_no_human_results():
    path = Path(__file__).resolve().parents[1] / 'reviews/modules/language-corpus.json'
    m = review.validate_module(review.decode(path.read_bytes()))
    language_items = [i for i in m['items'] if i['section'] != 'provenance']
    assert len(language_items) == 225
    assert len({i['id'] for i in m['items']}) == 226
    for label in ('de', 'en', 'hi', 'id', 'pt', 'es', 'ru', 'ja', 'zh'):
        cases = [i for i in language_items if i['section'] == label]
        assert len(cases) == 25 and len({i['text'] for i in cases}) == 25
        assert sum(i['metadata']['partition'] == 'long' for i in cases) == 20
        for i in cases:
            assert sha256(i['text'].encode()).hexdigest() == i['metadata']['text_sha256']
            assert i['metadata']['intended_language'] == label
            if i['metadata']['partition'] == 'long':
                assert 80 <= len(i['text']) <= 500
    assert review.assess(m, [])['accepted'] == 0


def test_review_sources_participate_in_gate_identity_and_remote_snapshot(tmp_path):
    from verification_support.identity import source_identity
    from dev.test_hosts.snapshot import inventory
    for directory in ('src/specroad', 'tests', 'tools', 'verification', 'reviews'):
        (tmp_path / directory).mkdir(parents=True)
    (tmp_path / 'pyproject.toml').write_text('')
    target = tmp_path / 'reviews/data.json'
    target.write_text('{"value":1}')
    before = source_identity(tmp_path)
    assert 'reviews/data.json' in inventory(tmp_path)
    target.write_text('{"value":2}')
    assert source_identity(tmp_path) != before
