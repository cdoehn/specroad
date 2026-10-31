"""H.2 original-byte decoding and exact inclusive selection behavior."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import os
import subprocess

import pytest

from specroad.model.errors import ModelError
from specroad.query.git_source import GitObjectSource
from specroad.security import ProjectBoundary
from specroad.verification import CodeLineSelection, read_code_reference, select_code_lines
from support.import_guards import CORE_STDLIB_IMPORT_GUARD
from support.git_objects import GitFixture
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from test_code_reference_sources import PATH, reference


def line_reference(raw, selected, *, start=1, end=1, encoding='utf-8', **overrides):
    fields = {'file_sha256': sha256(raw).hexdigest(), 'start_line': start,
              'end_line': end, 'encoding': encoding,
              'selection_sha256': sha256(selected).hexdigest()}
    fields.update(overrides)
    return reference('line_range', **fields)


def bound_file(root, raw, selected, **fields):
    put(root, PATH, raw)
    record = line_reference(raw, selected, **fields)
    return read_code_reference(ProjectBoundary(root), record)


@pytest.mark.parametrize('raw,start,end,expected,total', [
    (b'first\nsecond\nlast', 2, 2, b'second\n', 3),
    (b'first\r\nsecond\r\nlast', 2, 2, b'second\n', 3),
    (b'first\rsecond\rlast', 2, 2, b'second\n', 3),
    (b'first\r\nsecond\rlast\n', 2, 3, b'second\nlast\n', 3),
    (b'first\nsecond\nlast', 2, 3, b'second\nlast', 3),
    (b'first\nsecond\nlast\n', 3, 3, b'last\n', 3),
    (b'first\nsecond\nlast', 3, 3, b'last', 3),
    (b'one', 1, 1, b'one', 1),
    (b'one\n', 1, 1, b'one\n', 1),
    (b'\n', 1, 1, b'\n', 1),
    (b'\r\n\r\n', 2, 2, b'\n', 2),
    (b'head\n\ntail', 2, 2, b'\n', 3),
    (b'a\rb\rc', 1, 3, b'a\nb\nc', 3),
], ids=['lf', 'crlf', 'cr', 'mixed', 'inclusive-end', 'final-lf', 'final-no-lf',
        'one-line', 'one-line-lf', 'blank', 'two-blanks', 'inner-blank', 'whole-range'])
def test_inclusive_ranges_and_exact_line_terminators(tmp_path, raw, start, end, expected, total):
    source = bound_file(tmp_path, raw, expected, start=start, end=end)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = select_code_lines(source)
    data = result.data
    assert result.selection_bytes == expected
    assert data['selection_sha256'] == sha256(expected).hexdigest()
    assert data['selection_hash_matches'] is True
    assert data['start_line'] == start and data['end_line'] == end
    assert data['line_count'] == total and data['selected_line_count'] == end - start + 1
    assert data['source'] == source.data and data['source_sha256'] == source.sha256
    assert source.source_bytes == raw and inventory(tmp_path) == before


@pytest.mark.parametrize('character', ['\v', '\f', '\x1c', '\x1d', '\x1e', '\x85', '\u2028', '\u2029', '\x00'])
def test_other_unicode_separators_are_content_not_line_boundaries(tmp_path, character):
    selected = ('a' + character + 'b\n').encode()
    source = bound_file(tmp_path, b'head\r\n' + selected + b'tail', selected, start=2, end=2)
    result = select_code_lines(source)
    assert result.selection_bytes == selected
    assert result.data['selection_hash_matches'] and result.data['line_count'] == 3


@pytest.mark.parametrize('encoding,text', [
    ('utf-8', 'e\u0301東京'), ('latin-1', 'Grüße'), ('cp1252', '€ café'),
    ('utf-16', '東京🙂'), ('utf-16-le', '東京🙂'), ('utf-16-be', '東京🙂'),
    ('utf-32-le', '東京🙂'), ('utf-32-be', '東京🙂'), ('shift_jis', '東京'),
], ids=['utf8-decomposed', 'latin1', 'cp1252', 'utf16-bom', 'utf16le', 'utf16be',
        'utf32le', 'utf32be', 'shift-jis'])
def test_declared_encoding_precedes_normalization_and_hashing(tmp_path, encoding, text):
    raw = ('head\r\n' + text + '\r\ntail').encode(encoding)
    expected = (text + '\n').encode('utf-8')
    source = bound_file(tmp_path, raw, expected, start=2, end=2, encoding=encoding)
    result = select_code_lines(source)
    assert result.selection_bytes == expected
    assert result.data['encoding'] == encoding and result.data['selection_hash_matches']
    assert result.data['selection_sha256'] == sha256(expected).hexdigest()
    assert result.data['source']['file_sha256'] == sha256(raw).hexdigest()


def test_utf8_bom_and_decomposed_characters_are_not_silently_stripped_or_normalized(tmp_path):
    raw = '\ufeffe\u0301\r\n'.encode()
    expected = '\ufeffe\u0301\n'.encode()
    result = select_code_lines(bound_file(tmp_path, raw, expected))
    assert result.selection_bytes == expected and result.data['selection_hash_matches']
    assert result.data['selection_sha256'] != sha256('é\n'.encode()).hexdigest()


@pytest.mark.parametrize('changed', [b'other prefix\nKEEP\ntail\n', b'prefix\nKEEP\nother suffix',
                                     b'prefix\r\nKEEP\r\ntail\r\n'])
def test_changes_outside_selection_or_newline_style_preserve_selection_match(tmp_path, changed):
    original = b'prefix\nKEEP\ntail\n'
    record = line_reference(original, b'KEEP\n', start=2, end=2)
    put(tmp_path, PATH, changed)
    source = read_code_reference(ProjectBoundary(tmp_path), record)
    result = select_code_lines(source)
    assert result.selection_bytes == b'KEEP\n' and result.data['selection_hash_matches']
    assert result.data['source']['file_hash_matches'] is False
    assert result.data['source']['reference'] == record.data
    assert result.data['reference_state_evaluated'] is False and 'state' not in result.data
    assert (tmp_path / PATH).read_bytes() == changed


def test_matching_file_hash_does_not_override_wrong_selection_hash(tmp_path):
    source = bound_file(tmp_path, b'first\nsecond', b'not-the-selected-text', start=2, end=2)
    result = select_code_lines(source)
    assert result.selection_bytes == b'second'
    assert result.data['source']['file_hash_matches'] is True
    assert result.data['selection_hash_matches'] is False


def test_match_elsewhere_is_not_substituted_for_stored_position(tmp_path):
    source = bound_file(tmp_path, b'wrong\nKEEP\n', b'KEEP\n')
    result = select_code_lines(source)
    assert result.selection_bytes == b'wrong\n' and not result.data['selection_hash_matches']
    assert result.data['relocation_evaluated'] is False


@pytest.mark.parametrize('raw,start,end', [(b'', 1, 1), (b'x\n', 2, 2), (b'x', 2, 2),
                                        (b'x\ny', 1, 3), (b'\n', 1, 2)])
def test_unavailable_range_is_not_truncated_or_given_an_empty_hash(tmp_path, raw, start, end):
    source = bound_file(tmp_path, raw, b'', start=start, end=end)
    with pytest.raises(ModelError) as caught:
        select_code_lines(source)
    assert caught.value.reason == 'code_reference_selection_missing'
    assert caught.value.pointer == '/end_line'


@pytest.mark.parametrize('encoding,raw,reason', [
    ('no-such-code-encoding', b'a', 'code_reference_encoding_unavailable'),
    ('base64_codec', b'YQ==', 'code_reference_encoding_unavailable'),
    ('rot_13', b'a', 'code_reference_encoding_unavailable'),
    ('utf-8', b'\xff', 'code_reference_decode_failed'),
    ('utf-16-le', b'a', 'code_reference_decode_failed'),
    ('ascii', b'\x80', 'code_reference_decode_failed'),
])
def test_decoding_failures_do_not_guess_replace_or_return_a_selection(tmp_path, encoding, raw, reason):
    source = bound_file(tmp_path, raw, b'', encoding=encoding)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        select_code_lines(source)
    assert caught.value.reason == reason and caught.value.pointer == '/encoding'
    assert source.source_bytes == raw and inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['file', 'text_anchor', 'symbol_hint', 'generated_artifact'])
def test_other_reference_kinds_do_not_gain_line_selection_or_currency(tmp_path, kind):
    put(tmp_path, PATH, b'code\n')
    source = read_code_reference(ProjectBoundary(tmp_path), reference(kind))
    with pytest.raises(ModelError) as caught:
        select_code_lines(source)
    assert caught.value.reason == 'code_reference_line_range_required'
    assert caught.value.pointer == '/reference_kind'
    assert source.data['selection_evaluated'] is source.data['reference_state_evaluated'] is False


@pytest.mark.parametrize('value', [None, {}, b'bytes', 'path'])
def test_selection_requires_owned_source_bytes_not_an_arbitrary_input(value):
    with pytest.raises(ModelError) as caught:
        select_code_lines(value)
    assert caught.value.reason == 'code_reference_source_bytes_required'


def test_file_and_historical_git_selection_agree_without_checkout(tmp_path):
    repo = GitFixture(tmp_path / 'repo')
    raw = 'head\r\nGrüße\r\ntail'.encode('latin-1')
    selected = 'Grüße\n'.encode()
    commit = repo.commit({PATH: raw})
    record = line_reference(raw, selected, start=2, end=2, encoding='latin-1')
    put(repo.root, PATH, raw)
    file_selection = select_code_lines(read_code_reference(ProjectBoundary(repo.root), record))
    put(repo.root, PATH, b'other working bytes')
    repo.commit({PATH: b'later'}, parent=commit)
    before = repo.capture()
    source = read_code_reference(GitObjectSource(repo.root, commit), record)
    git_selection = select_code_lines(source)
    assert git_selection.selection_bytes == file_selection.selection_bytes == selected
    assert git_selection.data['selection_sha256'] == file_selection.data['selection_sha256']
    assert git_selection.data['selection_hash_matches']
    assert git_selection.data['source']['git_commit'] == commit and repo.capture() == before


def test_selection_uses_owned_snapshot_without_reopening_or_launching(tmp_path, monkeypatch):
    source = bound_file(tmp_path, b'head\r\nKEEP\r\n', b'KEEP\n', start=2, end=2)
    (tmp_path / PATH).unlink()
    def forbidden(*args, **kwargs):
        raise AssertionError('selection attempted I/O or process execution')
    monkeypatch.setattr(os, 'open', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    result = select_code_lines(source)
    assert result.selection_bytes == b'KEEP\n' and result.data['selection_hash_matches']


def test_selection_value_is_immutable_detached_and_not_a_state_or_permission(tmp_path):
    source = bound_file(tmp_path, b'head\nKEEP\n', b'KEEP\n', start=2, end=2)
    result = select_code_lines(source)
    digest = result.sha256
    data = result.data; data['source']['reference'].clear(); data['selection_hash_matches'] = False
    assert result.data['source'] == source.data and result.sha256 == digest
    assert result.data['selection_hash_matches'] and result.data['selection_evaluated']
    for key in ('relocation_evaluated', 'reference_state_evaluated', 'symbol_resolved',
                'source_code_executed', 'write_authorized'):
        assert result.data[key] is False
    assert 'state' not in result.data
    with pytest.raises(FrozenInstanceError): result.selection_bytes = b'forged'
    with pytest.raises(TypeError): CodeLineSelection()
    with pytest.raises(TypeError): bool(result)


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_public_selection_runs_in_fresh_standard_library_only_runtime(tmp_path, mode):
    project = tmp_path / 'project'; project.mkdir()
    raw = b'head\r\n__import__("os").system("compiler")\r\ntail'
    selected = b'__import__("os").system("compiler")\n'
    put(project, PATH, raw)
    record = line_reference(raw, selected, start=2, end=2)
    body = CORE_STDLIB_IMPORT_GUARD + '''import json,os,sys
from specroad.verification import read_code_reference,select_code_lines
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
result=select_code_lines(source)
print(json.dumps(result.data))
'''
    before = inventory(project)
    if mode == 'core':
        completed = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        completed = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == select_code_lines(read_code_reference(ProjectBoundary(project), record)).data
    assert inventory(project) == before
