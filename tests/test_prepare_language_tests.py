"""Explicit setup mechanics; controlled probe results are not runtime proofs."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import prepare_language_tests as setup
from language_packaging.inventory import NUMPY
from language_packaging.runtime_matrix import load_runtime_matrix


def prepared_inputs(tmp_path, monkeypatch, invalid=None):
    python = tmp_path / 'python'; python.mkdir()
    wheels = tmp_path / 'wheels'; wheels.mkdir()
    for minor in NUMPY:
        binary = python / ('cpython-' + minor + '.1-linux-x86_64-gnu') / 'bin' / ('python' + minor)
        binary.parent.mkdir(parents=True)
        binary.write_bytes(('owned controlled probe ' + minor).encode()); binary.chmod(0o700)
    calls, wheel_reads = [], []
    def probe(command, **options):
        calls.append((command, options))
        minor = Path(command[0]).name[len('python'):]
        assert command[1:4] == ['-I', '-B', '-c']
        assert options['stdin'] == setup.subprocess.DEVNULL and options['check'] is True
        assert set(options['env']) == {'PATH', 'LANG'} and 'timeout' not in options
        identity = ['cpython', minor + '.1', 'linux', 'x86_64', False]
        if invalid == 'version': identity[1] = '3.9.1'
        elif invalid == 'platform': identity[2] = 'win32'
        elif invalid == 'free_threaded': identity[4] = True
        elif invalid == 'changed_binary': Path(command[0]).write_bytes(b'replaced')
        return SimpleNamespace(stdout=json.dumps(identity).encode())
    def read_wheels(path, minor):
        assert path == wheels
        wheel_reads.append(minor)
        if invalid == 'wheel': raise ValueError('Wheel hash mismatch')
    monkeypatch.setattr(setup.subprocess, 'run', probe)
    monkeypatch.setattr(setup, 'read_wheels', read_wheels)
    return python, wheels, calls, wheel_reads


def test_explicit_preparation_checks_all_five_selected_runtimes_and_wheel_sets(tmp_path, monkeypatch):
    python, wheels, calls, wheel_reads = prepared_inputs(tmp_path, monkeypatch)
    output = tmp_path / 'runtimes.json'
    result = setup.prepare(python, wheels, output)
    assert load_runtime_matrix(output) == result
    assert len(calls) == 5 and wheel_reads == list(NUMPY)
    assert all(Path(row['executable']).is_relative_to(python) for row in result['interpreters'].values())


@pytest.mark.parametrize('invalid', ['version', 'platform', 'free_threaded', 'changed_binary', 'wheel'])
def test_failed_preparation_publishes_no_runtime_manifest(tmp_path, monkeypatch, invalid):
    python, wheels, _, _ = prepared_inputs(tmp_path, monkeypatch, invalid)
    output = tmp_path / 'runtimes.json'
    with pytest.raises(ValueError): setup.prepare(python, wheels, output)
    assert not output.exists()


def test_existing_local_selection_is_preserved_without_processes(tmp_path, monkeypatch):
    python, wheels, calls, wheel_reads = prepared_inputs(tmp_path, monkeypatch)
    output = tmp_path / 'runtimes.json'; output.write_bytes(b'existing operator selection')
    with pytest.raises(FileExistsError): setup.prepare(python, wheels, output)
    assert output.read_bytes() == b'existing operator selection' and calls == wheel_reads == []


def test_ambiguous_minor_is_not_silently_chosen(tmp_path, monkeypatch):
    python, wheels, calls, _ = prepared_inputs(tmp_path, monkeypatch)
    extra = python / 'cpython-3.10.2-linux-x86_64-gnu/bin/python3.10'
    extra.parent.mkdir(parents=True); extra.write_bytes(b'other prepared runtime')
    output = tmp_path / 'runtimes.json'
    with pytest.raises(ValueError): setup.prepare(python, wheels, output)
    assert calls == [] and not output.exists()
