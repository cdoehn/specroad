"""The write-attempt oracle distinguishes permitted process IPC from files."""
import builtins
import io
import os
import socket
import subprocess
import sys

import pytest

from support.read_only import inventory, no_write_attempts


@pytest.mark.parametrize('text', [False, True])
def test_allowed_real_process_roundtrips_stdin_without_filesystem_changes(tmp_path, text):
    payload = 'complete worker input' if text else b'complete\x00worker\xffinput'
    before = inventory(tmp_path)
    with no_write_attempts(allow_subprocess=True) as attempts:
        result = subprocess.run(
            [sys.executable, '-I', '-S', '-B', '-c',
             'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())'],
            input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=tmp_path, text=text, check=True, timeout=30)
    assert result.stdout == payload and not result.stderr
    assert attempts == [] and inventory(tmp_path) == before


@pytest.mark.parametrize('opener', ['builtins', 'io'], ids=['open0', 'open1'])
@pytest.mark.parametrize('descriptor', [False, True])
def test_allowed_process_flag_still_rejects_file_paths_and_regular_descriptors(
        tmp_path, opener, descriptor):
    target = tmp_path/'original'
    target.write_bytes(b'unchanged')
    with target.open('r+b') as stream:
        before = inventory(tmp_path)
        with pytest.raises(AssertionError):
            with no_write_attempts(allow_subprocess=True) as attempts:
                # Resolve after the guard installs its wrappers; a callable
                # captured during collection would bypass the write oracle.
                active_opener = builtins.open if opener == 'builtins' else io.open
                try:
                    with active_opener(stream.fileno() if descriptor else target, 'wb',
                                       **({'closefd': False} if descriptor else {})) as output:
                        output.write(b'forbidden')
                except AssertionError:
                    pass
        assert len(attempts) == 1 and inventory(tmp_path) == before


@pytest.mark.parametrize('operation', ['create', 'mkdir', 'unlink', 'replace', 'socket'])
def test_process_permission_does_not_enable_filesystem_or_network_operations(tmp_path, operation):
    target = tmp_path/'original'
    target.write_bytes(b'unchanged')
    before = inventory(tmp_path)
    with pytest.raises(AssertionError):
        with no_write_attempts(allow_subprocess=True) as attempts:
            try:
                if operation == 'create':
                    descriptor = os.open(tmp_path/'new', os.O_WRONLY | os.O_CREAT, 0o600)
                    os.close(descriptor)
                elif operation == 'mkdir':
                    os.mkdir(tmp_path/'new')
                elif operation == 'unlink':
                    os.unlink(target)
                elif operation == 'replace':
                    os.replace(target, tmp_path/'new')
                else:
                    socket.socket().close()
            except AssertionError:
                pass
    assert len(attempts) == 1 and inventory(tmp_path) == before


def test_default_guard_still_forbids_process_creation():
    with pytest.raises(AssertionError):
        with no_write_attempts() as attempts:
            try:
                subprocess.run([sys.executable, '-I', '-S', '-B', '-c', 'pass'],
                               check=True, timeout=30)
            except AssertionError:
                pass
    assert len(attempts) == 1


def test_default_guard_does_not_enable_pipe_writes():
    read_fd, write_fd = os.pipe()
    try:
        with pytest.raises(AssertionError):
            with no_write_attempts() as attempts:
                try:
                    with io.open(write_fd, 'wb', closefd=False) as stream:
                        stream.write(b'forbidden')
                except AssertionError:
                    pass
        assert len(attempts) == 1
    finally:
        os.close(read_fd)
        os.close(write_fd)


@pytest.mark.parametrize('descriptor', [-1, 1 << 100])
def test_invalid_descriptor_is_not_treated_as_an_allowed_pipe(descriptor):
    with pytest.raises(AssertionError):
        with no_write_attempts(allow_subprocess=True) as attempts:
            try:
                io.open(descriptor, 'wb')
            except AssertionError:
                pass
    assert len(attempts) == 1


def test_write_swallowed_after_successful_worker_is_still_reported(tmp_path):
    before = inventory(tmp_path)
    with pytest.raises(AssertionError):
        with no_write_attempts(allow_subprocess=True) as attempts:
            result = subprocess.run(
                [sys.executable, '-I', '-S', '-B', '-c',
                 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())'],
                input=b'worker', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=tmp_path, check=True, timeout=30)
            assert result.stdout == b'worker' and not result.stderr
            try:
                (tmp_path/'forbidden').write_bytes(b'bad')
            except AssertionError:
                pass
    assert len(attempts) == 1 and inventory(tmp_path) == before
