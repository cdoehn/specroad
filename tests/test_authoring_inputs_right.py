"""Negative input contracts preserve data and never allocate a visible identity."""
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from specroad.authoring import inputs
from specroad.authoring.inputs import (normalize_artifact_create_input,
    parse_artifact_create_input, read_artifact_create_input)
from specroad.changes import AuthoringError
from specroad.security import SafetyViolation
from support.command_parity import build_core, process_environment
from support.read_only import inventory, no_write_attempts
from test_authoring_inputs import fields, UnusedStdin


REQUIRED = {
    'goal': 'statement', 'need': 'stakeholder', 'capability': 'description',
    'requirement': 'normative_force', 'scenario': 'actors', 'decision': 'decision',
    'risk': 'probability', 'assumption': 'validation_status', 'component': 'responsibility',
    'interface': 'source_component', 'release': 'name', 'milestone': 'objective',
    'task': 'done_criteria', 'term': 'definition', 'source': 'locator',
    'verification': 'method', 'test': 'test_identity', 'issue': 'issue_status',
    'document': 'purpose', 'section': 'title', 'content_block': 'block_kind',
    'view': 'scope_descriptor', 'code_ref': 'path', 'configuration': 'selection',
}


@pytest.mark.parametrize('kind,field', list(REQUIRED.items()))
@pytest.mark.parametrize('defect', ['missing', 'null'])
@pytest.mark.parametrize('route', ['mapping', 'file', 'stdin'])
def test_each_type_rejects_missing_or_wrong_required_value_before_planning(tmp_path, kind, field, defect, route):
    value = fields(kind)
    if defect == 'missing': value.pop(field)
    else: value[field] = None
    raw = json.dumps(value).encode(); path = tmp_path / 'fields.json'; path.write_bytes(raw)
    before = inventory(tmp_path)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no allocation')):
        with pytest.raises(AuthoringError) as error:
            if route == 'mapping': normalize_artifact_create_input(kind, value)
            else: read_artifact_create_input(kind, input=str(path) if route == 'file' else '-',
                         stdin=UnusedStdin() if route == 'file' else BytesIO(raw))
    assert error.value.exit_code == 3
    assert error.value.diagnostic()['write_state'] == 'not_committed'
    assert error.value.diagnostic()['authorization_granted'] is False
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('value', ['"owner","ignored":true', '"owner","another":{"private":1}',
    '"owner","value":"different"', '"owner"} {}', '"unterminated', 'NaN'])
def test_composite_option_is_exactly_one_json_value(value, tmp_path):
    before = inventory(tmp_path)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no allocation')):
        with pytest.raises(AuthoringError) as error:
            parse_artifact_create_input(['goal', '--title', 'Goal', '--statement', 'Statement',
                '--owner', value], cwd=tmp_path, stdin=UnusedStdin())
    assert error.value.exit_code == 3 and error.value.pointer.startswith('/owner')
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind,changes', [
    ('requirement', {'normative_force': 'should'}),
    ('capability', {'verification_plan_status': 'waived'}),
    ('content_block', {'block_kind': 'page_break'}),
])
def test_conditional_native_field_requirements_remain_effective(kind, changes):
    value = fields(kind); value.update(changes)
    with no_write_attempts():
        with pytest.raises(AuthoringError) as error: normalize_artifact_create_input(kind, value)
    assert error.value.exit_code == 3


@pytest.mark.parametrize('extra', ['command_id', 'handler', 'input', 'fields', 'actor_type',
                                  'actor_id', 'request_id', 'expected_revision'])
def test_file_content_cannot_select_a_command_or_supply_hidden_control_fields(tmp_path, extra):
    value = fields('goal'); value[extra] = '__import__("os").system("untrusted")'
    path = tmp_path / 'fields.json'; path.write_bytes(json.dumps(value).encode()); before = inventory(tmp_path)
    with no_write_attempts():
        with pytest.raises(AuthoringError) as error:
            read_artifact_create_input('goal', input=str(path), stdin=UnusedStdin())
    assert error.value.exit_code == 3 and error.value.pointer == '/' + extra
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('value', ['false', 'null', '42', '[]'])
def test_union_option_wrong_types_are_schema_errors(value):
    with no_write_attempts():
        with pytest.raises(AuthoringError) as error:
            read_artifact_create_input('goal', options={'--title': 'Goal', '--statement': 'Text',
                '--owner': value}, stdin=UnusedStdin())
    assert error.value.exit_code == 3


@pytest.mark.parametrize('field,option', [('title', 'Other'), ('statement', 'Other'), ('owner', '"Other"')])
@pytest.mark.parametrize('source', ['file', 'stdin'])
def test_conflicts_are_rejected_with_the_original_fields_preserved(tmp_path, field, option, source):
    value = fields('goal'); path = tmp_path / 'fields.json'; raw = json.dumps(value).encode(); path.write_bytes(raw)
    before = inventory(tmp_path); stream = BytesIO(raw)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no allocation')):
        with pytest.raises(AuthoringError) as error:
            read_artifact_create_input('goal', input=str(path) if source == 'file' else '-',
                options={'--' + field: option}, stdin=UnusedStdin() if source == 'file' else stream)
    assert error.value.exit_code == 2 and error.value.pointer == '/' + field
    assert inventory(tmp_path) == before and not stream.closed


@pytest.mark.parametrize('kind', ['closed', 'absent-read', 'noncallable-read', 'missing-default-buffer'])
def test_unavailable_binary_input_is_an_environment_error(tmp_path, monkeypatch, kind):
    if kind == 'closed': stream = BytesIO(); stream.close()
    elif kind == 'absent-read': stream = object()
    elif kind == 'noncallable-read':
        class NotReadable: read = 1
        stream = NotReadable()
    else:
        monkeypatch.setattr(sys, 'stdin', StringIO('must not read text implicitly')); stream = None
    before = inventory(tmp_path)
    with no_write_attempts():
        with pytest.raises(AuthoringError) as error:
            read_artifact_create_input('goal', input='-', stdin=stream)
    assert error.value.exit_code == 5 and inventory(tmp_path) == before


@pytest.mark.parametrize('problem', ['os-error', 'closed-error', 'security', 'none', 'text', 'oversized'])
def test_failed_read_is_not_retried_or_reinterpreted(problem, tmp_path):
    class Reader:
        calls = 0
        def read(self, size):
            self.calls += 1
            if self.calls == 1: return b'{"title":'
            if problem == 'os-error': raise OSError('private filesystem failure')
            if problem == 'closed-error': raise ValueError('closed stream')
            if problem == 'security': raise SafetyViolation('private unsafe read')
            if problem == 'none': return None
            if problem == 'text': return 'text'
            return b'x' * (size + 1)
    stream = Reader(); before = inventory(tmp_path)
    with no_write_attempts():
        with pytest.raises(AuthoringError) as error:
            read_artifact_create_input('goal', input='-', stdin=stream)
    assert error.value.exit_code == (5 if problem in ('os-error', 'closed-error') else 7)
    assert stream.calls == 2 and inventory(tmp_path) == before
    assert 'private' not in json.dumps(error.value.diagnostic())


@pytest.mark.parametrize('raw', [b'', b'{"title":', b'\xef\xbb\xbf{}', b'{"owner":"x","owner":"y"}',
    b'{"title":"\\ud800"}', b'{"title":"x","extensions":{"x.a":NaN}}'])
def test_stdin_syntax_failures_do_not_create_an_intent(raw):
    stream = BytesIO(raw)
    with no_write_attempts():
        with pytest.raises(AuthoringError) as error:
            read_artifact_create_input('goal', input='-', stdin=stream)
    assert error.value.exit_code == 3 and not stream.closed


@pytest.mark.parametrize('mutation', ['replace', 'grow', 'shrink'])
def test_changed_file_is_rejected_with_foreign_final_state_preserved(tmp_path, monkeypatch, mutation):
    path = tmp_path / 'fields.json'; path.write_bytes(json.dumps(fields('goal')).encode())
    inode = path.stat().st_ino; original = os.read; changed = False; expected = None
    def observed(fd, size):
        nonlocal changed, expected
        raw = original(fd, size)
        if not changed and os.fstat(fd).st_ino == inode:
            changed = True
            if mutation == 'replace':
                other = tmp_path / 'replacement'; other.write_bytes(path.read_bytes()); other.replace(path)
            elif mutation == 'grow': path.write_bytes(path.read_bytes() + b' ')
            else: path.write_bytes(b'{}')
            expected = inventory(tmp_path)
        return raw
    monkeypatch.setattr(inputs.os, 'read', observed)
    with pytest.raises(AuthoringError) as error:
        read_artifact_create_input('goal', input=str(path), stdin=UnusedStdin())
    assert changed and error.value.exit_code == 7
    assert inventory(tmp_path) == expected


def test_fifo_is_rejected_before_a_potential_blocking_open(tmp_path):
    path = tmp_path / 'pipe'; os.mkfifo(path); before = inventory(tmp_path)
    with no_write_attempts():
        with pytest.raises(AuthoringError) as error:
            read_artifact_create_input('goal', input=str(path), stdin=UnusedStdin())
    assert error.value.exit_code == 7 and inventory(tmp_path) == before


@pytest.mark.parametrize('distribution', ['module', 'zipapp'])
def test_built_adapters_reject_invalid_stdin_without_project_side_effects(tmp_path, distribution):
    root = Path(__file__).resolve().parents[1]; output = tmp_path / 'build'
    built = build_core(root, output); assert built.returncode == 0, built.stderr
    source = output / ('module' if distribution == 'module' else 'specroad.pyz')
    working = tmp_path / 'project'; working.mkdir(); (working / 'foreign').write_bytes(b'keep')
    (working / 'sitecustomize.py').write_text("raise AssertionError('project code imported')\n")
    before = inventory(working)
    body = '''import json,sys
sys.path.insert(0, sys.argv[1])
from specroad.authoring.inputs import parse_artifact_create_input
from specroad.changes import AuthoringError
try:
 parse_artifact_create_input(['goal', '--input', '-'])
except AuthoringError as error:
 sys.stdout.write(json.dumps(error.diagnostic()))
 raise SystemExit(error.exit_code)
raise AssertionError('invalid input accepted')
'''
    value = fields('goal'); value.pop('statement')
    process = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', body, str(source)],
        input=json.dumps(value).encode(), capture_output=True, cwd=working, env=process_environment())
    assert process.returncode == 3, process.stderr
    diagnostic = json.loads(process.stdout)
    assert diagnostic['write_state'] == 'not_committed' and diagnostic['authorization_granted'] is False
    assert inventory(working) == before
