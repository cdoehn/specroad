"""Bounded RFC6455 WebSocket client for Codex's existing local Unix socket.

No network listener, subprocess, auth token, or new daemon is created here.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import struct
import time
from .errors import ControlError
from . import codex_socket
from .local import decode_object

from .codex_limits import MAX_LINE, MAX_RESPONSE
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class UnixWebSocket:
    def __init__(self, codex_home):
        self.buffer = bytearray()
        self.sock = None
        try:
            path = Path(codex_home) / "app-server-control" / "app-server-control.sock"
            target = codex_socket.trusted_daemon_socket(path)
            # Capture the on-disk identity before connecting: a pathname check
            # must not turn into unconditional trust of a changed symlink.
            original = path.lstat()
            endpoint = target.lstat()
            destination = os.readlink(path) if stat.S_ISLNK(original.st_mode) else None
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            try:
                self.sock.connect(str(target))
            except (ConnectionRefusedError, FileNotFoundError, socket.timeout):
                raise ControlError("codex_daemon_unavailable", "The existing Codex daemon socket is not accepting connections.") from None
            except PermissionError:
                raise ControlError("codex_socket_access_denied", "Cannot access the existing Codex daemon socket.") from None
            # A group-writable user home may contain a private Codex link
            # directory. Credential verification protects the actual peer, not
            # merely the pathname metadata. SO_PEERCRED is Linux-specific.
            if codex_socket.connected_peer_uid(self.sock) != os.getuid():
                raise ControlError("codex_socket_untrusted", "The connected Codex daemon is owned by another user.")
            if (codex_socket.socket_identity(path) != codex_socket.identity(original) or
                    codex_socket.socket_identity(target) != codex_socket.identity(endpoint) or
                    (destination is not None and os.readlink(path) != destination) or
                    codex_socket.trusted_daemon_socket(path) != target):
                raise ControlError("codex_socket_untrusted", "Codex daemon socket path changed during connection.")
            self._handshake()
        except ControlError:
            self.close()
            raise
        except OSError:
            self.close()
            raise ControlError("codex_daemon_unavailable", "Unable to contact the existing Codex daemon socket.") from None

    def _receive(self, count, deadline):
        while len(self.buffer) < count:
            remain = None if deadline is None else deadline - time.monotonic()
            if remain is not None and remain <= 0:
                raise ControlError("codex_protocol_timeout", "Codex did not reply before the deadline.")
            self.sock.settimeout(remain)
            try:
                raw = self.sock.recv(min(65536, max(count - len(self.buffer), 1)))
            except socket.timeout:
                raise ControlError("codex_protocol_timeout", "Codex did not reply before the deadline.") from None
            except OSError:
                raise ControlError("codex_connection_lost", "Codex daemon connection failed.") from None
            if not raw:
                raise ControlError("codex_connection_lost", "Codex daemon closed the connection.")
            self.buffer.extend(raw)
        result = bytes(self.buffer[:count]); del self.buffer[:count]
        return result

    def _handshake(self):
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = ("GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n"
                   "Connection: Upgrade\r\nSec-WebSocket-Key: " + key + "\r\n"
                   "Sec-WebSocket-Version: 13\r\n\r\n").encode("ascii")
        self.sock.sendall(request)
        deadline = time.monotonic() + 5
        header = bytearray()
        while not header.endswith(b"\r\n\r\n"):
            if len(header) > 8192:
                raise ControlError("codex_handshake_failed", "Oversized Codex WebSocket handshake.")
            header.extend(self._receive(1, deadline))
        try:
            lines = header.decode("ascii").split("\r\n")
            fields = {}
            for line in lines[1:]:
                if not line:
                    continue
                name, value = line.split(":", 1)
                name = name.strip().lower()
                if name in fields:
                    raise ValueError
                fields[name] = value.strip()
            expected = base64.b64encode(hashlib.sha1((key + _WS_GUID).encode()).digest()).decode()
            if (not lines[0].startswith("HTTP/1.1 101 ") or
                    fields.get("sec-websocket-accept") != expected or
                    fields.get("upgrade", "").lower() != "websocket" or
                    "upgrade" not in {token.strip().lower() for token in fields.get("connection", "").split(",")} or
                    "sec-websocket-extensions" in fields or
                    "sec-websocket-protocol" in fields):
                raise ValueError
        except (ValueError, UnicodeError):
            raise ControlError("codex_handshake_failed", "The existing daemon did not complete the WebSocket upgrade.") from None

    def _frame(self, payload: bytes, opcode=1):
        mask = os.urandom(4)
        size = len(payload)
        header = bytearray([0x80 | opcode, 0x80 | min(size, 126 if size <= 65535 else 127)])
        if size > 65535:
            header.extend(struct.pack("!Q", size))
        elif size >= 126:
            header.extend(struct.pack("!H", size))
        return bytes(header) + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(payload))

    def send(self, document):
        payload = json.dumps(document, separators=(",", ":")).encode()
        if len(payload) > MAX_LINE:
            raise ControlError("codex_protocol_error", "Outgoing Codex RPC message is too large.")
        self._send_frame(payload, opcode=1)

    def read(self, timeout: float | None = 15):
        """Read one JSON-RPC message, handling RFC6455 ping and text fragments."""
        deadline = None if timeout is None else time.monotonic() + timeout
        assembled = bytearray()
        continuation = False
        while True:
            header = self._receive(2, deadline)
            first, second = header
            if first & 0x70 or second & 0x80:
                raise ControlError("codex_protocol_error", "Invalid WebSocket framing from the Codex daemon.")
            opcode, fin = first & 15, bool(first & 0x80)
            size = second & 0x7f
            if size == 126:
                size = struct.unpack("!H", self._receive(2, deadline))[0]
                if size < 126:
                    raise ControlError("codex_protocol_error", "Noncanonical WebSocket frame size.")
            elif size == 127:
                size = struct.unpack("!Q", self._receive(8, deadline))[0]
                if size <= 65535 or size >= 2**63:
                    raise ControlError("codex_protocol_error", "Noncanonical WebSocket frame size.")
            # Validate framing before reading an announced body. Control frames
            # do not contribute bytes to a fragmented text message.
            if opcode >= 8:
                if opcode not in (8, 9, 10) or not fin or size > 125:
                    raise ControlError("codex_protocol_error", "Invalid WebSocket control frame.")
                payload = self._receive(size, deadline)
                if opcode == 8:
                    raise ControlError("codex_connection_lost", "Codex daemon closed the WebSocket.")
                if opcode == 9:
                    self._send_frame(payload, opcode=10)
                continue
            if opcode == 1 and not continuation:
                continuation = True
            elif opcode != 0 or not continuation:
                raise ControlError("codex_protocol_error", "Unexpected Codex WebSocket message type.")
            if size > MAX_RESPONSE or len(assembled) + size > MAX_RESPONSE:
                self.close()
                raise ControlError("codex_response_too_large", "Codex daemon WebSocket response exceeds the bounded receive budget.",
                                   details={"limit_bytes": MAX_RESPONSE, "announced_bytes": len(assembled) + size})
            payload = self._receive(size, deadline)
            assembled.extend(payload)
            if not fin:
                continue
            try:
                return decode_object(assembled)
            except (ValueError, TypeError, UnicodeError, RecursionError):
                raise ControlError("codex_protocol_error", "Invalid JSON RPC message from Codex daemon.") from None

    def _send_frame(self, payload: bytes, opcode: int):
        if opcode >= 8 and len(payload) > 125:
            raise ControlError("codex_protocol_error", "Oversized WebSocket control frame.")
        try:
            self.sock.settimeout(5)
            self.sock.sendall(self._frame(payload, opcode))
        except OSError:
            raise ControlError("codex_connection_lost", "The existing Codex daemon connection was lost.") from None

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None
