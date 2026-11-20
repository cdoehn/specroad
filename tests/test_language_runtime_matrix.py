"""Runtime prerequisites are explicit, complete and bound to local bytes."""
from hashlib import sha256
import json

import pytest

from language_packaging.inventory import NUMPY
from language_packaging.runtime_matrix import load_runtime_matrix


def configuration(tmp_path):
    wheelhouse = tmp_path / 'wheels'; wheelhouse.mkdir()
    interpreters = {}
    for minor in NUMPY:
        executable = tmp_path / ('python-' + minor)
        executable.write_bytes(('owned identity fixture ' + minor).encode())
        executable.chmod(0o700)
        interpreters[minor] = dict(executable=str(executable), version=minor + '.1',
                                  sha256=sha256(executable.read_bytes()).hexdigest())
    value = dict(format_version=1, kind='specroad-language-test-runtimes-v1',
                 wheelhouse=str(wheelhouse), interpreters=interpreters)
    return tmp_path / 'runtimes.json', value


def write(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def test_complete_prerequisites_load_without_execution_or_claiming_verification(tmp_path, monkeypatch):
    path, value = configuration(tmp_path)
    write(path, value)
    monkeypatch.setenv('SPECROAD_LANGUAGE_TEST_RUNTIMES', str(path))
    assert load_runtime_matrix() == value
    assert load_runtime_matrix(path) == value


def test_missing_manifest_never_skips_or_discovers_another_interpreter(tmp_path):
    with pytest.raises(ValueError, match='Missing explicitly prepared'):
        load_runtime_matrix(tmp_path / 'missing.json')


@pytest.mark.parametrize('invalid', ['missing_minor', 'extra_minor', 'format_bool', 'foreign_kind',
    'extra_field', 'relative_wheels', 'missing_wheels', 'relative_executable', 'parent_component',
    'wrong_version', 'wrong_hash', 'missing_executable', 'not_executable', 'duplicate_path',
    'extra_binding', 'linked_executable', 'linked_parent', 'linked_wheels', 'linked_manifest'])
def test_unbound_or_incomplete_matrix_is_rejected(tmp_path, invalid):
    path, value = configuration(tmp_path)
    row = value['interpreters']['3.10']
    from pathlib import Path
    executable = Path(row['executable'])
    if invalid == 'missing_minor': del value['interpreters']['3.12']
    elif invalid == 'extra_minor': value['interpreters']['3.15'] = dict(row)
    elif invalid == 'format_bool': value['format_version'] = True
    elif invalid == 'foreign_kind': value['kind'] = 'unknown'
    elif invalid == 'extra_field': value['fallback'] = True
    elif invalid == 'relative_wheels': value['wheelhouse'] = 'wheels'
    elif invalid == 'missing_wheels': value['wheelhouse'] = str(tmp_path / 'missing')
    elif invalid == 'relative_executable': row['executable'] = 'python'
    elif invalid == 'parent_component': row['executable'] = str(tmp_path / '..' / executable.name)
    elif invalid == 'wrong_version': row['version'] = '3.11.1'
    elif invalid == 'wrong_hash': row['sha256'] = '0' * 64
    elif invalid == 'missing_executable': executable.unlink()
    elif invalid == 'not_executable': executable.chmod(0o600)
    elif invalid == 'duplicate_path': value['interpreters']['3.11']['executable'] = str(executable)
    elif invalid == 'extra_binding': row['fallback'] = True
    elif invalid == 'linked_executable':
        target = tmp_path / 'original'; executable.rename(target); executable.symlink_to(target)
    elif invalid == 'linked_parent':
        link = tmp_path / 'link'; link.symlink_to(tmp_path, target_is_directory=True)
        row['executable'] = str(link / executable.name)
    elif invalid == 'linked_wheels':
        link = tmp_path / 'link'; link.symlink_to(value['wheelhouse'], target_is_directory=True)
        value['wheelhouse'] = str(link)
    write(path, value)
    if invalid == 'linked_manifest':
        original = path; path = tmp_path / 'link.json'; path.symlink_to(original)
    with pytest.raises((ValueError, OSError)):
        load_runtime_matrix(path)


def test_duplicate_json_fields_cannot_rebind_an_interpreter(tmp_path):
    path, value = configuration(tmp_path)
    path.write_text(json.dumps(value)[:-1] + ',"format_version":1}', encoding='utf-8')
    with pytest.raises(ValueError, match='Duplicate'):
        load_runtime_matrix(path)
