"""21.b.R: adversarial carriers, minimal edits and current native read boundaries."""
import json
import pytest
from specroad.model.errors import ModelError
from specroad.storage.plan_markdown import parse_plan
from specroad.storage.plan_edits import SourceEdit
from specroad.security import SafetyViolation
from support.plan_models import PLAN, ENTRY, plan, entry
from support.plan_sources import block, metadata, small_source, project, token
from support.read_only import inventory, no_write_attempts


def test_unicode_offsets_are_bytes_and_columns_are_characters():
    raw, _, _ = small_source(title='תכנית 😀', entry_title='تطبيق 日本語 😀')
    parsed = parse_plan(raw)
    section = parsed.sections[1]
    assert section.title.read(raw) == 'تطبيق 日本語 😀'.encode()
    assert section.display_id.read(raw) == b'A' and section.checkbox.read(raw) == b' '
    changed = parsed.replace_fields({ENTRY: {'title': 'מימוש é', 'display_id': 'س١'}},
        expected_file_sha256=parsed.file_sha256)
    assert changed.source_bytes == raw.replace('## [ ] [A] تطبيق 日本語 😀'.encode(), '## [ ] [س١] מימוש é'.encode())
    assert changed.projections[1].data['id'] == ENTRY
    # Display identifiers are NFC; literal title text is not normalized.
    with pytest.raises(ModelError, match='invalid_plan_display_id'):
        parsed.replace_fields({ENTRY: {'display_id': 'é'}}, expected_file_sha256=parsed.file_sha256)


def test_list_description_preserves_unicode_line_separators_and_white_lines():
    raw = block('# [P] Plan', plan()) + block('- [ ] [A] Entry', entry(), 'RTL: שלום\u2028عربي\u2029終\n\n \nEnd', indent=2)
    assert raw.endswith('  RTL: שלום\u2028عربي\u2029終\n\n \n  End'.encode('utf-8'))
    source = parse_plan(raw)
    assert source.projections[1].data['description'] == 'RTL: שלום\u2028عربي\u2029終\n\n \nEnd'
    changed = source.replace_fields({ENTRY: {'description': 'חדש\u2028نص\n\n'}}, expected_file_sha256=source.file_sha256)
    assert changed.source_bytes == raw[:source.sections[1].body.start] + '  חדש\u2028نص\n\n'.encode()


def test_minimal_metadata_updates_preserve_literal_escapes_and_other_tokens():
    p = metadata(plan())
    p['notes'] = ['literal\nvalue']
    encoded = json.dumps(p, ensure_ascii=True, indent=3).replace('"revision": 1', '"revision" : 1').replace('"maturity": "draft"', '"maturity" : "draft"')
    encoded = encoded.replace('"notes": [', '"notes" : [')
    raw = block('# [21] Plan', plan(), 'Unchanged\n', encoded=encoded)
    source = parse_plan(raw)
    changed = source.replace_fields({PLAN: {'revision': 2, 'maturity': 'proposed'}}, expected_file_sha256=source.file_sha256)
    assert changed.source_bytes == raw.replace(b'"revision" : 1', b'"revision" : 2').replace(b'"maturity" : "draft"', b'"maturity" : "proposed"')
    assert changed.projections[0].data['notes'] == ['literal\nvalue']
    assert changed.replace_fields({PLAN: {'revision': 2, 'maturity': 'proposed'}}, expected_file_sha256=changed.file_sha256).source_bytes == changed.source_bytes


def test_new_optional_metadata_only_inserts_tokens_and_never_manufactures_proof():
    raw, _, _ = small_source()
    source = parse_plan(raw)
    changed = source.replace_fields({ENTRY: {'notes': ['Keep this'], 'phase': 'prepare'}}, expected_file_sha256=source.file_sha256)
    marker = b',"notes":["Keep this"],"phase":"prepare"'
    assert changed.source_bytes.count(marker) == 1 and changed.source_bytes.replace(marker, b'') == raw
    assert changed.projections[1].data['notes'] == ['Keep this']
    assert 'commit_refs' not in changed.projections[1].data
    assert changed.projections[1].data['revision'] == 1
    assert changed.revision_diagnostics(source)[0]['actual_revision'] == 1


def test_matched_derived_metadata_is_updated_with_only_the_requested_field():
    e = entry(); e.update(title='Original', display_id='A', description='Body\n')
    raw = block('# [21] Plan', plan()) + block('## [ ] [A] Original', e, 'Body\n', encoded=json.dumps(e, indent=2))
    source = parse_plan(raw)
    changed = source.replace_fields({ENTRY: {'title': 'New'}}, expected_file_sha256=source.file_sha256)
    assert changed.source_bytes == raw.replace(b'Original', b'New')
    assert changed.projections[1].data['description'] == 'Body\n'


@pytest.mark.parametrize('revision', [1, 3, 7])
def test_bad_content_revision_is_a_warning_with_exact_identity_not_reader_repair(revision):
    raw, _, _ = small_source()
    source = parse_plan(raw)
    changed = source.replace_fields({ENTRY: {'title': 'Manually changed', 'revision': revision}}, expected_file_sha256=source.file_sha256)
    warning, = changed.revision_diagnostics(source)
    assert warning['code'] == 'SRV206' and warning['severity'] == 'warning'
    assert warning['artifact_id'] == ENTRY and warning['expected_revision'] == 2
    assert warning['actual_revision'] == revision
    assert changed.projections[1].data['revision'] == revision
    assert not changed.revision_diagnostics()


def test_format_only_change_rebinds_file_without_changing_artifacts_or_revision():
    raw, _, _ = small_source()
    before = parse_plan(raw)
    after = parse_plan(raw.replace(b'"revision": 1', b'"revision" : 1'))
    assert before.file_sha256 != after.file_sha256
    assert [p.sha256 for p in before.projections] == [p.sha256 for p in after.projections]
    assert after.revision_diagnostics(before) == ()
    with pytest.raises(ModelError, match='plan_source_changed'):
        after.replace_fields({}, expected_file_sha256=before.file_sha256)


@pytest.mark.parametrize('variant,reason', [('id','artifact_identity_mismatch'), ('prefix','artifact_identity_mismatch'),
    ('duplicate','duplicate_artifact_id'), ('display','duplicate_plan_display_id'), ('relation','duplicate_plan_relation_id')])
def test_bad_or_colliding_ids_have_no_partial_projection(variant, reason):
    p = plan(); a = entry(); b = entry()
    b['id'] = 'SR-PENTRY-' + token(2); b['parent_relation_id'] = 'REL-' + token(3)
    label = 'B'
    if variant == 'id': b['id'] = 'SR-PENTRY-0001'
    if variant == 'prefix': b['id'] = 'XX-PENTRY-' + token(2)
    if variant == 'duplicate': b['id'] = ENTRY
    if variant == 'display': label = 'A'
    if variant == 'relation': b['parent_relation_id'] = a['parent_relation_id']
    raw = block('# [21] Plan', p) + block('## [ ] [A] First', a) + block('## [x] ['+label+'] Second', b)
    with pytest.raises(ModelError) as caught: parse_plan(raw, id_prefix='SR')
    error = caught.value
    # Malformed IDs may first fail the native schema before address validation.
    if variant == 'id': assert error.reason in (reason, 'schema_any_of', 'schema_pattern')
    elif variant == 'duplicate': assert error.reason in (reason, 'schema_unique_items')
    else: assert error.reason == reason
    diagnostic = error.diagnostic()
    assert diagnostic['code'] in ('SRV200','SRV201') and not diagnostic['partial_result_available']
    assert error.line >= 1 and error.position >= 0


def test_duplicate_json_key_location_tracks_physical_unicode_source():
    p = metadata(plan()); text = json.dumps(p, ensure_ascii=False, indent=2)
    text = text[:-2] + ',\n  "language": "de-DE"\n}'
    raw = block('# [21] תכנית', plan(), encoded=text)
    offset = raw.rindex(b'"language"')
    with pytest.raises(ModelError, match='duplicate_key') as caught: parse_plan(raw)
    error = caught.value
    assert error.position == offset
    assert error.line == raw[:offset].count(b'\n')+1 and error.column == 3
    assert error.pointer == '/language'


@pytest.mark.parametrize('variant,reason', [('jump','plan_list_parent_missing'), ('odd','plan_list_indentation'),
    ('meta','plan_metadata_header_mismatch'), ('body','plan_body_indentation'), ('tab','plan_orphan_metadata')])
def test_list_indentation_is_explicit_and_never_synthesizes_parents(variant, reason):
    p = block('# [21] Plan', plan())
    if variant == 'jump': raw = p + block('  - [ ] [A] Entry', entry(), indent=4)
    if variant == 'odd': raw = p + block(' - [ ] [A] Entry', entry(), indent=3)
    if variant == 'meta': raw = p + block('- [ ] [A] Entry', entry(), indent=0)
    if variant == 'body': raw = p + block('- [ ] [A] Entry', entry(), indent=2) + b'No indent\n'
    if variant == 'tab': raw = p + block('\t- [ ] [A] Entry', entry(), indent=2)
    with pytest.raises(ModelError, match=reason): parse_plan(raw)


def test_longer_fences_heading_closures_and_one_blank_line_are_preserved():
    raw = block('  # [P] Plan ###  ', plan(), gap='\n', fence='````')
    raw = raw.replace(b'````\n', b'`````\n')
    raw += block('### [x] [E] Entry ##', entry(), 'Free\n', gap='\n')
    source = parse_plan(raw)
    assert [p.data['title'] for p in source.projections] == ['Plan', 'Entry']
    assert source.projections[0].data['children'] == [ENTRY]
    assert source.replace_fields({ENTRY: {'title': 'Changed'}}, expected_file_sha256=source.file_sha256).source_bytes == raw.replace(b'[E] Entry ##', b'[E] Changed ##')
    invalid = raw.replace(b'Entry ##\n\n```', b'Entry ##\n\n\n```')
    with pytest.raises(ModelError, match='plan_orphan_metadata'): parse_plan(invalid)


@pytest.mark.parametrize('spaces', range(4))
def test_atx_metadata_fences_accept_non_code_indentation(spaces):
    raw = block('# [P] Plan', plan(), 'Free\n')
    raw = raw.replace(b'```', b' '*spaces+b'```')
    source = parse_plan(raw)
    assert source.projections[0].data['description'] == 'Free\n'
    assert source.replace_fields({}, expected_file_sha256=source.file_sha256).source_bytes == raw


def test_nested_examples_and_inline_comments_do_not_change_parent_stack():
    header = 'Parent <!-- preserved comment -->'
    raw = block('# [P] Plan', plan()) + block('## [ ] [A] '+header, entry(),
        '<!--\n## [x] [fake] invisible\n```specroad-entry-v1\n{}\n```\n-->\n')
    b = entry(); b.update(id='SR-PENTRY-'+token(2), parent_relation_id='REL-'+token(3))
    raw += block('- [ ] [B] Child', b, '```text<!--code-info\n- [x] [fake] still code\n```\n', indent=2)
    source = parse_plan(raw)
    assert len(source.sections) == 3 and source.projections[1].data['title'] == header
    assert source.projections[1].data['children'] == [b['id']]
    assert source.projections[2].data['parent_id'] == ENTRY
    assert source.projections[2].data['description'] == '```text<!--code-info\n- [x] [fake] still code\n```\n'


@pytest.mark.parametrize('example', ['> <!-- a quoted example\n', '    <!-- indented code\n',
    'An inline `<!--` token\n', r'An escaped \<!-- token'+'\n'])
def test_comment_examples_cannot_hide_following_real_entries(example):
    raw = block('# [P] Plan', plan(), example) + block('## [ ] [A] Entry', entry())
    source = parse_plan(raw)
    assert len(source.sections) == 2
    assert source.projections[0].data['description'] == example
    assert source.projections[1].data['id'] == ENTRY


def test_invalid_carrier_bytes_remain_readable_for_explicit_diagnosis(tmp_path):
    raw, _, _ = small_source()
    raw += b'```specroad-entry-v1\n{}\n```\n'
    source = project(tmp_path, {PLAN: raw}); path = 'spec/implementation-plans/'+PLAN+'.md'
    before = inventory(tmp_path)
    with no_write_attempts():
        with pytest.raises(ModelError, match='plan_orphan_metadata'): source.read_plan(path)
        assert source.read_plan_bytes(path) == raw
    assert inventory(tmp_path) == before


def test_current_native_reader_rejects_shadow_paths_old_projects_and_changed_configuration(tmp_path):
    raw, _, _ = small_source(); source = project(tmp_path, {PLAN: raw})
    path = 'spec/implementation-plans/'+PLAN+'.md'
    wrong = path.replace(PLAN, 'SR-IPLAN-'+token(23))
    with pytest.raises(ModelError, match='plan_carrier_identity_mismatch'): parse_plan(raw, path=wrong)
    for name in (path+'.json', 'spec/plan-entries/'+ENTRY+'.json', '../outside.md', 'generated/plan.md'):
        with pytest.raises(ModelError): source.read_plan(name)
    conf = json.loads((tmp_path/'specroad.json').read_bytes()); conf['schema_version'] = '0.2.0'
    (tmp_path/'specroad.json').write_text(json.dumps(conf))
    with pytest.raises(ModelError, match='configuration_changed'): source.read_plan(path)
    from specroad.storage.project import ProjectSource
    with pytest.raises(ModelError, match='plan_project_migration_required'): ProjectSource(tmp_path).read_plan(path)


def test_native_read_boundary_rejects_linked_carriers(tmp_path):
    raw, _, _ = small_source(); root = tmp_path/'project'; source = project(root, {PLAN: raw})
    path = 'spec/implementation-plans/'+PLAN+'.md'
    outside = tmp_path/'outside.md'; outside.write_bytes(raw)
    (root/path).unlink(); (root/path).symlink_to(outside)
    with pytest.raises(SafetyViolation): source.read_plan(path)
    assert outside.read_bytes() == raw


def test_field_edit_cannot_inject_extra_structured_entries_or_change_ownership():
    raw, _, _ = small_source(); source = parse_plan(raw)
    extra = entry(); extra.update(id='SR-PENTRY-'+token(2), parent_relation_id='REL-'+token(3))
    injection = block('## [ ] [B] Injected', extra).decode()
    with pytest.raises(ModelError, match='plan_unrequested_projection_change'):
        source.replace_fields({ENTRY: {'description': injection}}, expected_file_sha256=source.file_sha256)
    for field in ('id', 'children', 'parent_id', 'plan_id'):
        with pytest.raises(ModelError, match='plan_structural_edit_required'):
            source.replace_fields({ENTRY: {field: 'changed'}}, expected_file_sha256=source.file_sha256)
    s = source.sections[1].title
    with pytest.raises(ModelError, match='invalid_utf8'):
        source.replace_spans([SourceEdit(s.start, s.end, s.read(raw), b'\x80')], expected_file_sha256=source.file_sha256)


def test_many_levels_use_an_iterative_parent_stack():
    # Beyond Python's recursion depth: logical nesting is not JSON nesting.
    chunks = [block('# [P] Plan', plan())]
    for index in range(1100):
        e = entry(); e.update(id='SR-PENTRY-'+token(index+1), parent_relation_id='REL-'+token(index+1))
        chunks.append(block('  '*index+'- [ ] ['+str(index)+'] Entry', e, indent=2*index+2,
            encoded=json.dumps(metadata(e), ensure_ascii=False, separators=(',', ':'))))
    source = parse_plan(b''.join(chunks))
    assert len(source.sections) == 1101
    assert source.projections[-1].data['children'] == []
    assert source.projections[-1].data['parent_id'] == 'SR-PENTRY-'+token(1099)
    assert source.projections[0].data['children'] == ['SR-PENTRY-'+token(1)]
