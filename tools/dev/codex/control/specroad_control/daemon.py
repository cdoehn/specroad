"""Responsive lifecycle IPC plus a single event-driven automation task."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import selectors
import signal
import socket
import stat
import time
import uuid
from .automation import Engine, Gate
from .config import Config, load
from .errors import ControlError
from .lifecycle import Lifecycle
from .start_delay import StartDelay
from .local import Paths, json_write, lock, private_dir
from .ipc import receive, request, same_user, scope
from .notifications import Notifications
from .state import read_state
from .status_wire import encoded
from .telemetry import record
from .disk_space import DiskGuard, CHECK_SECONDS, STOP_ERRORS


def run(paths: Paths) -> int:
    private_dir(paths.state)
    private_dir(paths.runtime)
    with lock(paths.state / "worker.lock"):
        from .handover_queue import startup
        config, queued = startup(paths)
        previous_umask = os.umask(0o077)
        try:
            return _locked_run(paths, config, queued=queued)
        finally:
            os.umask(previous_umask)


def _locked_run(paths: Paths, config: Config | None = None, *, queued=None) -> int:
    config = config or load(paths)
    previous = read_state(paths)
    if previous and previous["active_job"] and not config.enabled:
        raise ControlError("unresolved_job", "Unresolved prior work must be reviewed before starting; no replay is attempted.")
    desired = previous.get("desired", "running") if previous else "running"
    if desired not in ("running", "paused"):
        raise ControlError("invalid_state", "Unknown persisted lifecycle mode.")
    if queued:
        from .handover_queue import state_read
        if state_read(paths, queued)['phase'] == 'armed':
            desired = 'running'  # Explicit observation only; no development before handover.
    lifecycle = Lifecycle(desired)
    delay = StartDelay(config.start_delay_seconds if config.enabled else 0.0)
    disk = DiskGuard(config, paths) if config.enabled else None
    gate = Gate(guard=disk)
    gate.set(desired == "running" and delay.ready())
    engine = watcher = None
    future = None
    run_id = str(uuid.uuid4())
    started = time.time()
    runtime_error = None
    stop_reason = None
    pending_scan = config.enabled
    due = time.monotonic()
    disk_due = due

    def snapshot():
        return {"instance": paths.instance,
                "bindings": {"repository": str(config.repository), "apply_repository": str(config.apply_directory),
                             "exchange": str(config.exchange), "repo_id": config.repo_id,
                             "thread_id": config.session_id, "config": str(paths.config), "unit": paths.unit.name},
                "schema": 1, "run_id": run_id, "pid": os.getpid(), "started_at": started,
                "updated_at": time.time(), "phase": lifecycle.phase, "desired": lifecycle.desired,
                "active_job": lifecycle.active_job, "development_enabled": config.enabled,
                "capabilities": ["lifecycle", "development"] if config.enabled else ["lifecycle"],
                "driver": config.transport if config.enabled else "foundation-only",
                "automation": engine.summary() if engine else None, "runtime_error": runtime_error,
                "stop_reason": stop_reason, "disk_space": disk.snapshot() if disk else None,
                "start_delay": delay.snapshot(stopping=lifecycle.stopping),
                **({'handover_request_id': engine.request_id} if hasattr(engine, 'request_id') else {})}

    def save():
        doc = snapshot()
        json_write(paths.state_file, doc)
        print(json.dumps({"event": "lifecycle", "phase": doc["phase"], "run_id": run_id,
                          "automation_stage": doc["automation"].get("stage") if doc["automation"] else None,
                          "error": runtime_error or (doc["automation"].get("error") if doc["automation"] else None),
                          "runtime_error": runtime_error,
                          "stop_reason": stop_reason,
                          "source_sha256": doc["automation"].get("source_sha256") if doc["automation"] else None,
                          "retry_at": doc["automation"].get("retry_at") if doc["automation"] else None,
                          "retry_attempt": doc["automation"].get("retry_attempt") if doc["automation"] else None,
                          **{k: (doc["automation"] or {}).get(k) for k in ("turn_id", "thread_status", "turn_status", "codex_error", "codex_will_retry", "retry_blocked_reason", "retry_mode", "overload_check_at")}}), flush=True)
        return doc

    def storage_stop(exc):
        nonlocal stop_reason
        gate.set(False)  # Close the dispatch boundary before any filesystem writes.
        lifecycle.request('stop')
        if stop_reason is None:
            stop_reason = exc.code
            record('storage_stop', reason=exc.code, **exc.details)
            save()

    def check_storage():
        nonlocal disk_due
        if disk is not None and not lifecycle.stopping:
            try:
                disk.require()
            except ControlError as exc:
                if exc.code not in STOP_ERRORS:
                    raise
                storage_stop(exc)
            disk_due = time.monotonic() + CHECK_SECONDS

    if paths.socket.exists() or paths.socket.is_symlink():
        st = paths.socket.lstat()
        if not stat.S_ISSOCK(st.st_mode) or st.st_uid != os.getuid():
            raise ControlError("unsafe_socket", "Refusing to replace a foreign or non-socket path.")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.5)
            try:
                probe.connect(str(paths.socket))
            except ConnectionRefusedError:
                pass
            else:
                raise ControlError("already_running", "A live socket will not be replaced, even under another state directory.")
        paths.socket.unlink()

    read_fd, write_fd = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
    old_handlers = {}
    socket_identity = None
    old_wakeup = signal.set_wakeup_fd(write_fd)

    def on_stop(_signum, _frame):
        # The handler never acquires a lock held by the task thread.
        lifecycle.request("stop")

    def wake(_future):
        try:
            os.write(write_fd, b"J")
        except (BlockingIOError, OSError):
            pass

    for sig in (signal.SIGTERM, signal.SIGINT):
        old_handlers[sig] = signal.signal(sig, on_stop)
    try:
        if config.enabled:
            if not config.repository.is_dir() or not (config.repository / ".git").exists() or not config.exchange.is_dir():
                raise ControlError("workspace_missing", "Configured Dev Git directory and Exchange must already exist.")
            if queued:
                from .handover_queue import DeferredHandover
                engine = DeferredHandover(config, paths, gate, queued)
            else:
                watcher = Notifications(config.exchange)  # Watch before the first scan: no lost startup event.
                engine = Engine(config, paths, gate)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener, selectors.DefaultSelector() as selector, ThreadPoolExecutor(max_workers=1) as pool:
            listener.bind(str(paths.socket))
            bound = paths.socket.lstat()
            socket_identity = (bound.st_dev, bound.st_ino)
            os.chmod(paths.socket, 0o600)
            listener.listen(16)
            selector.register(listener, selectors.EVENT_READ)
            selector.register(read_fd, selectors.EVENT_READ)
            if watcher:
                selector.register(watcher, selectors.EVENT_READ)
            save()
            while lifecycle.phase != "stopped":
                if disk is not None and time.monotonic() >= disk_due:
                    check_storage()
                    if lifecycle.phase == 'stopped':
                        break
                gate.set(lifecycle.desired == "running" and not lifecycle.stopping and runtime_error is None and delay.ready())
                if future is not None and future.done():
                    try:
                        result = future.result()
                        if result.get('handover_complete'):
                            config = load(paths, allow_deferred=True)
                            if disk is not None:
                                disk.rebind(config)
                            if not result['resume_after']:
                                lifecycle.desired = 'paused'
                            save()  # Durable resume/pause decision before removing startup barrier.
                            from .handover_queue import finish_request
                            finish_request(paths, engine.doc)
                            if not lifecycle.stopping:
                                engine.close()
                                watcher = Notifications(config.exchange)
                                selector.register(watcher, selectors.EVENT_READ)
                                engine = Engine(config, paths, gate)
                                pending_scan, due = True, time.monotonic() + config.settle_seconds
                        if result.get("halted") and not lifecycle.stopping:
                            lifecycle.request("pause")
                        if "retry_after" in result:
                            pending_scan, due = True, time.monotonic() + max(0, result["retry_after"])
                        if result.get("again"):
                            pending_scan, due = True, time.monotonic() + config.settle_seconds
                    except ControlError as exc:
                        if exc.code in STOP_ERRORS:
                            storage_stop(exc)
                        else:
                            runtime_error = exc.code
                            record("automation_error", source_sha256=engine.summary().get("source_sha256"), error=exc.code, decision="blocked")
                            if not lifecycle.stopping:
                                lifecycle.request("pause")
                    except Exception:
                        runtime_error = "automation_internal_error"
                        if not lifecycle.stopping:
                            lifecycle.request("pause")
                    future = None
                    lifecycle.finish_job()
                    save()
                    if lifecycle.phase == "stopped":
                        break
                if engine and pending_scan and future is None and lifecycle.phase == "idle" and runtime_error is None and time.monotonic() >= delay.due(due):
                    check_storage()
                    if lifecycle.stopping:
                        break
                    gate.set(True)
                    lifecycle.begin_job()
                    save()  # Preserve the begun work before handing it to the task.
                    future = pool.submit(engine.tick)
                    future.add_done_callback(wake)
                    pending_scan = False
                timeout = max(0, delay.due(due) - time.monotonic()) if engine and pending_scan and future is None and lifecycle.phase == "idle" and runtime_error is None else None
                if disk is not None and not lifecycle.stopping:
                    remaining = max(0, disk_due - time.monotonic())
                    timeout = remaining if timeout is None else min(timeout, remaining)
                for key, _mask in selector.select(timeout):
                    if key.fileobj == read_fd:
                        os.read(read_fd, 4096)
                        gate.set(lifecycle.desired == "running" and not lifecycle.stopping and runtime_error is None and delay.ready())
                        save()
                        continue
                    if watcher and key.fileobj is watcher:
                        try:
                            if watcher.consume():
                                pending_scan, due = True, time.monotonic() + config.settle_seconds
                        except ControlError as exc:
                            runtime_error = exc.code
                            gate.set(False)
                            if not lifecycle.stopping:
                                lifecycle.request("pause")
                            selector.unregister(watcher)
                            save()
                        continue
                    with listener.accept()[0] as client:
                        client.settimeout(0.5)
                        try:
                            same_user(client)
                            document = receive(client, limit=4096, timeout=0.5)
                            if set(document) != {"command", "scope"} or document["scope"] != scope(paths):
                                raise ControlError("wrong_scope", "The request must address this configured controller.")
                            command = document["command"]
                            if not isinstance(command, str) or command not in ("status", "pause", "resume", "stop"):
                                raise ValueError
                            if command != "status":
                                if command == "resume" and runtime_error:
                                    raise ControlError("needs_review", "A runtime error requires review and a controlled restart.")
                                lifecycle.request(command)
                                gate.set(lifecycle.desired == "running" and not lifecycle.stopping and runtime_error is None and delay.ready())
                                if command == "resume":
                                    pending_scan, due = config.enabled, time.monotonic()
                                save()
                            reply = {"ok": True, "state": snapshot()}
                        except ControlError as exc:
                            reply = {"ok": False, "error": exc.code}
                        except (ValueError, KeyError, TypeError, OSError):
                            reply = {"ok": False, "error": "invalid_request"}
                        try:
                            client.sendall(encoded(reply))
                        except OSError:
                            pass
            gate.set(False)
            save()
    finally:
        gate.set(False)
        if engine:
            engine.close()
        if watcher:
            watcher.close()
        signal.set_wakeup_fd(old_wakeup)
        for sig, old in old_handlers.items():
            signal.signal(sig, old)
        os.close(read_fd)
        os.close(write_fd)
        try:
            current = paths.socket.lstat()
        except FileNotFoundError:
            current = None
        if current and socket_identity == (current.st_dev, current.st_ino) and stat.S_ISSOCK(current.st_mode):
            paths.socket.unlink()
    return 0
