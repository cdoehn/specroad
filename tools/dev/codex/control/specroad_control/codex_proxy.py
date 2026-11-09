"""Metadata-only Codex RPC: preserve the exact Dev thread and refuse approvals.

A direct Unix WebSocket client attaches to the ALREADY running daemon.
"""
from collections import deque
from pathlib import Path
import time
from .config import Config, thread_directories
from .errors import ControlError
from .telemetry import record
from .codex_ws import UnixWebSocket, MAX_LINE
from .codex_history import TurnHistory
from .continuation_history import ContinuationHistory
from .codex_limits import MAX_LOG, MAX_PENDING_BYTES, json_size as _json_size


class Proxy:
    """RPC to the existing app-server, never a daemon/thread launcher."""
    def __init__(self, config: Config, pass_fds=(), *, continuation=False):
        self.config = config
        self.sequence = 0
        self.pending = deque()
        self.connection = None
        try:
            self.connection = UnixWebSocket(config.codex_home)
            self.call("initialize", {"clientInfo": {"name": "specroad_control", "version": "0.2.1"},
                                    **({'capabilities': {'experimentalApi': True}} if continuation else {})})
            self.send({"method": "initialized", "params": {}})
        except (ControlError, OSError):
            self.close()
            raise

    def send(self, document):
        self.connection.send(document)

    def read(self, timeout: float | None = 15):
        return self.connection.read(timeout)

    def call(self, method, params):
        self.sequence += 1
        request_id = self.sequence
        self.send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + 15
        while True:
            try:
                message = self.read(max(0, deadline - time.monotonic()))
            except ControlError as exc:
                if exc.code == "codex_response_too_large":
                    record("codex_response_limit", error=exc.code, rpc_method=method,
                           limit_bytes=exc.details.get("limit_bytes"),
                           announced_bytes=exc.details.get("announced_bytes"))
                raise
            if message.get("id") == request_id and "method" not in message:
                if "error" in message or not isinstance(message.get("result"), dict):
                    rpc_code = message.get('error', {}).get('code') if isinstance(message.get('error'), dict) else None
                    raise ControlError("codex_request_rejected", "The existing daemon rejected the protocol operation.",
                                       details={"rpc_method": method, "rpc_code": rpc_code if type(rpc_code) is int else None})
                return message["result"]
            if "id" in message and "method" in message:
                self.deny(message)
            else:
                retained = sum(_json_size(value) for value in self.pending)
                incoming = _json_size(message)
                if len(self.pending) >= 256:
                    self.close()
                    record("codex_event_limit", error="codex_event_backlog", rpc_method=method,
                           event_limit=256, queued_events=len(self.pending) + 1)
                    raise ControlError("codex_event_backlog", "Too many events before the requested reply.")
                if retained + incoming > MAX_PENDING_BYTES:
                    self.close()
                    record("codex_response_limit", error="codex_response_too_large", rpc_method=method,
                           limit_bytes=MAX_PENDING_BYTES, announced_bytes=retained + incoming)
                    raise ControlError("codex_response_too_large", "Pending Codex notifications exceed the bounded receive budget.",
                                       details={"limit_bytes": MAX_PENDING_BYTES, "announced_bytes": retained + incoming})
                self.pending.append(message)

    def deny(self, message):
        self.send({"id": message["id"], "error": {"code": -32601, "message": "No automatic approval/input handler"}})

    def inspect_identity(self, *, include_turns=False):
        result = self.call("thread/read", {"threadId": self.config.session_id, **({"includeTurns": True} if include_turns else {})})
        thread = result.get("thread")
        if not isinstance(thread, dict) or thread.get("id") != self.config.session_id:
            raise ControlError("wrong_thread", "The configured thread was not resolved exactly.")
        return thread

    def inspect_thread(self, *, include_turns=False):
        thread = self.inspect_identity(include_turns=include_turns)
        if not isinstance(thread.get("cwd"), str) or Path(thread["cwd"]).resolve() not in thread_directories(self.config):
            raise ControlError("wrong_thread_repository", "The thread does not belong to the configured Dev directory.")
        return thread

    def thread(self):
        thread = self.inspect_thread()
        status = thread.get("status", {})
        if not isinstance(status, dict) or status.get("type") not in ("idle", "notLoaded"):
            raise ControlError("dev_thread_busy", "The Dev thread is active or its activity cannot be established.",
                               details={'thread_status': 'active' if self.status_type(thread) == 'active' else 'unknown'})
        return thread

    @staticmethod
    def status_type(thread):
        status = thread.get("status")
        return status.get("type") if isinstance(status, dict) else "unknown"

    def inspect_turn(self, turn_id):
        return TurnHistory(self).inspect(turn_id)

    def inspect_continuation(self, turn_id):
        return ContinuationHistory(self).inspect(turn_id)

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()
