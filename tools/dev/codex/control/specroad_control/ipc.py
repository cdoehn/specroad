"""Bounded, same-user local IPC. This protocol never sends Codex prompts."""
import hashlib
import json
import os
import socket
import stat
import struct
import time
from .errors import ControlError
from .local import Paths, decode_object


def scope(paths: Paths) -> str:
    return hashlib.sha256(os.fsencode(paths.config)).hexdigest()


def same_user(sock: socket.socket):
    _pid, uid, _gid = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if uid != os.getuid():
        raise ControlError("foreign_peer", "Control requests require the same local user.")


def receive(sock: socket.socket, *, limit: int, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    data = bytearray()
    while b"\n" not in data:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        sock.settimeout(remaining)
        part = sock.recv(min(4096, limit + 1 - len(data)))
        if not part:
            raise ValueError("Incomplete request")
        data.extend(part)
        if len(data) > limit:
            raise ValueError("Request too large")
    return decode_object(data)


def exchange(sock: socket.socket, command: str, request_scope: str) -> dict:
    same_user(sock)
    sock.sendall((json.dumps({"command": command, "scope": request_scope}) + "\n").encode())
    reply = receive(sock, limit=65536, timeout=2.0)
    if type(reply.get("ok")) is not bool:
        raise ControlError("protocol_error", "The controller reply has no boolean success field.")
    if not reply.get("ok"):
        raise ControlError(reply.get("error", "protocol_error"), "The controller rejected the request.")
    return reply


def request(paths: Paths, command: str) -> dict:
    try:
        st = paths.socket.lstat()
        if not stat.S_ISSOCK(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise ControlError("unsafe_socket", "The control endpoint must be a private socket owned by this user.")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2.0)
            client.connect(str(paths.socket))
            return exchange(client, command, scope(paths))
    except (FileNotFoundError, ConnectionRefusedError):
        raise ControlError("not_running", "The background controller is not reachable.") from None
    except (TimeoutError, ValueError, ConnectionError, RecursionError):
        raise ControlError("protocol_error", "The local controller did not provide a valid reply.") from None
