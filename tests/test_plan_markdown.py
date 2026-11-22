"""21.b.W: real plan source bytes and independently specified data oracles."""
import json
from hashlib import sha256
import pytest
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.storage.plan_markdown import parse_plan
from specroad.storage.plan_edits import SourceEdit
from support.plan_models import PLAN, ENTRY, plan, entry
from support.plan_sources import block, metadata, small_source, project, token
from support.read_only import inventory, no_write_attempts


def test_two_real_carriers_have_one_owned_manifest_each_and_no_shadow_files(tmp_path):
    other = 'SR-IPLAN-' + token(21)
    raw, expected_plan, expected_entry = small_source()
    second, second_plan, second_entry = small_source(plan_id=other, label='نطاق', title='תכנית')
    second_entry['id'] = 'SR-PENTRY-' + token(22)
    second_entry['parent_relation_id'] = 'REL-' + token(24)
    second_plan['children'] = [second_entry['id']]
    second = second.replace(ENTRY.encode(), second_entry['id'].encode()).replace(
        ('REL-' + token(2)).encode(), second_entry['parent_relation_id'].encode())
    source = project(tmp_path, {PLAN: raw, other: second})
    before = inventory(tmp_path)
    with no_write_attempts():
        for identity, data, expected in ((PLAN, raw, [expected_plan, expected_entry]),
                (other, second, [second_plan, second_entry])):
            path = 'spec/implementation-plans/' + identity + '.md'
            result = source.read_plan(path)
            assert result.source_bytes == data and result.file_sha256 == sha256(data).hexdigest()
            assert [p.data for p in result.projections] == expected
            assert result.resource_manifest == {'path': path, 'file_sha256': sha256(data).hexdigest(),
                'artifacts': [{'id': v['id'], 'sha256': canonical_json_sha256(v)} for v in expected]}
            source.check_plan_current(result)
            assert result.replace_fields({}, expected_file_sha256=result.file_sha256).source_bytes == data
    assert inventory(tmp_path) == before
    assert not list((tmp_path/'spec/implementation-plans').glob('*.json'))


def test_full_fields_remain_typed_and_optional_missing_values_stay_missing():
    p, e = plan(), entry()
    p['children'] = [ENTRY]
    e.update(notes=['Explicit parent note'], acceptance_criteria=['A genuine result'],
        expected_scope={'files': ['src/component.py'], 'symbols': ['build']}, phase='verify',
        required=False, commit_refs=[{'commit': 'abc', 'repository': 'literal'}],
        commit_message_template='{display_id} {title}', extensions={'example.org:extra': {'value': 2}})
    raw = block('# [21] Plan', p, 'Description\n') + block('- [x] [21.a.W] Deliver', e, 'body\n', indent=2)
    result = parse_plan(raw)
    expected = {**e, 'title': 'Deliver', 'implemented': True, 'description': 'body\n'}
    assert result.projections[1].data == expected
    assert 'notes' not in result.projections[0].data and 'required' not in result.projections[0].data
    assert result.projections[1].data['maturity'] == 'draft'
    result.projections[1].data['notes'].append('outside mutation')
    assert result.projections[1].data == expected


def test_heading_gaps_and_unbounded_list_depth_use_only_real_parents():
    p = plan()
    pieces = [block('# [21] Plan', p)]
    values = []
    for index, level in enumerate((2, 5, 3)):
        e = entry(); e.update(id='SR-PENTRY-' + token(index+1), parent_relation_id='REL-' + token(index+1))
        pieces.append(block('#'*level + ' [ ] [H' + str(index) + '] Section', e))
        values.append(e['id'])
    for index in range(12):
        e = entry(); e.update(id='SR-PENTRY-' + token(index+4), parent_relation_id='REL-' + token(index+4))
        pieces.append(block('  '*index + '- [x] [L'+str(index)+'] Deep', e, indent=index*2+2))
        values.append(e['id'])
    result = parse_plan(b''.join(pieces))
    by_id = {p.data['id']: p.data for p in result.projections}
    assert by_id[PLAN]['children'] == [values[0]]
    assert by_id[values[0]]['children'] == values[1:3]
    assert by_id[values[1]]['children'] == []
    assert by_id[values[2]]['children'] == [values[3]]
    for parent, child in zip(values[3:], values[4:]):
        assert by_id[parent]['children'] == [child]
        assert by_id[child]['parent_id'] == parent and by_id[child]['plan_id'] == PLAN
    assert by_id[values[-1]]['children'] == [] and len(result.sections) == 16


@pytest.mark.parametrize('wrapper', ['fence', 'tilde', 'quote', 'indent', 'comment'])
def test_code_quote_and_comment_examples_do_not_create_objects(wrapper):
    raw, _, _ = small_source()
    example = block('## [x] [example] Invisible', entry(), 'payload\n')
    if wrapper == 'fence': example = b'````markdown\n' + example + b'````\n'
    if wrapper == 'tilde': example = b'~~~example\n' + example + b'~~~\n'
    if wrapper == 'quote': example = b''.join(b'> '+line for line in example.splitlines(keepends=True))
    if wrapper == 'indent': example = b''.join(b'    '+line for line in example.splitlines(keepends=True))
    if wrapper == 'comment': example = b'<!--\n' + example + b'-->\n'
    complete = raw + example + b'\n- [x] [unstructured] No metadata\n'
    parsed = parse_plan(complete)
    assert len(parsed.sections) == 2
    assert parsed.projections[-1].data['description'] == ('Commit prose.\n' + example.decode() + '\n- [x] [unstructured] No metadata\n')
    assert parsed.replace_fields({}, expected_file_sha256=parsed.file_sha256).source_bytes == complete


def test_field_changes_preserve_all_unrequested_source_spans_and_identity():
    raw, _, _ = small_source(description='<!-- untouched -->\n\nOrdinary text\n\n')
    parsed = parse_plan(raw)
    altered = parsed.replace_fields({ENTRY: {'title': 'Renamed', 'display_id': '99', 'implemented': True}},
        expected_file_sha256=parsed.file_sha256)
    assert altered.source_bytes == raw.replace(b'## [ ] [A] Build feature\n', b'## [x] [99] Renamed\n')
    assert altered.projections[1].data['id'] == ENTRY
    assert altered.projections[0].sha256 == parsed.projections[0].sha256
    assert altered.projections[1].sha256 != parsed.projections[1].sha256
    assert altered.file_sha256 != parsed.file_sha256
    assert altered.revision_diagnostics() == ()
    assert [r['artifact_id'] for r in altered.revision_diagnostics(parsed)] == [ENTRY]
    assert altered.revision_diagnostics(parsed)[0]['code'] == 'SRV206'


def test_manual_edits_are_next_read_truth_without_mutating_old_observation(tmp_path):
    raw, _, _ = small_source()
    source = project(tmp_path, {PLAN: raw})
    path = 'spec/implementation-plans/' + PLAN + '.md'
    original = source.read_plan(path)
    changed = raw.replace(b'Build feature', 'مصادقة'.encode())
    (tmp_path/path).write_bytes(changed)
    before = inventory(tmp_path)
    with no_write_attempts():
        current = source.read_plan(path)
        with pytest.raises(ModelError, match='plan_source_changed'): source.check_plan_current(original)
    assert original.source_bytes == raw and current.source_bytes == changed
    assert current.projections[1].data['title'] == 'مصادقة'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('replacement,reason', [
    (b'{"x":1,"x":2}', 'duplicate_key'), (b'{"x":NaN}', 'nonfinite_number'),
    (b'[]', 'object_required'), (b'{} {}', 'invalid_json'),
    (b'{"extra":true}', 'artifact_type_mismatch')])
def test_bad_metadata_is_localized_and_never_yields_a_partial_plan(replacement, reason):
    raw, _, _ = small_source(description='תיאור\n')
    first = raw.index(b'```specroad-entry-v1\n') + len(b'```specroad-entry-v1\n')
    last = raw.index(b'```\n', first)
    invalid = raw[:first] + replacement + b'\n' + raw[last:]
    with pytest.raises(ModelError) as caught: parse_plan(invalid, path='spec/implementation-plans/'+PLAN+'.md')
    error = caught.value
    assert error.reason == reason
    assert error.line == invalid[:first].count(b'\n') + 1
    assert error.column >= 1 and error.position >= first
    assert error.path.endswith(PLAN+'.md')
    assert replacement.decode() not in str(error)


@pytest.mark.parametrize('change,reason', [
    ('status', 'plan_invalid_header'), ('orphan', 'plan_orphan_metadata'),
    ('unclosed', 'plan_unclosed_metadata'), ('crlf', 'plan_lf_required'),
    ('bom', 'plan_bom_forbidden'), ('utf8', 'invalid_utf8'), ('duplicate', 'duplicate_plan_heading')])
def test_malformed_structures_are_visible(change, reason):
    raw, _, _ = small_source()
    if change == 'status': raw = raw.replace(b'## [ ]', b'## [X]')
    if change == 'orphan': raw += b'```specroad-entry-v1\n{}\n```\n'
    if change == 'unclosed': raw = raw[:raw.rindex(b'```\n')]
    if change == 'crlf': raw = raw.replace(b'\n', b'\r\n')
    if change == 'bom': raw = b'\xef\xbb\xbf' + raw
    if change == 'utf8': raw += b'\xff'
    if change == 'duplicate': raw += block('# [other] Other', plan())
    with pytest.raises(ModelError, match=reason) as caught: parse_plan(raw)
    assert caught.value.line >= 1 and caught.value.column >= 1


def test_spans_require_exact_bytes_binding_ownership_and_nonoverlap():
    raw, _, _ = small_source()
    result = parse_plan(raw)
    span = result.sections[1].title
    valid = SourceEdit(span.start, span.end, span.read(raw), b'Changed')
    assert result.replace_spans([valid], expected_file_sha256=result.file_sha256).source_bytes == raw.replace(b'Build feature', b'Changed')
    for edits, expected, reason in (([valid], '0'*64, 'plan_source_changed'),
        ([SourceEdit(span.start, span.end, b'incorrect', b'Changed')], result.file_sha256, 'plan_edit_preimage_mismatch'),
        ([valid, valid], result.file_sha256, 'plan_edits_overlap'),
        ([SourceEdit(0, len(raw), raw, raw)], result.file_sha256, 'plan_edit_outside_spans')):
        with pytest.raises(ModelError, match=reason): result.replace_spans(edits, expected_file_sha256=expected)
    assert result.source_bytes == raw


def test_derived_duplicates_must_match_real_structure_and_unknown_fields_fail():
    p = plan(); p['title'] = 'Plan'; p['description'] = ''; p['children'] = []
    original = block('# [21] Plan', p, encoded=json.dumps(p))
    assert parse_plan(original).projections[0].data == p
    for field, value in (('title','wrong'), ('children',[ENTRY]), ('description','not here')):
        changed = dict(p); changed[field] = value
        with pytest.raises(ModelError, match='plan_derived_field_conflict'):
            parse_plan(block('# [21] Plan', p, encoded=json.dumps(changed)))
    changed = metadata(p); changed['unknown_core_field'] = True
    with pytest.raises(ModelError, match='unknown_field'):
        parse_plan(block('# [21] Plan', p, encoded=json.dumps(changed)))


def test_context_hash_excludes_checkbox_revision_audit_and_maturity_but_not_content():
    raw, _, _ = small_source()
    source = parse_plan(raw)
    changed = source.replace_fields({ENTRY: {'implemented': True, 'revision': 2, 'maturity': 'proposed'}},
        expected_file_sha256=source.file_sha256)
    assert changed.context_sha256(ENTRY) == source.context_sha256(ENTRY)
    assert changed.projections[1].sha256 != source.projections[1].sha256
    assert not changed.revision_diagnostics(source)
    assert changed.projections[0].sha256 == source.projections[0].sha256
    content = changed.replace_fields({ENTRY: {'description': 'Changed text\n'}}, expected_file_sha256=changed.file_sha256)
    assert content.context_sha256(ENTRY) != changed.context_sha256(ENTRY)
    assert canonical_json_bytes(source.projections[1].data) != canonical_json_bytes(content.projections[1].data)
