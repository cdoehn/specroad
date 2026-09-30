"""Runtime loader and isolation contracts of trusted test subprocesses."""

import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from support.processes import run_core, run_python


@pytest.mark.parametrize("library_path", [
    None,
    "",
    "/toolcache/Python/3.12/x64/lib",
    "/runtime/first lib:/runtime/second/lib",
])
def test_loader_path_is_preserved_exactly_when_supplied(tmp_path, library_path):
    # Observe the real subprocess API boundary without depending on which
    # Python installation happens to need a loader path on this machine.
    environment = {"PATH": "/must/not/be/inherited", "TEMP": str(tmp_path)}
    expected = {"PATH": "", "TEMP": str(tmp_path)}
    if library_path is not None:
        environment["LD_LIBRARY_PATH"] = library_path
        expected["LD_LIBRARY_PATH"] = library_path
    with patch.dict(os.environ, environment, clear=True):
        before = dict(os.environ)
        with patch("support.processes.subprocess.run") as launch:
            run_python(["-I", "-S", "-B", "-c", "pass"], tmp_path)
        assert launch.call_count == 1
        assert launch.call_args.kwargs["env"] == expected
        assert dict(os.environ) == before


def test_missing_optional_environment_is_not_reconstructed(tmp_path):
    with patch.dict(os.environ, {}, clear=True):
        with patch("support.processes.subprocess.run") as launch:
            run_python(["-I", "-c", "pass"], tmp_path)
        assert launch.call_args.kwargs["env"] == {"PATH": ""}
        assert dict(os.environ) == {}


def test_only_named_runtime_variables_cross_the_process_boundary(tmp_path):
    permitted = {
        "SystemRoot": "/system", "WINDIR": "/windows",
        "TEMP": "/temp", "TMP": "/tmp", "TMPDIR": "/tmpdir",
        "LD_LIBRARY_PATH": "/trusted/runtime/lib",
    }
    denied = {
        name: "not-for-the-child"
        for name in (
            "GH_TOKEN", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "SPECRD_TEST_SECRET",
            "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PYTEST_ADDOPTS",
            "LD_PRELOAD", "LD_AUDIT", "LD_DEBUG", "DYLD_INSERT_LIBRARIES", "BASH_ENV",
        )
    }
    with patch.dict(os.environ, {**permitted, **denied, "PATH": "/tools"}, clear=True):
        before = dict(os.environ)
        with patch("support.processes.subprocess.run") as launch:
            run_python(["-I", "-c", "pass"], tmp_path)
        assert launch.call_args.kwargs["env"] == {**permitted, "PATH": ""}
        assert dict(os.environ) == before


@pytest.mark.parametrize("capture", [False, True])
@pytest.mark.parametrize("explicit_python", [False, True])
def test_launch_keeps_executable_io_and_no_timeout_contract(tmp_path, capture, explicit_python):
    executable = tmp_path / "trusted python" if explicit_python else None
    arguments = ["-I", "-S", "-B", "-c", "raise SystemExit(17)"]
    completed = subprocess.CompletedProcess([], 17, b"out" if capture else None, b"error")
    with patch("support.processes.subprocess.run", return_value=completed) as launch:
        actual = run_python(arguments, tmp_path, python=executable, capture=capture)
    assert actual is completed
    assert launch.call_count == 1
    assert launch.call_args.args == ([str(executable or sys.executable), *arguments],)
    options = launch.call_args.kwargs
    assert options["cwd"] == tmp_path
    assert options["stdin"] == subprocess.DEVNULL
    assert options["stdout"] == (subprocess.PIPE if capture else subprocess.DEVNULL)
    assert options["stderr"] == subprocess.PIPE
    assert options.get("shell", False) is False
    assert options.get("timeout") is None


@pytest.mark.parametrize("explicit_python", [False, True])
def test_live_isolated_python_keeps_runtime_path_without_leaking_secrets(tmp_path, explicit_python):
    # Keep any actually required host path and append an owned empty directory.
    # Never replace the CI interpreter's real library directory with a fake one.
    library_dir = tmp_path / "runtime with spaces"
    library_dir.mkdir()
    inherited = os.environ.get("LD_LIBRARY_PATH")
    library_path = (inherited + os.pathsep if inherited else "") + str(library_dir)
    denied = ("GH_TOKEN", "GITHUB_TOKEN", "SPECRD_TEST_SECRET", "PYTHONPATH",
              "PYTHONHOME", "VIRTUAL_ENV", "LD_PRELOAD", "LD_AUDIT", "BASH_ENV")
    environment = {name: "not-for-the-child" for name in denied}
    environment["LD_LIBRARY_PATH"] = library_path
    body = """
import json, os, ssl, zlib
print(json.dumps({
    'library_path': os.environ.get('LD_LIBRARY_PATH'),
    'blocked': {name: os.environ.get(name) for name in %r},
    'path': os.environ.get('PATH'),
    'stdin': sys.stdin.read(),
    'cwd': os.getcwd(),
    'isolated': sys.flags.isolated,
    'no_site': sys.flags.no_site,
    'no_bytecode': sys.dont_write_bytecode,
    'compression_roundtrip': zlib.decompress(zlib.compress(b'payload')) == b'payload',
    'tls_available': bool(ssl.OPENSSL_VERSION_NUMBER),
}))
""" % (denied,)
    with patch.dict(os.environ, environment):
        before = dict(os.environ)
        completed = run_core(body, tmp_path, capture=True,
                             python=Path(sys.executable) if explicit_python else None)
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout) == {
            "library_path": library_path, "blocked": {name: None for name in denied},
            "path": "", "stdin": "", "cwd": str(tmp_path.resolve()),
            "isolated": 1, "no_site": 1, "no_bytecode": True,
            "compression_roundtrip": True, "tls_available": True,
        }
        assert dict(os.environ) == before
    assert list(tmp_path.iterdir()) == [library_dir]


def test_live_child_failure_is_not_retried_or_replaced_by_success(tmp_path):
    completed = run_python(["-I", "-S", "-B", "-c", "raise SystemExit(17)"],
                           tmp_path, capture=True)
    assert completed.returncode == 17
    assert list(tmp_path.iterdir()) == []
