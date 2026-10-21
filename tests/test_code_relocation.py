"""Exact stored/unique/missing/ambiguous locations, without reference writes."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import os
import subprocess

import pytest

from specroad.model.errors import ModelError
from specroad.query.git_source import GitObjectSource
from specroad.security import ProjectBoundary
from specroad.verification import (CodeSelectionLocation, locate_code_selection,
                                   read_code_reference, select_code_lines)
from support.git_objects import GitFixture
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from test_code_reference_sources import PATH, reference
from test_code_line_selection import bound_file, line_reference


def anchored_reference(raw, selected, *, mode='text', start=1, count=1, **overrides):
    anchor = {'format_version': 'code-anchor-v1', 'mode': mode}
    fields = {'file_sha256': sha256(raw).hexdigest(), 'selection_sha256': sha256(selected).hexdigest()}
    if mode == 'text':
        anchor.update(start_line=start, line_count=count)
        fields['encoding'] = 'utf-8'
    else:
        anchor.update(start_byte=start, byte_count=count)
    fields['anchor'] = anchor
    fields.update(overrides)
    return reference('text_anchor', **fields)


def located_file(root, raw, selected, *, mode='line_range', start=1, count=1, **fields):
    record = (line_reference(raw, selected, start=start, end=start + count - 1, **fields)
              if mode == 'line_range' else anchored_reference(raw, selected, mode=mode, start=start, count=count, **fields))
    put(root, PATH, raw)
    source = read_code_reference(ProjectBoundary(root), record)
    before = inventory(root), record.source_bytes, source.data
    with no_write_attempts():
        result = locate_code_selection(source)
    assert (inventory(root), record.source_bytes, source.data) == before
    assert result.data['source'] == source.data and result.data['source_sha256'] == source.sha256
    return result


@pytest.mark.parametrize('mode', ['line_range', 'text'])
@pytest.mark.parametrize('raw,start,count,selected,outcome,matches,new', [
    (b'wrong\nKEEP\n', 1, 1, b'KEEP\n', 'relocated', 1, (2, 2)),
    (b'KEEP\nwrong\n', 2, 1, b'KEEP\n', 'relocated', 1, (1, 1)),
    (b'KEEP\n', 99, 1, b'KEEP\n', 'relocated', 1, (1, 1)),
    (b'A\nB\n', 2, 2, b'A\nB\n', 'relocated', 1, (1, 2)),
    (b'wrong\r\nA\rB\r\ntail', 1, 2, b'A\nB\n', 'relocated', 1, (2, 3)),
    (b'wrong\nKEEP', 1, 1, b'KEEP', 'relocated', 1, (2, 2)),
    (b'wrong\nKEEP\nKEEP\n', 1, 1, b'KEEP\n', 'selection_ambiguous', 2, None),
    (b'wrong\nKEEP\nKEEP\nKEEP\n', 1, 1, b'KEEP\n', 'selection_ambiguous', 3, None),
    (b'wrong\nA\nA\nA\n', 1, 2, b'A\nA\n', 'selection_ambiguous', 2, None),
    (b'other\n', 1, 1, b'KEEP\n', 'selection_missing', 0, None),
    (b'', 1, 1, b'', 'selection_missing', 0, None),
    (b'A\n', 1, 2, b'A\n', 'selection_missing', 0, None),
    (b'KEEP\n', 2, 1, b'', 'selection_missing', 0, None),
    (b'wrong\nKEEP\n', 1, 1, b'KEEP', 'selection_missing', 0, None),
    (b'wrong\nKEEP', 1, 1, b'KEEP\n', 'selection_missing', 0, None),
    (b'wrong\nxKEEP\n', 1, 1, b'KEEP\n', 'selection_missing', 0, None),
    (b'wrong\n\n', 1, 1, b'\n', 'relocated', 1, (2, 2)),
], ids=['forward', 'backward', 'old-position-gone', 'old-range-truncated', 'mixed-newlines',
        'no-final-lf', 'two-matches', 'three-matches', 'overlapping-lines', 'no-match',
        'empty-file', 'no-shorter-window', 'no-phantom-final-line', 'lf-is-content',
        'missing-lf-is-content', 'no-substring', 'blank-line'])
def test_text_locations_are_exact_full_windows(tmp_path, mode, raw, start, count, selected, outcome, matches, new):
    result = located_file(tmp_path, raw, selected, mode=mode, start=start, count=count)
    data = result.data
    assert data['selection_result'] == outcome and data['match_count'] == matches
    assert data['search_performed'] is True and data['stored_position_matches'] is False
    position = None if new is None else {'start_line': new[0], 'end_line': new[1]}
    assert data['new_position'] == data['matched_position'] == position
    assert result.selection_bytes == (selected if new else None)
    assert data['selection_sha256'] == (sha256(selected).hexdigest() if new else None)
    assert data['stored_position'] == {'start_line': start, 'end_line': start + count - 1}
    assert data['reference_state_evaluated'] is False and 'state' not in data


@pytest.mark.parametrize('mode', ['line_range', 'text', 'bytes'])
def test_stored_position_wins_even_with_multiple_other_matches_and_changed_file(tmp_path, mode):
    raw = b'A\nA\nA\n'
    result = located_file(tmp_path, raw, b'A\n', mode=mode,
                          start=2, count=2 if mode == 'bytes' else 1, file_sha256='0' * 64)
    data = result.data
    assert result.selection_bytes == b'A\n' and data['selection_result'] == 'stored_position'
    assert data['stored_position_matches'] is True and data['search_performed'] is False
    assert data['match_count'] is None and data['new_position'] is None
    assert data['matched_position'] == data['stored_position']
    assert data['source']['file_hash_matches'] is False


@pytest.mark.parametrize('raw,selected,start,count,outcome,matches,position', [
    (b'xx\xff\x00\r\nyy', b'\xff\x00\r\n', 0, 4, 'relocated', 1, 2),
    (b'AAxx', b'AA', 2, 2, 'relocated', 1, 0),
    (b'xxAA', b'AA', 99, 2, 'relocated', 1, 2),
    (b'xAAAA', b'AA', 0, 2, 'selection_ambiguous', 3, None),
    (b'xxAAxxAA', b'AA', 0, 2, 'selection_ambiguous', 2, None),
    (b'xxA\r\n', b'A\n', 0, 2, 'selection_missing', 0, None),
    (b'', b'', 0, 1, 'selection_missing', 0, None),
    (b'A', b'A', 0, 2, 'selection_missing', 0, None),
    (b'\x00\xff', b'\xff', 0, 1, 'relocated', 1, 1),
], ids=['raw-binary', 'backward', 'old-offset-missing', 'overlaps', 'separated',
        'no-newline-normalization', 'empty', 'no-truncation', 'single-byte'])
def test_byte_anchor_search_preserves_every_byte_and_counts_overlaps(tmp_path, raw, selected, start, count, outcome, matches, position):
    result = located_file(tmp_path, raw, selected, mode='bytes', start=start, count=count)
    data = result.data
    assert data['selection_result'] == outcome and data['match_count'] == matches
    expected = None if position is None else {'start_byte': position, 'byte_count': count}
    assert data['matched_position'] == data['new_position'] == expected
    assert data['encoding'] is None and data['source_line_count'] is None
    assert result.selection_bytes == (selected if position is not None else None)


@pytest.mark.parametrize('encoding,text', [('utf-16', '東京🙂'), ('utf-32-be', 'Grüße'),
                                         ('latin-1', 'café'), ('utf-8', 'e\u0301\u2028\x00keep')])
@pytest.mark.parametrize('mode', ['line_range', 'text'])
def test_relocation_uses_stored_encoding_and_preserves_non_newline_characters(tmp_path, encoding, text, mode):
    raw = ('prefix\r\n' + text + '\rtail').encode(encoding)
    selected = (text + '\n').encode()
    result = located_file(tmp_path, raw, selected, mode=mode, encoding=encoding)
    assert result.data['selection_result'] == 'relocated'
    assert result.data['new_position'] == {'start_line': 2, 'end_line': 2}
    assert result.selection_bytes == selected and result.data['source_line_count'] == 3


def test_no_unicode_composition_folding_or_fuzzy_matching(tmp_path):
    result = located_file(tmp_path, 'wrong\né\n'.encode(), 'e\u0301\n'.encode())
    assert result.data['selection_result'] == 'selection_missing'
    assert result.data['source']['file_hash_matches'] is True


@pytest.mark.parametrize('encoding,raw,reason', [
    ('does-not-exist', b'A', 'code_reference_encoding_unavailable'),
    ('base64_codec', b'QQ==', 'code_reference_encoding_unavailable'),
    ('utf-8\x00', b'A', 'schema_not'),
    ('utf-8', b'wrong\nKEEP\n\xff', 'code_reference_decode_failed'),
    ('utf-16-le', b'x', 'code_reference_decode_failed'),
    ('unicode_escape', b'\\ud800', 'code_reference_decode_failed'),
])
@pytest.mark.parametrize('api', ['stored', 'locate'])
def test_encoding_errors_remain_distinct_from_missing_selection(tmp_path, encoding, raw, reason, api):
    if reason == 'schema_not':
        # Control characters are rejected by the existing stored-record schema,
        # before either public selector can receive a bound source.
        with pytest.raises(ModelError) as caught:
            line_reference(raw, b'KEEP\n', encoding=encoding)
        assert caught.value.reason == reason and caught.value.pointer == '/encoding'
        return
    source = bound_file(tmp_path, raw, b'KEEP\n', encoding=encoding)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        (select_code_lines if api == 'stored' else locate_code_selection)(source)
    assert caught.value.reason == reason and caught.value.pointer == '/encoding'


@pytest.mark.parametrize('anchor', [
    {'text': 'KEEP', 'line': 1}, {'format_version': 'future', 'mode': 'text'},
    {'format_version': 1, 'mode': 'bytes'},
])
def test_legacy_or_unknown_anchors_are_preserved_without_guessing(tmp_path, anchor):
    record = anchored_reference(b'KEEP\n', b'KEEP\n', anchor=anchor)
    put(tmp_path, PATH, b'KEEP\n')
    source = read_code_reference(ProjectBoundary(tmp_path), record)
    before = record.source_bytes, source.data, inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        locate_code_selection(source)
    assert caught.value.reason == 'code_reference_anchor_unsupported'
    assert (record.source_bytes, source.data, inventory(tmp_path)) == before


@pytest.mark.parametrize('mode', ['text', 'bytes'])
@pytest.mark.parametrize('mutation', ['missing-start', 'missing-count', 'unknown-field',
                                    'bool-start', 'negative-start', 'string-count', 'zero-count', 'bool-count'])
def test_malformed_versioned_anchors_cannot_gain_a_selection(tmp_path, mode, mutation):
    first, length = ('start_line', 'line_count') if mode == 'text' else ('start_byte', 'byte_count')
    anchor = {'format_version': 'code-anchor-v1', 'mode': mode, first: 1, length: 1}
    if mutation == 'missing-start': del anchor[first]
    elif mutation == 'missing-count': del anchor[length]
    elif mutation == 'unknown-field': anchor['execute'] = 'compiler'
    elif mutation == 'bool-start': anchor[first] = True
    elif mutation == 'negative-start': anchor[first] = -1
    elif mutation == 'string-count': anchor[length] = '1'
    elif mutation == 'zero-count': anchor[length] = 0
    else: anchor[length] = False
    record = anchored_reference(b'A', b'A', mode=mode, anchor=anchor)
    put(tmp_path, PATH, b'A')
    with pytest.raises(ModelError) as caught:
        locate_code_selection(read_code_reference(ProjectBoundary(tmp_path), record))
    assert caught.value.reason == 'code_reference_anchor_invalid'


@pytest.mark.parametrize('mode', ['regex', 'symbol', None, [], {}])
def test_anchor_mode_is_explicit_and_never_executable(tmp_path, mode):
    record = anchored_reference(b'A', b'A', anchor={'format_version': 'code-anchor-v1', 'mode': mode})
    put(tmp_path, PATH, b'A')
    with pytest.raises(ModelError) as caught:
        locate_code_selection(read_code_reference(ProjectBoundary(tmp_path), record))
    assert caught.value.reason == 'code_reference_anchor_invalid' and caught.value.pointer == '/anchor/mode'


def test_text_anchor_requires_encoding_even_when_source_is_ascii(tmp_path):
    record = reference('text_anchor', anchor={'format_version': 'code-anchor-v1', 'mode': 'text', 'start_line': 1, 'line_count': 1})
    put(tmp_path, PATH, b'A')
    with pytest.raises(ModelError) as caught:
        locate_code_selection(read_code_reference(ProjectBoundary(tmp_path), record))
    assert caught.value.reason == 'code_reference_encoding_required'


@pytest.mark.parametrize('mode,fields', [('text', {'start_line': 2}), ('text', {'end_line': 2}),
                                      ('bytes', {'start_line': 1}), ('bytes', {'encoding': 'utf-8'})])
def test_conflicting_top_level_coordinates_or_byte_encoding_are_rejected(tmp_path, mode, fields):
    with pytest.raises(ModelError) as caught:
        located_file(tmp_path, b'A', b'A', mode=mode, start=1 if mode == 'text' else 0, **fields)
    assert caught.value.reason == 'code_reference_anchor_conflict'


def test_redundant_matching_text_positions_are_not_a_second_selector(tmp_path):
    result = located_file(tmp_path, b'A\nB', b'A\n', mode='text', start_line=1, end_line=1)
    assert result.data['selection_result'] == 'stored_position'


@pytest.mark.parametrize('mode', ['line_range', 'text', 'bytes'])
def test_huge_expected_extent_is_missing_without_truncation_or_extent_allocation(tmp_path, mode):
    result = located_file(tmp_path, b'A', b'A', mode=mode, start=10**12, count=10**12)
    assert result.data['selection_result'] == 'selection_missing'
    assert result.data['stored_selection_sha256'] is None and result.selection_bytes is None


@pytest.mark.parametrize('value', [None, {}, b'A', 'path'])
def test_locator_requires_an_owned_source(value):
    with pytest.raises(ModelError) as caught:
        locate_code_selection(value)
    assert caught.value.reason == 'code_reference_source_bytes_required'


@pytest.mark.parametrize('kind', ['file', 'symbol_hint', 'generated_artifact'])
def test_passive_nonselection_kinds_do_not_become_location_evidence(tmp_path, kind):
    put(tmp_path, PATH, b'A')
    with pytest.raises(ModelError) as caught:
        locate_code_selection(read_code_reference(ProjectBoundary(tmp_path), reference(kind)))
    assert caught.value.reason == 'code_reference_selection_kind_required'


@pytest.mark.parametrize('mode', ['text', 'bytes'])
def test_file_and_historical_git_locations_agree_without_checkout(tmp_path, mode):
    repo = GitFixture(tmp_path / 'repo')
    raw, selected = (b'wrong\r\nKEEP\r\n', b'KEEP\n') if mode == 'text' else (b'xx\xff\x00', b'\xff\x00')
    record = anchored_reference(raw, selected, mode=mode, start=1 if mode == 'text' else 0, count=1 if mode == 'text' else 2)
    commit = repo.commit({PATH: raw})
    put(repo.root, PATH, raw)
    file_result = locate_code_selection(read_code_reference(ProjectBoundary(repo.root), record))
    repo.commit({PATH: b'later'}, parent=commit)
    put(repo.root, PATH, b'different working source')
    before = repo.capture()
    git_result = locate_code_selection(read_code_reference(GitObjectSource(repo.root, commit), record))
    assert git_result.data['selection_result'] == file_result.data['selection_result'] == 'relocated'
    assert git_result.data['new_position'] == file_result.data['new_position']
    assert git_result.selection_bytes == file_result.selection_bytes == selected
    assert repo.capture() == before


def test_bound_snapshot_is_located_without_reopening_or_launching(tmp_path, monkeypatch):
    source = bound_file(tmp_path, b'wrong\nKEEP\n', b'KEEP\n')
    (tmp_path / PATH).unlink()
    def forbidden(*args, **kwargs):
        raise AssertionError('locator attempted I/O or process execution')
    monkeypatch.setattr(os, 'open', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    result = locate_code_selection(source)
    assert result.selection_bytes == b'KEEP\n' and result.data['selection_result'] == 'relocated'


def test_location_is_detached_immutable_and_not_state_or_permission(tmp_path):
    result = located_file(tmp_path, b'wrong\nKEEP\n', b'KEEP\n')
    data, digest = result.data, result.sha256
    data['source']['reference'].clear(); data['new_position']['start_line'] = 99
    assert result.data['new_position']['start_line'] == 2 and result.sha256 == digest
    for key in ('reference_state_evaluated', 'symbol_resolved', 'source_code_executed', 'write_authorized'):
        assert result.data[key] is False
    assert result.data['selection_evaluated'] and result.data['relocation_evaluated']
    with pytest.raises(FrozenInstanceError): result.selection_bytes = b'forged'
    with pytest.raises(TypeError): CodeSelectionLocation()
    with pytest.raises(TypeError): bool(result)


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_location_runs_in_fresh_standard_library_only_runtime(tmp_path, mode):
    project = tmp_path / 'project'; project.mkdir()
    raw = b'wrong\r\n__import__("os").system("compiler")\r\n'
    selected = b'__import__("os").system("compiler")\n'
    put(project, PATH, raw)
    record = anchored_reference(raw, selected)
    body = '''import json,os,sys
class OnlyCoreAndStdlib:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] not in sys.stdlib_module_names | {'specroad'}:
            raise AssertionError('third-party import attempted: '+fullname)
sys.meta_path.insert(0, OnlyCoreAndStdlib())
from specroad.verification import read_code_reference,locate_code_selection
from specroad.security import ProjectBoundary
from specroad.storage.record_artifact import RecordArtifact
'''
    body += 'source=read_code_reference(ProjectBoundary(' + repr(str(project)) + '),RecordArtifact(' + repr(record.source_bytes) + '))\n'
    body += '''def guard(event,args):
    if event in {'subprocess.Popen','os.system','socket.__new__','os.mkdir','os.remove','os.rename'}:
        raise AssertionError('prohibited effect: '+event)
    if event == 'open':
        path,mode,flags=args
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            raise AssertionError('write attempted')
sys.addaudithook(guard)
result=locate_code_selection(source)
print(json.dumps(result.data))
'''
    before = inventory(project)
    if mode == 'core':
        completed = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        completed = run_python(['-I', '-S', '-B', '-c', 'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == locate_code_selection(read_code_reference(ProjectBoundary(project), record)).data
    assert inventory(project) == before
