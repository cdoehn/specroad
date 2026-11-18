"""One Linux host capability, no remote commands or package-supplied authority."""
from contextlib import contextmanager
import hmac
import json
import os
import secrets
import socket
import struct
import sys
import threading

from ._files import require

_ENV_LOCK = threading.Lock()
_FIELDS = ('SPECROAD_RETURN_PYTHON', 'SPECROAD_RETURN_SOCKET', 'SPECROAD_RETURN_TOKEN', 'SPECROAD_RETURN_TIMEOUT')


@contextmanager
def receiver_channel(receive, timeout):
    # Linux abstract sockets avoid PATH_MAX/AF_UNIX path truncation. Both a
    # same-uid peer and the independent one-use capability are mandatory.
    token = secrets.token_hex(32)
    name = 'specroad-return-' + secrets.token_hex(24)
    stop = threading.Event()
    outcome = {'result': None, 'error': None}
    with _ENV_LOCK, socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind('\0' + name); listener.listen(1); listener.settimeout(0.2)
        old = {k: os.environ.get(k) for k in _FIELDS}
        def serve():
            while not stop.is_set():
                try:
                    connection, _ = listener.accept()
                except socket.timeout:
                    continue
                with connection:
                    connection.settimeout(min(timeout, 30))
                    try:
                        _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                        require(uid == os.getuid(), 'return_host_peer_rejected')
                        raw = bytearray()
                        while not raw.endswith(b'\n'):
                            part = connection.recv(1024)
                            require(bool(part) and len(raw) + len(part) <= 4096, 'return_host_request_invalid')
                            raw.extend(part)
                        value = json.loads(raw)
                        require(type(value) is dict and set(value) == {'token'}
                            and type(value['token']) is str and hmac.compare_digest(value['token'], token),
                            'return_host_capability_rejected')
                        outcome['result'] = receive()
                        connection.sendall(b'{"status":"proposal_received"}\n')
                    except BaseException as error:
                        outcome['error'] = error
                        try: connection.sendall(b'{"status":"failed"}\n')
                        except OSError: pass
                    return
        thread = threading.Thread(target=serve, name='specroad-return-receiver')
        os.environ.update(dict(zip(_FIELDS, (sys.executable, name, token, str(timeout)))))
        thread.start()
        try:
            yield outcome
        finally:
            stop.set(); thread.join()
            for key, value in old.items():
                if value is None: os.environ.pop(key, None)
                else: os.environ[key] = value
