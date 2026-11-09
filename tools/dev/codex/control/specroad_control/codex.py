"""Explicit existing-thread execution; no model-based waiting and no implicit fork."""
import json
import os
from pathlib import Path
import selectors
import subprocess
from .config import Config, child_environment
from .execution_scope import execution_directory, exec_policy_options
from .errors import ControlError
from .local import decode_object, read_private, write_private, json_write

from .codex_proxy import Proxy, MAX_LINE, MAX_LOG
from .proxy_turn import run_proxy_turn
from .local import json_read


class Codex:
    def __init__(self, config: Config, pass_fds=()):
        self.config, self.pass_fds = config, tuple(pass_fds)
        self.observe = lambda **_fields: None

    def check(self):
        with Proxy(self.config, self.pass_fds) as proxy:
            proxy.thread()
        return {"thread_resolved": True, "model_called": False, "transport": self.config.transport,
                "remote_visibility": "not_verified"}

    def activity(self):
        """Observe a known thread state without treating an unknown state as active."""
        with Proxy(self.config, self.pass_fds) as proxy:
            thread = proxy.inspect_thread()
            state = proxy.status_type(thread)
        if state not in ('active', 'idle', 'notLoaded'):
            raise ControlError('apply_reconciliation_thread_unknown', 'Thread activity is not proven.')
        return state

    def inspect_turn(self, turn_id):
        with Proxy(self.config, self.pass_fds) as proxy:
            return proxy.inspect_turn(turn_id)

    def inspect_continuation(self, turn_id):
        with Proxy(self.config, self.pass_fds, continuation=True) as proxy:
            return proxy.inspect_continuation(turn_id)

    def inspect_overload_wait(self, turn_id):
        from .continuation_history import ContinuationHistory
        with Proxy(self.config, self.pass_fds, continuation=True) as proxy:
            return ContinuationHistory(proxy).observe_wait(turn_id)

    def run(self, prompt: str, schema: dict, directory: Path, *, readonly=False, authorize=lambda: True, continuation=None):
        if self.config.transport == "app-server-proxy":
            return self.run_proxy(prompt, schema, directory, readonly=readonly, authorize=authorize, continuation=continuation)
        if continuation is not None:
            raise ControlError('continuation_transport_unproven', 'Only the existing app-server may continue partial work.')
        working = execution_directory(self.config)
        # Prove existence/cwd/activity before exec; no --last, new thread, fork or bypass.
        self.check()
        if not authorize():
            raise ControlError("dispatch_paused", "Pause/stop reached the dispatch boundary first.")
        if execution_directory(self.config) != working:
            raise ControlError('invalid_thread_workspace', 'The thread workspace changed before dispatch.')
        schema_path = directory / "schema.json"
        answer_path = directory / "answer.json"
        write_private(schema_path, (json.dumps(schema) + "\n").encode(), exclusive=True)
        if answer_path.exists() or answer_path.is_symlink():
            raise ControlError("job_output_exists", "A previous job output will not be overwritten.")
        options = exec_policy_options(self.config, readonly=readonly)
        args = [str(self.config.codex_executable), "exec", "resume", "--json", *options]
        args[2:2] = ["--cd", str(working)]
        args.extend(["--output-schema", str(schema_path), "--output-last-message", str(answer_path), self.config.session_id, "-"])
        stdout_path, stderr_path = directory / "events.jsonl", directory / "stderr.log"
        write_private(stdout_path, b"", exclusive=True)
        write_private(stderr_path, b"", exclusive=True)
        try:
            child = subprocess.Popen(args, cwd=working, env=child_environment(self.config),
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     start_new_session=True, pass_fds=self.pass_fds, umask=0o077)
        except OSError:
            raise ControlError("codex_launch_failed", "Codex could not be launched; no automatic retry.") from None
        error = None
        thread_seen = False
        started = completed = 0
        buffer = bytearray()
        discard_line = False
        written = {"out": 0, "err": 0}
        try:
            child.stdin.write(prompt.encode())
            child.stdin.close()
        except OSError:
            error = "codex_connection_lost"
        with stdout_path.open("ab") as out, stderr_path.open("ab") as err, selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ, ("out", out))
            selector.register(child.stderr, selectors.EVENT_READ, ("err", err))
            while selector.get_map():
                for key, _ in selector.select():
                    raw = os.read(key.fileobj.fileno(), 65536)
                    if not raw:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        continue
                    kind, log = key.data
                    keep = max(0, min(len(raw), MAX_LOG - written[kind]))
                    log.write(raw[:keep]); log.flush(); written[kind] += keep
                    if kind != "out":
                        continue
                    buffer.extend(raw)
                    while b"\n" in buffer:
                        line, _, buffer = buffer.partition(b"\n")
                        if discard_line or len(line) > MAX_LINE:
                            error = "codex_protocol_error"; discard_line = False; continue
                        try:
                            event = decode_object(line)
                            kind_event = event.get("type")
                            if kind_event == "thread.started":
                                if thread_seen or event.get("thread_id") != self.config.session_id:
                                    error = "wrong_thread"
                                thread_seen = True
                            elif kind_event == "turn.started":
                                if not thread_seen or started or completed:
                                    error = "codex_protocol_error"
                                started += 1
                            elif kind_event == "turn.completed":
                                if not thread_seen or started != 1 or completed:
                                    error = "codex_protocol_error"
                                completed += 1
                            elif kind_event in ("turn.failed", "error"):
                                error = "codex_turn_failed"
                        except (ValueError, TypeError, UnicodeError, RecursionError):
                            error = "codex_protocol_error"
                    if len(buffer) > MAX_LINE:
                        buffer.clear(); discard_line = True; error = "codex_protocol_error"
        rc = child.wait()  # Deliberately no timeout, terminate or forced interruption of Dev work.
        if buffer.strip() or not thread_seen or started != 1 or completed != 1 or rc != 0:
            error = error or "codex_turn_incomplete"
        if error:
            raise ControlError(error, "Codex did not provide an unambiguous completion; inspect the private job evidence.")
        try:
            answer = decode_object(read_private(answer_path))
        except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
            raise ControlError("codex_receipt_invalid", "No valid structured final response.") from None
        json_write(directory / "protocol-completion.json", {"transport": "exec", "thread_id": self.config.session_id,
                   "completed": True, "answer": answer})
        return answer

    def run_proxy(self, prompt, schema, directory, *, readonly=False, authorize=lambda: True, continuation=None):
        try:
            return run_proxy_turn(self, prompt, schema, directory, readonly=readonly, authorize=authorize, continuation=continuation)
        except ControlError as exc:
            if exc.code not in ("codex_connection_lost", "codex_protocol_error", "codex_proxy_unavailable",
                                "codex_protocol_timeout", "codex_daemon_unavailable"):
                raise
            # A single metadata reconnect can observe live work, never replace it.
            # Silence is not a failure; failed observation is not terminal proof.
            try:
                ref = json_read(directory / "turn.json")
                if not ref or ref.get("thread_id") != self.config.session_id:
                    raise ControlError("codex_turn_unidentified", "No exact turn receipt.")
                live = self.inspect_turn(ref["turn_id"])
                details = {"turn_id": ref["turn_id"], "thread_status": live.get("thread_status"),
                           "turn_status": (live.get("turn") or {}).get("status")}
                decision = "preserve_active" if details["thread_status"] == "active" or details["turn_status"] == "inProgress" else "needs_recovery"
                json_write(directory / "observation.json", {**details, "decision": decision})
                self.observe(**details, decision=decision)
            except (ControlError, KeyError, TypeError):
                details = {"thread_status": "unknown", "turn_status": "unknown"}
                self.observe(**details, decision="needs_recovery")
            raise ControlError(exc.code, str(exc), details=details) from None
