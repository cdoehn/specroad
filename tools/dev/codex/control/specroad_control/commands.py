"""Explicit local setup and diagnostics, never an automatic service/model start."""
from contextlib import contextmanager
from dataclasses import replace
import os
from pathlib import Path
import shutil
import subprocess
import sys
from specroad_control.toml_compat import tomllib
from uuid import uuid4
from .automation import Engine, Gate, scope
from .bootstrap import inspect_history, select_source, require_initial
from .blocked_recovery import recover_blocked
from .config import Config, load, parse, render, identity, setup_config
from .errors import ControlError
from .ledger import Ledger
from .telemetry import record
from .local import Paths, lock, private_dir, json_read, json_write, write_private


def existing_core() -> Path:
    candidates = []
    command = shutil.which("patchharbor")
    if command:
        try:
            first = Path(command).read_text().splitlines()[0]
            if first.startswith("#!/"):
                candidates.append(Path(first[2:]))
        except (OSError, UnicodeError):
            pass
    home = Path.home()
    for root in (os.environ.get("PIPX_HOME"), home / ".local/share/pipx", home / ".local/pipx"):
        if root:
            candidates.append(Path(root) / "venvs/patchharbor/bin/python")
    candidates.append(Path(sys.executable))
    for path in dict.fromkeys(candidates):
        if not path.is_absolute():
            continue
        try:
            tested = subprocess.run([str(path), "-I", "-B", "-c", "from patchharbor.result_reader import capture_result_reference; from patchharbor.api import validate_patch"],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False)
            if tested.returncode == 0:
                return path
        except (OSError, subprocess.TimeoutExpired):
            pass
    raise ControlError("core_unavailable", "Specify --core-python pointing to the existing PatchHarbor installation; nothing was installed.")


def ready(config: Config):
    if not config.enabled:
        raise ControlError("automation_not_configured", "Configure the explicit Dev thread and product Result first.")
    if not config.repository.is_dir() or not (config.repository / ".git").exists() or not config.exchange.is_dir():
        raise ControlError("workspace_missing", "Dev Git directory and Exchange must already exist.")


@contextmanager
def offline(paths: Paths):
    private_dir(paths.state)
    with lock(paths.state / "operation.lock"), lock(paths.state / "worker.lock"):
        yield


def configure(paths: Paths, *, thread_id: str, result: str | None = None, codex: str | None = None,
              core_python: str | None = None, transport: str | None = None,
              access_mode: str | None = None) -> dict:
    with offline(paths):
        old, legacy = setup_config(paths)
        if access_mode is not None and access_mode not in ('workspace-write', 'full-access'):
            raise ControlError('invalid_access_mode', 'Select workspace-write or full-access explicitly.')
        try:
            identity(thread_id)
        except (ValueError, TypeError):
            raise ControlError("invalid_thread_id", "An explicit canonical thread UUID is required.") from None
        codex_path = Path(codex or old.codex_executable or shutil.which("codex") or "")
        if not codex_path.is_absolute() or not os.access(codex_path, os.X_OK):
            raise ControlError("codex_unavailable", "Supply --codex as the absolute installed Codex executable path.")
        python_path = Path(core_python) if core_python else old.core_python or existing_core()
        home = old.codex_home or Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        candidate = replace(old, session_id=thread_id, codex_executable=codex_path,
                            core_python=python_path, codex_home=home, transport=transport or old.transport,
                            access_mode=old.access_mode if access_mode is None else access_mode,
                            command_path=old.command_path or os.environ.get("PATH", ""))
        history_path = paths.state / "automation.sqlite3"
        exists, empty_history = inspect_history(candidate, history_path, legacy)
        source = select_source(candidate, result, legacy, needs_initial=not exists or empty_history)
        if source is not None:
            candidate = replace(candidate, repo_id=source["binding"]["repo_id"])
        elif not candidate.repo_id:
            raise ControlError("state_not_initialized", "Supply --result once to initialize the runtime state.")
        candidate = replace(candidate, enabled=True)
        try:
            candidate = parse(tomllib.loads(render(candidate)), paths)
        except (ValueError, TypeError, KeyError):
            raise ControlError("invalid_config", "Setup settings are invalid; existing configuration is preserved.") from None
        ready(candidate)
        empty_history = require_initial(candidate, history_path, source, exists=exists)
        with Engine(candidate, paths, Gate()) as engine:
            evidence = engine.codex.check()
            if source is not None:
                source = engine.exchange.source(source)  # Recheck the bytes after preflight.
            history = Ledger(history_path, scope(candidate), initial=source)
            history.close()
            # Runtime state is durable BEFORE configuration becomes enabled.
            # Repeating setup after an interrupted config write is idempotent.
            write_private(paths.config, render(candidate).encode())
        return {"configured": True, "service_started": False, "config": str(paths.config),
                "access_mode": candidate.access_mode,
                "runtime_state": str(history_path), "bootstrap_created": not exists or empty_history,
                "legacy_seed_migrated": legacy is not None, **evidence}


@contextmanager
def configured_offline(paths: Paths, *, allow_apply_reconciliation=False):
    # Read only after the same locks used by handover: never retain stale binding.
    with offline(paths):
        config = load(paths)
        ready(config)
        if not allow_apply_reconciliation and (paths.state / 'automation.sqlite3').exists():
            from .apply_reconcile_history import require_no_pending
            history = Ledger(paths.state / 'automation.sqlite3', scope(config))
            try:
                require_no_pending(history)
            finally:
                history.close()
        with Engine(config, paths, Gate()) as engine:
            yield config, engine


def check(paths: Paths) -> dict:
    with configured_offline(paths) as (_config, engine):
        engine.source_for_check()
        return {"core_validated": True, "model_called": False, **engine.codex.check()}


def probe(paths: Paths) -> dict:
    with configured_offline(paths) as (_config, engine):
        marker = "SPECROAD-CONTROL-PROBE-" + str(uuid4())
        directory = paths.state / "probes" / marker
        private_dir(directory)
        schema = {"type": "object", "additionalProperties": False,
                  "properties": {"marker": {"type": "string"}}, "required": ["marker"]}
        prompt = ("Nur ein kurzer Sichtbarkeitstest in diesem vorhandenen Thread. Keine Tools, "
                  "keine Dateien lesen/aendern, kein Patch, keine Tests, keine Schleife. "
                  "Antworte ausschliesslich im verlangten JSON mit marker=" + marker)
        result = engine.codex.run(prompt, schema, directory, readonly=True)
        if result != {"marker": marker}:
            raise ControlError("probe_failed", "The same-thread probe did not return its exact marker.")
        evidence = {"same_thread_protocol": True, "model_called": True, "marker": marker,
                    "remote_visibility": "not_verified", "service_started": False}
        json_write(directory / "probe.json", evidence)
        return evidence


def recover(paths: Paths) -> dict:
    """Offline, evidence-only recovery; NEVER dispatch a replacement model call."""
    with configured_offline(paths) as (config, engine):
        if not (paths.state / "automation.sqlite3").exists():
            return {"recovered": False, "reason": "no_history", "model_called": False}
        ledger = Ledger(paths.state / "automation.sqlite3", scope(config))
        try:
            row = ledger.current()
            if row is None or row["stage"] not in ("running", "uncertain"):
                return {"recovered": False, "reason": "no_uncertain_job", "model_called": False}
            source = engine.exchange.source(row["source"])
            engine.excluded = ledger.published_hashes() | {source.get("patch_sha256")}
            retry = ledger.retry_info(source["sha256"])
            directory = ledger.attempt_directory(paths, source["sha256"], retry["number"] if retry else 0)
            protocol = json_read(directory / "protocol-completion.json")
            modern = (config.transport == 'app-server-proxy' and row['error'] == 'codex_turn_failed'
                      and protocol is None and json_read(directory / 'dispatch.json') is not None
                      and json_read(directory / 'attempt.json') is not None)
            checkpoint = None
            if modern:
                from . import continuation
                try:
                    proved = continuation.proof(config, engine.codex, directory, source)
                    checkpoint = {key: proved[key] for key in ('workspace_sha256', 'history_sha256')}
                except ControlError as exc:
                    raise ControlError('recovery_unproven', 'Continuation proof rejected: ' + exc.code) from None
            else:
                engine.codex.check()  # Unknown activity remains blocked outside the strict modern proof.
            if protocol is not None:
                if protocol.get("completed") is not True or protocol.get("thread_id") != config.session_id or protocol.get("transport") not in ("exec", "app-server-proxy"):
                    raise ControlError("recovery_evidence_invalid", "Completion evidence does not match the configured thread.")
                if row["stage"] == "uncertain" and row["error"] == "dev_blocked":
                    recover_blocked(engine, ledger, source, protocol, directory / "protocol-completion.json")
                else:
                    engine.accept(ledger, source, protocol.get("answer"))
            else:
                # A real hash-bound output is sufficient to wait for Apply, not to
                # claim the interrupted Codex turn was successful or retry it.
                patches = engine.eligible_patches(source)
                if len(patches) > 1:
                    raise ControlError("recovery_unproven", "Several bound outputs need review; no replay.")
                if patches:
                    if modern:
                        engine.adopt_failed_output(ledger, source, directory, checkpoint=checkpoint)
                    else:
                        ledger.change("waiting_result", patch_sha=patches[0]["sha256"])
                elif config.transport == "app-server-proxy" and row["error"] == "codex_turn_failed":
                    try:
                        pending = engine.schedule_retry(ledger, source, directory, legacy=not modern, checkpoint=checkpoint)
                    except ControlError as exc:
                        if (modern and exc.code == 'retry_patch_present'
                                and engine.adopt_failed_output(ledger, source, directory, checkpoint=checkpoint)):
                            return {'recovered': True, 'stage': 'waiting_result',
                                    'model_called': False, 'service_started': False}
                        record("retry_decision", source_sha256=source["sha256"], decision="blocked", reason=exc.code)
                        raise ControlError("recovery_unproven", "Retry proof rejected: " + exc.code + "; existing work is preserved.") from None
                    return {"recovered": True, "stage": "retry_wait", "retry_at": pending["due"],
                            "retry_attempt": pending["number"], "model_called": False, "service_started": False}
                else:
                    raise ControlError("recovery_unproven", "No unique bound output/completion; prior work remains unresolved.")
            row = ledger.current()
            return {"recovered": row["stage"] in ("waiting_result", "no_work"),
                    "stage": row["stage"], "model_called": False, "service_started": False}
        finally:
            ledger.close()
