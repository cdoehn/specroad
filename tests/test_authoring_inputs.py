"""Real file/stdin/option normalization before identity allocation or publication."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from specroad.authoring.inputs import (ArtifactCreateInput, normalize_artifact_create_input,
    parse_artifact_create_input, read_artifact_create_input)
from specroad.changes import AuthoringError, prepare_authoring_request
from specroad.model.audit_values import Actor, UtcTimestamp
from specroad.model.canonical import canonical_json_bytes
from specroad.model.identity_values import ArtifactIdentity
from specroad.model.requirement import prepare_requirement
from support.command_parity import build_core, process_environment
from support.domain import domain_value
from support.records import record_value
from support.read_only import inventory, no_write_attempts

DOMAIN = ('goal', 'need', 'capability', 'requirement', 'scenario', 'decision', 'risk',
          'assumption', 'component', 'interface', 'release', 'milestone', 'task', 'term')
RECORD = ('source', 'verification', 'test', 'issue', 'document', 'section',
          'content_block', 'view', 'code_ref', 'configuration')
GENERATED = {'schema_version', 'artifact_type', 'id', 'id_scheme', 'maturity', 'revision',
             'created_at', 'updated_at', 'created_by', 'updated_by'}


def fields(kind):
    value = domain_value(kind) if kind in DOMAIN else record_value(kind)
    return {k: v for k, v in value.items() if k not in GENERATED}


class UnusedStdin:
    def read(self, *args):
        raise AssertionError('stdin was not explicitly selected')


@pytest.mark.parametrize('kind', DOMAIN + RECORD)
@pytest.mark.parametrize('route', ['mapping', 'file', 'stdin'])
def test_all_regular_draft_types_preserve_expected_fields(tmp_path, kind, route):
    value = fields(kind); path = tmp_path / 'input fields.json'
    raw = json.dumps(value, ensure_ascii=False, indent=2).encode(); path.write_bytes(raw)
    before = inventory(tmp_path); stream = BytesIO(raw)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no identity allocation')):
        if route == 'mapping': result = normalize_artifact_create_input(kind, value)
        else:
            result = read_artifact_create_input(kind, input=path.name if route == 'file' else '-',
                cwd=tmp_path, stdin=UnusedStdin() if route == 'file' else stream)
    expected = {'format_version': '1.0.0', 'command_id': 'artifact.create', 'artifact_type': kind, 'fields': value}
    assert result.data == expected
    assert result.source_bytes == canonical_json_bytes(expected)
    assert result.sha256 == sha256(result.source_bytes).hexdigest()
    assert not GENERATED.intersection(result.fields)
    assert inventory(tmp_path) == before and not stream.closed


@pytest.mark.parametrize('kind', ['goal', 'requirement', 'term', 'scenario', 'risk', 'document'])
def test_real_field_option_tokens_match_file_and_stdin(tmp_path, kind):
    value = fields(kind)
    # Independently declared CLI encodings for these six concrete examples.
    json_fields = {'owner', 'relations', 'extensions', 'synonyms', 'forbidden_synonyms',
                   'actors', 'main_flow', 'probability', 'impact', 'audience', 'render_policy'}
    tokens = [kind]
    for name, content in value.items():
        tokens.extend(['--' + name.replace('_', '-'),
                       json.dumps(content, ensure_ascii=False) if name in json_fields else content])
    raw = json.dumps(value, ensure_ascii=False).encode()
    path = tmp_path / 'fields.json'; path.write_bytes(raw); before = inventory(tmp_path)
    with no_write_attempts():
        options = parse_artifact_create_input(tokens, cwd=tmp_path, stdin=UnusedStdin())
        file = parse_artifact_create_input([kind, '--input', str(path)], cwd=tmp_path, stdin=UnusedStdin())
        stream = parse_artifact_create_input([kind, '--input=-'], cwd=tmp_path, stdin=BytesIO(raw))
    assert options.source_bytes == file.source_bytes == stream.source_bytes
    assert options.fields == value and inventory(tmp_path) == before


def test_owned_input_and_returned_fields_cannot_change_preparation():
    value = fields('goal'); prepared = normalize_artifact_create_input('goal', value)
    before = prepared.source_bytes; value['title'] = 'changed'; prepared.fields['title'] = 'other'
    assert prepared.source_bytes == before
    with pytest.raises(FrozenInstanceError): prepared.source_bytes = b'{}'
    with pytest.raises(TypeError): bool(prepared)
    with pytest.raises(TypeError): ArtifactCreateInput({})


def test_transport_path_whitespace_and_object_order_do_not_bind_semantic_intent(tmp_path):
    value = fields('requirement'); a = tmp_path / 'one.json'; b = tmp_path / 'another.json'
    a.write_bytes(json.dumps(value, indent=4).encode())
    b.write_bytes(json.dumps(dict(reversed(tuple(value.items()))), separators=(',', ':')).encode())
    with no_write_attempts():
        x = read_artifact_create_input('requirement', input=str(a), stdin=UnusedStdin())
        y = read_artifact_create_input('requirement', input=str(b), stdin=UnusedStdin())
    assert x.source_bytes == y.source_bytes and x.sha256 == y.sha256
    assert str(a).encode() not in x.source_bytes and str(b).encode() not in y.source_bytes


def test_complementary_and_identical_sources_have_same_intent(tmp_path):
    value = fields('goal'); file_value = {k: v for k, v in value.items() if k != 'statement'}
    path = tmp_path / 'fields.json'; path.write_bytes(json.dumps(file_value).encode())
    a = read_artifact_create_input('goal', input=str(path),
        options={'--statement': value['statement'], '--title': value['title']}, stdin=UnusedStdin())
    assert a.source_bytes == normalize_artifact_create_input('goal', value).source_bytes


def test_language_spelling_normalizes_without_rewriting_prose_or_force():
    value = fields('requirement'); value.update(language='de-de', statement='  A\u0308 muss wörtlich bleiben.  ')
    prepared = normalize_artifact_create_input('requirement', value)
    assert prepared.fields['language'] == 'de-DE'
    assert prepared.fields['statement'] == value['statement']
    assert prepared.fields['normative_force'] == 'must'


def test_only_empty_relation_and_extension_containers_are_defaulted():
    value = {'title': 'Goal', 'statement': 'Literal statement', 'owner': 'engineering'}
    prepared = normalize_artifact_create_input('goal', value)
    assert prepared.fields == {**value, 'relations': [], 'extensions': {}}
    assert value == {'title': 'Goal', 'statement': 'Literal statement', 'owner': 'engineering'}


@pytest.mark.parametrize('field', sorted(GENERATED))
def test_no_input_can_supply_allocated_identity_audit_or_maturity(field, tmp_path):
    value = fields('goal'); value[field] = 'not caller-controlled here'
    before = inventory(tmp_path)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no identity allocation')):
        with pytest.raises(AuthoringError) as error: normalize_artifact_create_input('goal', value)
    assert error.value.exit_code == 3 and error.value.pointer == '/' + field
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['evidence', 'baseline', 'proposal', 'relation_review'])
def test_specialized_records_cannot_enter_generic_create_input(kind):
    with pytest.raises(AuthoringError) as error: normalize_artifact_create_input(kind, fields('goal'))
    assert error.value.reason == 'specialized_operation_required' and error.value.exit_code == 3


@pytest.mark.parametrize('raw', [b'[]', b'null', b'{broken', b'{"title":"a","title":"b"}',
                                b'{} {}', b'{"title":"\xff"}'])
def test_invalid_json_is_rejected_without_a_stdin_fallback(tmp_path, raw):
    path = tmp_path / 'input.json'; path.write_bytes(raw); before = inventory(tmp_path)
    with no_write_attempts():
        with pytest.raises(AuthoringError) as error:
            read_artifact_create_input('goal', input=str(path), stdin=UnusedStdin())
    assert error.value.exit_code == 3 and inventory(tmp_path) == before


@pytest.mark.parametrize('tokens', [[], ['goal', '--unknown', 'value'], ['goal', '--input'],
    ['goal', '--title', 'one', '--title', 'two'], ['goal', 'extra']])
def test_bad_option_tokens_never_read_stdin(tokens, tmp_path):
    with no_write_attempts():
        with pytest.raises(AuthoringError) as error:
            parse_artifact_create_input(tokens, cwd=tmp_path, stdin=UnusedStdin())
    assert error.value.exit_code == 2


@pytest.mark.parametrize('kind', ['link', 'directory', 'missing'])
def test_explicit_input_path_keeps_native_security_and_io_classes(tmp_path, kind):
    source = tmp_path / 'source.json'; source.write_bytes(json.dumps(fields('goal')).encode())
    path = tmp_path / 'input'
    if kind == 'link': path.symlink_to(source)
    elif kind == 'directory': path.mkdir()
    before = inventory(tmp_path)
    with no_write_attempts():
        with pytest.raises(AuthoringError) as error:
            read_artifact_create_input('goal', input=str(path), stdin=UnusedStdin())
    assert error.value.exit_code == (5 if kind == 'missing' else 7)
    assert inventory(tmp_path) == before


def test_literal_dash_filename_is_distinct_from_explicit_stdin(tmp_path):
    path = tmp_path / '-'; value = fields('goal'); path.write_bytes(json.dumps(value).encode())
    result = read_artifact_create_input('goal', input='./-', cwd=tmp_path, stdin=UnusedStdin())
    assert result.fields == value


def test_chunked_binary_stdin_is_complete_and_remains_caller_owned():
    value = fields('goal'); value['statement'] = 'literal ä{} $() text ' * 14000
    raw = json.dumps(value, ensure_ascii=False).encode()
    class Chunked(BytesIO):
        def read(self, size):
            assert 0 < size <= 65536
            return super().read(min(size, 7919))
    stream = Chunked(raw)
    result = read_artifact_create_input('goal', input='-', stdin=stream)
    assert result.fields == value and stream.tell() == len(raw) and not stream.closed


def test_conflicting_sources_do_not_plan_or_allocate(tmp_path):
    path = tmp_path / 'input.json'; path.write_bytes(json.dumps(fields('goal')).encode()); before = inventory(tmp_path)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no identity allocation')):
        with pytest.raises(AuthoringError) as error:
            read_artifact_create_input('goal', input=str(path), options={'--title': 'Different'}, stdin=UnusedStdin())
    assert error.value.reason == 'authoring_input_conflict' and error.value.exit_code == 2
    assert inventory(tmp_path) == before


def test_preparation_feeds_the_existing_requirement_constructor_and_authoring_binding(tmp_path):
    value = fields('requirement'); raw = json.dumps(value).encode(); path = tmp_path / 'input.json'; path.write_bytes(raw)
    prepared = [normalize_artifact_create_input('requirement', value),
        read_artifact_create_input('requirement', input=str(path), stdin=UnusedStdin()),
        read_artifact_create_input('requirement', input='-', stdin=BytesIO(raw))]
    identity = ArtifactIdentity('SR-REQ-' + '0' * 26, 'random128-v1', 'requirement', 'SR')
    actor = Actor('human', 'declared test actor'); timestamp = UtcTimestamp('2026-01-01T00:00:00Z')
    before = inventory(tmp_path); requests = []
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('identity is already explicit')):
        for item in prepared:
            draft = prepare_requirement(item.fields, identity=identity, actor=actor, planned_at=timestamp)
            requests.append(prepare_authoring_request(command_id='artifact create', actor=actor,
                operations=[{'op': 'create', 'artifact': draft.data, 'result_id': identity.id}],
                dry_run=True))
    assert len({request.sha256 for request in requests}) == 1
    assert all(request.data['write_authorized'] is False and request.data['route'] == 'preview' for request in requests)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('distribution', ['module', 'zipapp'])
def test_built_distribution_reads_real_binary_stdin_without_project_imports(tmp_path, distribution):
    root = Path(__file__).resolve().parents[1]; output = tmp_path / 'build'
    built = build_core(root, output); assert built.returncode == 0, built.stderr
    (tmp_path / 'sitecustomize.py').write_text("raise AssertionError('project code imported')\n")
    source = output / ('module' if distribution == 'module' else 'specroad.pyz')
    body = '''import sys
sys.path.insert(0, sys.argv[1])
from specroad.authoring.inputs import parse_artifact_create_input
prepared = parse_artifact_create_input(['goal', '--input', '-'])
sys.stdout.buffer.write(prepared.source_bytes)
'''
    value = fields('goal'); value['statement'] = "Literal __import__('os').system('never execute')"
    process = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', body, str(source)],
        input=json.dumps(value).encode(), capture_output=True, cwd=tmp_path, env=process_environment())
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {'format_version': '1.0.0', 'command_id': 'artifact.create',
                                        'artifact_type': 'goal', 'fields': value}
