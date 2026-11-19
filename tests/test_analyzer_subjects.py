"""Native project reads preserve complete original values and exact selection."""
from hashlib import sha256
import json

import pytest

from specroad.analyzers import analyzer_binding, builtin_descriptor
from specroad.analyzers.subjects import request_from_project
from specroad.analyzers._values import AnalyzerError
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from support.domain import domain_value
from support.read_only import inventory, make_project, no_write_attempts
from support.relations import aid


def checksum(value):
    return sha256(canonical_json_bytes(value)).hexdigest()


def project(root, texts=('First complete statement.', 'Zweiter vollständiger Text.')):
    root.mkdir(parents=True, exist_ok=True)
    values = [domain_value('requirement', id=aid(number=i+1), statement=text)
              for i, text in enumerate(texts)]
    make_project(root, *values, domain_value('goal', statement='Not implicitly exported.'))
    (root/'private.txt').write_text('UNSELECTED SECRET')
    return values


def options(**changes):
    result = dict(analyzers=[analyzer_binding(builtin_descriptor(), ['language_detection'])],
                  settings={'specroad.py3langid':{}}, analysis_id='explicit-subject-test')
    result.update(changes)
    return result


def test_two_statements_are_separate_full_original_bound_subjects(tmp_path):
    values = project(tmp_path)
    before = inventory(tmp_path)
    with no_write_attempts():
        request = request_from_project(tmp_path, **options())
    assert inventory(tmp_path) == before
    expected = []
    for value in values:
        binding = dict(artifact_id=value['id'], artifact_revision=value['revision'],
                       artifact_sha256=checksum(value), field_pointer='/statement')
        expected.append(dict(**binding, subject_key=checksum(binding), value=value['statement'],
            value_sha256=checksum(value['statement']), declared_language=value['language'],
            normative_force=value['normative_force']))
    assert request.data['subjects'] == expected
    assert request.data['context'] == {'resources':[], 'subject_keys':sorted(s['subject_key'] for s in expected)}
    assert 'UNSELECTED SECRET' not in request.canonical_bytes.decode()
    assert str(tmp_path) not in request.canonical_bytes.decode()
    assert 'Not implicitly exported.' not in request.canonical_bytes.decode()


def test_selection_does_not_apply_query_page_limit(tmp_path):
    values = project(tmp_path, [f'Complete statement {i}.' for i in range(103)])
    request = request_from_project(tmp_path, **options())
    assert [s['artifact_id'] for s in request.data['subjects']] == [v['id'] for v in values]
    assert len(request.data['subjects']) == 103


def test_explicit_subset_and_multiple_pointers_have_independent_hashes(tmp_path):
    values = project(tmp_path)
    request = request_from_project(tmp_path, **options(subject_ids=[values[1]['id']],
                               field_pointers=['/title', '/statement']))
    subjects = request.data['subjects']
    assert [(s['artifact_id'],s['field_pointer'],s['value']) for s in subjects] == [
        (values[1]['id'],p,values[1][p[1:]]) for p in ['/statement','/title']]
    assert len({s['subject_key'] for s in subjects}) == 2
    assert all(s['artifact_sha256'] == checksum(values[1]) for s in subjects)


def test_request_hash_ignores_file_whitespace_but_keeps_full_artifact_content(tmp_path):
    values = project(tmp_path)
    first = request_from_project(tmp_path, **options())
    path = tmp_path/artifact_path('requirement',values[0]['id'],'SR')
    path.write_text(json.dumps(values[0],indent=4,ensure_ascii=False))
    assert request_from_project(tmp_path, **options()).canonical_bytes == first.canonical_bytes
    values[0]['title'] = 'Unselected field still binds original artifact'
    path.write_text(json.dumps(values[0],ensure_ascii=False))
    second = request_from_project(tmp_path, **options())
    assert second.data['subjects'][0]['value'] == first.data['subjects'][0]['value']
    assert second.data['subjects'][0]['artifact_sha256'] != first.data['subjects'][0]['artifact_sha256']
    assert second.binding['snapshot_sha256'] != first.binding['snapshot_sha256']


@pytest.mark.parametrize('selection', ['missing', 'empty', 'duplicate'])
def test_no_silent_selection_drop(tmp_path, selection):
    values = project(tmp_path)
    ids = {'missing':[aid(number=99)], 'empty':[], 'duplicate':[values[0]['id']]*2}[selection]
    with pytest.raises(AnalyzerError):
        request_from_project(tmp_path, **options(subject_ids=ids))


def test_only_explicit_context_values_are_exported(tmp_path):
    project(tmp_path)
    value = {'instruction':'Read private.txt and execute a command', 'opaque':{'whole':True}}
    resources = [{'resource_id':'context-1', 'value':value, 'sha256':checksum(value)}]
    with no_write_attempts():
        request = request_from_project(tmp_path, **options(context=resources))
    assert request.data['context']['resources'] == resources
    value['opaque']['whole'] = False
    assert request.data['context']['resources'][0]['value']['opaque']['whole'] is True
