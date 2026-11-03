"""One explicit existing-thread turn over the shared local app-server."""
import json
from .codex_proxy import Proxy, MAX_LOG
from .errors import ControlError
from .execution_scope import execution_directory
from .turn_errors import failure_details, error_code
from .local import decode_object, write_private, json_write
from .continuation import terminal, sha, policy


def run_proxy_turn(self, prompt, schema, directory, *, readonly=False, authorize=lambda: True, continuation=None):
    """Explicit alternative using the user's existing, shared local app-server."""
    working = execution_directory(self.config)
    with Proxy(self.config, self.pass_fds, **({'continuation': True} if continuation else {})) as proxy:
        def preflight():
            if continuation:
                if readonly:
                    raise ControlError('continuation_dispatch_unproven', 'A continuation is a productive turn.')
                terminal(proxy.inspect_continuation(continuation['turn_id']), continuation['turn_id'],
                         history=continuation['history_sha256'])
            else:
                proxy.thread()
        preflight()
        resumed = proxy.call("thread/resume", {"threadId": self.config.session_id, "excludeTurns": True})
        if resumed.get("thread", {}).get("id") != self.config.session_id:
            raise ControlError("wrong_thread", "Resume did not return the explicit existing thread.")
        preflight()  # No model call; recheck status after attachment.
        if not authorize():
            raise ControlError("dispatch_paused", "Pause/stop reached the dispatch boundary first.")
        if execution_directory(self.config) != working:
            raise ControlError('invalid_thread_workspace', 'The thread workspace changed before dispatch.')
        write_private(directory / "schema.json", (json.dumps(schema) + "\n").encode(), exclusive=True)
        events = directory / "events.jsonl"
        write_private(events, b"", exclusive=True)
        turn_policy = {'approvalPolicy': 'never', 'sandboxPolicy': {'type': 'readOnly'}} if readonly else policy(self.config)
        params = {"threadId": self.config.session_id, "cwd": str(working),
                  "input": [{"type": "text", "text": prompt}], **turn_policy, "outputSchema": schema}
        started = proxy.call("turn/start", params)
        turn = started.get("turn", {})
        turn_id = turn.get("id")
        if not isinstance(turn_id, str) or not turn_id:
            raise ControlError("codex_turn_unidentified", "The begun turn cannot be identified; do not repeat it.")
        json_write(directory / "turn.json", {"thread_id": self.config.session_id, "turn_id": turn_id})
        if not readonly:
            json_write(directory / 'dispatch.json', {'thread_id': self.config.session_id,
                       'turn_id': turn_id, 'prompt_sha256': sha(prompt), 'cwd': params['cwd'], **turn_policy})
        last_answer = None
        failure_event = None
        observe = getattr(self, "observe", lambda **_fields: None)
        observe(turn_id=turn_id, turn_status="inProgress", decision="wait_for_terminal")
        written = 0
        with events.open("ab") as stream:
            while True:
                event = proxy.pending.popleft() if proxy.pending else proxy.read(timeout=None)
                raw = (json.dumps(event) + "\n").encode()
                keep = max(0, min(len(raw), MAX_LOG - written))
                stream.write(raw[:keep]); stream.flush(); written += keep
                if "id" in event and "method" in event:
                    proxy.deny(event)
                    continue
                method, data = event.get("method"), event.get("params", {})
                if not isinstance(data, dict) or data.get("threadId") != self.config.session_id:
                    continue
                if method == "thread/status/changed":
                    status = data.get("status", {})
                    if isinstance(status, dict):
                        observe(thread_status=status.get("type"), turn_id=turn_id)
                if method == "error" and data.get("turnId") == turn_id:
                    failure_event = data
                    observe(turn_id=turn_id, turn_status="inProgress", codex_error=error_code(data.get("error")),
                            codex_will_retry=data.get("willRetry"), decision="wait_for_terminal")
                if method == "item/completed" and data.get("turnId") == turn_id:
                    item = data.get("item", {})
                    if isinstance(item, dict) and item.get("type") == "agentMessage":
                        last_answer = item.get("text")
                if method == "turn/completed" and isinstance(data.get("turn"), dict) and data["turn"].get("id") == turn_id:
                    details = failure_details(data["turn"], failure_event)
                    observe(turn_id=turn_id, **details, decision="terminal_received")
                    if data["turn"].get("status") != "completed" or data["turn"].get("error"):
                        json_write(directory / "failure.json", {"thread_id": self.config.session_id,
                                   "turn_id": turn_id, **details})
                        raise ControlError("codex_turn_failed", "The existing app-server reported an unsuccessful turn.", details=details)
                    break
        try:
            if not isinstance(last_answer, str) or len(last_answer.encode()) > 65536:
                raise ValueError
            answer = decode_object(last_answer)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise ControlError("codex_receipt_invalid", "No final structured answer in the completed turn.") from None
        write_private(directory / "answer.json", (json.dumps(answer) + "\n").encode(), exclusive=True)
        json_write(directory / "protocol-completion.json", {"transport": "app-server-proxy", "thread_id": self.config.session_id,
                   "turn_id": turn_id, "completed": True, "answer": answer})
        return answer
