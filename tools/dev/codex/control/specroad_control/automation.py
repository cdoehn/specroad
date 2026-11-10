"""One model call per hash-bound source, then wait for the existing Apply daemon."""
from contextlib import ExitStack
import hashlib
from pathlib import Path
import threading
import time
from .retry_proof import proof
from . import continuation
from .overload_runtime import OverloadWaiting
from .workspace import fingerprint
from .telemetry import record
from .codex import Codex
from .config import Config
from .core import Core
from .errors import ControlError
from .exchange import Exchange
from .ledger import Ledger
from .local import Paths, lock, private_dir, json_write, json_read

from .job_contract import SCHEMA, scope, prompt_for, contract, schema_for, new_contract
from .mixed_contract import MIXED, supports_v4
from .mixed_evidence import verify_handoff, verify_followup


class Gate:
    def __init__(self, guard=None):
        self.mutex = threading.Lock()
        self.allowed = True
        self.guard = guard

    def set(self, allowed):
        with self.mutex:
            self.allowed = allowed

    def enter(self, commit):
        with self.mutex:
            if not self.allowed:
                return False
            if self.guard is not None:
                self.guard.require()
            commit()
            return True


class Engine(OverloadWaiting):
    def __init__(self, config: Config, paths: Paths, gate: Gate, *, core=None, codex=None, clock=time.time):
        self.config, self.paths, self.gate = config, paths, gate
        self.clock = clock
        self.core = core or Core(config)
        self.excluded = set()
        self.stack = ExitStack()
        self.summary_lock = threading.Lock()
        self.view = {"stage": "initializing", "error": None, "remote_visibility": "not_verified"}
        # Keep legacy locks as well as the shared user-wide ownership namespace.
        keys = ["repo-" + hashlib.sha256(str(config.repository.resolve()).encode()).hexdigest(),
                "thread-" + hashlib.sha256((str(config.codex_home.resolve()) + config.session_id).encode()).hexdigest(),
                "apply-" + hashlib.sha256(config.repo_id.encode()).hexdigest(),
                "apply-path-" + hashlib.sha256(str(config.apply_directory.resolve()).encode()).hexdigest(),
                "thread-id-" + hashlib.sha256(config.session_id.encode()).hexdigest()]
        targets = sorted({root / (key + ".lock") for root in paths.lock_roots for key in keys})
        try:
            descriptors = [self.stack.enter_context(lock(target)) for target in targets]
            self.codex = codex or Codex(config, [fd for fd in descriptors if fd is not None])
            self.codex.observe = self.observe
            self.exchange = Exchange(config, self.core, observe=self.update)
        except BaseException:
            self.stack.close()
            raise

    def summary(self):
        with self.summary_lock:
            return dict(self.view)

    def update(self, **values):
        with self.summary_lock:
            self.view.update(values)

    def observe(self, **values):
        record("codex_turn", source_sha256=self.summary().get("source_sha256"), **values)
        self.update(**{k: v for k, v in values.items() if k in ("turn_id", "turn_status", "thread_status", "codex_error", "codex_will_retry")})

    def tick(self):
        ledger = Ledger(self.paths.state / "automation.sqlite3", scope(self.config))
        try:
            from .current_acceptance_history import validate_history as current_history
            from .current_acceptance import tick as current_tick
            acceptance = current_history(ledger)
            if acceptance is not None:
                return current_tick(self, ledger, acceptance)
            from .apply_reconcile import validate_history, verify_completed, tick as reconcile_tick
            from .clarification_authorization_history import validate_history as authorization_history
            from .clarification_authorization import tick as authorization_tick, verify_completed as verify_authorized
            from .blocked_authorization_history import validate_history as blocked_history
            from .blocked_authorization import tick as blocked_tick
            blocked_grant = blocked_history(ledger)
            if blocked_grant is not None:
                return blocked_tick(self, ledger, blocked_grant)
            authorization = authorization_history(ledger)
            if authorization is not None:
                return authorization_tick(self, ledger, authorization)
            from .current_acceptance_history import active as accepted
            if accepted(ledger, ledger.current()['sha']) is None:
                verify_authorized(self, ledger)
            reconciliation = validate_history(ledger)
            if reconciliation is not None:
                return reconcile_tick(self, ledger, reconciliation)
            if accepted(ledger, ledger.current()['sha']) is None:
                verify_completed(self, ledger)
            row = ledger.current()
            self.update(stage=row["stage"], source_sha256=row["sha"], error=row["error"])
            if row["stage"] in ("running", "uncertain"):
                self.update(stage="uncertain", error=row["error"] or "unresolved_job")
                return {"halted": True, "again": False}
            if row["stage"] == "no_work":
                return {"halted": True, "again": False}
            source = self.exchange.source(row["source"])
            if row["stage"] == "waiting_result":
                next_results = self.exchange.following(source, row["patch_sha"])
                from .handoff_rebase import followups, candidate, wait_if_busy
                selected = ledger.request_contract()
                busy_runs = set()
                if selected and selected['version'] == 4:
                    next_results, busy_runs = followups(self, source, row['patch_sha'], next_results)
                recovered = ledger.blocked_recovery()
                if recovered is not None and (len(next_results) != 1 or next_results[0]["sha256"] != recovered["sha256"]):
                    raise ControlError("recovery_evidence_changed", "The exact recovered Apply result is missing or changed.")
                if len(next_results) > 1:
                    raise ControlError("ambiguous_result", "Several Apply runs match the pending patch; no latest-file guess.")
                if not next_results:
                    return {"halted": False, "again": False}
                # Validate the immutable dispatch again before carrying authority
                # into a new source. A coherent but changed counter is not proof.
                selected = ledger.request_contract()
                if (selected and selected['version'] in (2, 3, 4)
                        and ledger.output_kind() in ('patch_ready', 'spec_clarification', MIXED)):
                    retry = ledger.retry_info(source['sha256'])
                    directory = ledger.attempt_directory(self.paths, source['sha256'], retry['number'] if retry else 0)
                    attempt = json_read(directory/'attempt.json')
                    if not attempt or contract(attempt.get('request_contract')) != selected:
                        raise ControlError('request_contract_changed', 'Follow-up authority differs from the original attempt.')
                    continuation.request_prompt(attempt, source)
                evidence = (verify_followup(self, source, row['patch_sha'], next_results[0], ledger.output_kind())
                            if selected and selected['version'] == 4 else None)
                if selected and selected['version'] == 4 and candidate(next_results[0]):
                    waiting = wait_if_busy(self, next_results[0], ledger.known_runs() | busy_runs)
                    if waiting:
                        return waiting
                ledger.enqueue(next_results[0], decision_evidence=evidence)
                source = next_results[0]
                row = ledger.current()
                self.update(stage=row["stage"], source_sha256=row["sha"], error=row["error"])
            self.excluded = ledger.published_hashes() | {source.get("patch_sha256")}
            if row['stage'] == 'overload_wait':
                return self.observe_wait(ledger, source)
            # Already attempted patches are NOT adopted again after a failed Apply
            # that kept the same fingerprint. They need a new correction instead.
            patches = self.eligible_patches(source)
            if len(patches) > 1:
                raise ControlError("ambiguous_patch", "Several patches share this source binding.")
            if patches:
                retry = ledger.retry_info(source['sha256'])
                if row['stage'] == 'retry_wait' and retry and retry['evidence'].get('mode') == 'continuation':
                    try:
                        self.confirm_terminal(retry['evidence'])
                    except ControlError as exc:
                        if exc.code in ('dev_turn_active', 'continuation_background_active'):
                            return {'halted': False, 'again': False, 'retry_after': 30}
                        raise
                ledger.change("waiting_result", patch_sha=patches[0]["sha256"])
                self.update(stage="waiting_result", error=None)
                return {"halted": False, "again": True}
            retry = ledger.retry_info(source["sha256"])
            number = retry["number"] if retry else 0
            if row["stage"] == "retry_wait":
                if retry is None:
                    raise ControlError("invalid_retry_history", "Scheduled retry has no durable proof.")
                self.update(retry_attempt=number, retry_at=retry["due"], retry_mode=retry['evidence'].get('mode', 'readonly'))
                wait = retry["due"] - self.clock()
                if wait > 0:
                    return {"halted": False, "again": False, "retry_after": wait}
                try:
                    self.check_retry(source, retry, ledger=ledger)
                except ControlError as exc:
                    if exc.code in ('dev_turn_active', 'continuation_background_active'):
                        self.update(thread_status="active")
                        record("retry_decision", source_sha256=source["sha256"], decision="wait", reason=exc.code,
                               retry_attempt=number, wait_seconds=30)
                        return {"halted": False, "again": False, "retry_after": 30}
                    ledger.change("uncertain", error=exc.code)
                    self.update(stage="uncertain", error=exc.code)
                    record("retry_decision", source_sha256=source["sha256"], decision="blocked", reason=exc.code)
                    return {"halted": True, "again": False}
            from .blocked_authorization_history import active as active_blocked
            from .current_acceptance_history import active as accepted
            if (accepted(ledger, source['sha256']) or active_blocked(ledger, source['sha256'])) and self.codex.activity() == 'active':
                self.update(stage=row['stage'], thread_status='active')
                return {'halted': False, 'again': False, 'retry_after': 2}
            if not self.gate.allowed:
                self.update(stage=row["stage"], error=None)
                return {"halted": False, "again": False}
            self.exchange.assert_current(source, ledger.known_runs())
            from .handoff_rebase import candidate, wait_if_busy
            if (ledger.request_contract() or {}).get('version') == 4 and candidate(source):
                waiting = wait_if_busy(self, source, ledger.known_runs())
                if waiting:
                    return waiting
            job_dir = ledger.attempt_directory(self.paths, source["sha256"], number)
            private_dir(job_dir)
            attempt = {"source_sha256": source["sha256"], "thread_id": self.config.session_id, "number": number}
            from .blocked_authorization_history import active as blocked_authority
            grant = accepted(ledger, source['sha256']) or blocked_authority(ledger, source['sha256'])
            fresh_grant = grant is not None and number == grant['attempt_number']
            continuing = retry['evidence'] if retry and not fresh_grant and retry['evidence'].get('mode') == 'continuation' else None
            if continuing:
                attempt['continuation'] = continuing
            previous = json_read(job_dir / "attempt.json")
            # New sources opt into v3; existing and retried attempts retain their
            # original version, including legacy absence of version metadata.
            origin = previous
            if origin is None and number and not fresh_grant:
                origin = json_read(ledger.attempt_origin(self.paths, source['sha256']) / 'attempt.json')
                if origin is None:
                    origin = {}  # Legacy read-only recovery must stay legacy.
            selected = (contract(origin.get('request_contract')) if origin is not None else
                        ledger.request_contract() or (new_contract(version=4) if supports_v4(source) and source['success'] and not source['dirty'] else new_contract()))
            ledger.bind_contract(selected)
            if previous is not None and any(previous.get(k) != v for k, v in attempt.items()):
                raise ControlError("retry_evidence_invalid", "An attempt directory belongs to different work.")
            if previous is not None and previous.get('continuation') != continuing:
                raise ControlError('retry_evidence_invalid', 'The attempt continuation binding changed.')
            if previous is None:
                attempt['request_contract'] = selected
                attempt['request_source'] = {key: source[key] for key in ('path', 'sha256', 'binding', 'run_id')}
                try:
                    attempt["workspace_sha256"] = fingerprint(self.config.repository)
                except ControlError as exc:
                    # Normal work may proceed; an unguarded failure can NEVER be retried.
                    attempt["workspace_sha256"] = None
                    record("retry_guard", source_sha256=source["sha256"], decision="retry_unavailable", reason=exc.code)
                json_write(job_dir / "attempt.json", attempt)
            else:
                attempt = previous
            self.update(stage="checking_dispatch", error=None, retry_attempt=number, retry_at=None,
                        retry_blocked_reason=None, codex_error=None, codex_will_retry=None, turn_status=None,
                        turn_id=None, thread_status=None)
            try:
                request_prompt = continuation.request_prompt(attempt, source) if 'request_source' in attempt or continuing else prompt_for(source)
                answer = self.codex.run(request_prompt,
                                        schema_for(selected), job_dir,
                                        authorize=lambda: self.authorize_request(ledger, source, job_dir, attempt, selected),
                                        **({'continuation': continuing} if continuing else {}))
                json_write(job_dir / "completion.json", answer)
                self.accept(ledger, source, answer)
            except ControlError as exc:
                from .handoff_rebase import candidate
                if (exc.code == 'repository_busy' and candidate(source)
                        and (ledger.request_contract() or {}).get('version') == 4
                        and ledger.current()['stage'] == 'ready'):
                    self.update(apply_wait_reason='repository_busy', stage='ready', error=None)
                    return {'halted': False, 'again': False, 'retry_after': 30}
                from .disk_space import STOP_ERRORS
                if exc.code in STOP_ERRORS:
                    raise  # No dispatch occurred; preserve the claim for an explicit later start.
                if exc.code == "dispatch_paused":
                    self.update(stage=ledger.current()["stage"], error=None)
                    return {"halted": False, "again": ledger.current()['stage'] == 'waiting_result'}
                if (exc.code == 'dev_thread_busy' and exc.details.get('thread_status') == 'active'
                        and ledger.current()['stage'] in ('ready', 'retry_wait')):
                    # No durable dispatch claim exists. Preserve the attempt and
                    # wait for the user's turn instead of pausing or steering it.
                    self.update(stage=ledger.current()['stage'], thread_status='active', error=None)
                    return {'halted': False, 'again': False, 'retry_after': 30}
                if ledger.current()['stage'] == 'retry_wait' and exc.code in ('dev_turn_active', 'continuation_background_active'):
                    self.update(stage='retry_wait', error=None)
                    return {'halted': False, 'again': False, 'retry_after': 30}
                self.observe(**{k: v for k, v in exc.details.items() if k in ("turn_id", "thread_status", "turn_status", "codex_error", "codex_will_retry")})
                record("automation_error", source_sha256=source["sha256"], error=exc.code,
                       retry_attempt=number, **exc.details)
                if exc.code == "codex_turn_failed" and self.config.transport == "app-server-proxy":
                    try:
                        if self.adopt_failed_output(ledger, source, job_dir):
                            return {'halted': False, 'again': True}
                        pending = self.schedule_retry(ledger, source, job_dir)
                        return {"halted": False, "again": False, "retry_after": max(0, pending["due"]-self.clock())}
                    except ControlError as rejected:
                        if rejected.code in ('continuation_background_active', 'continuation_actions_unproven'):
                            try:
                                return self.begin_wait(ledger, source, job_dir, number)
                            except ControlError as wait_error:
                                rejected = wait_error
                        self.update(retry_blocked_reason=rejected.code)
                        record("retry_decision", source_sha256=source["sha256"], decision="blocked", reason=rejected.code,
                               retry_attempt=number, **exc.details)
                # No terminal proof / unknown tools / ambiguous result: preserve work.
                stage = "ready" if ledger.current()["stage"] == "ready" else "uncertain"
                ledger.change(stage, error=exc.code)
                self.update(stage=stage, error=exc.code)
                return {"halted": True, "again": False}
            row = ledger.current()
            self.update(stage=row["stage"], source_sha256=source["sha256"], error=row["error"])
            return {"halted": row["stage"] in ("no_work", "uncertain"), "again": row["stage"] == "waiting_result"}
        finally:
            ledger.close()

    def schedule_retry(self, ledger, source, directory, *, legacy=False, checkpoint=None):
        if checkpoint is not None:
            failure = continuation.proof(self.config, self.codex, directory, source)
            if any(failure[key] != value for key, value in checkpoint.items()):
                raise ControlError('overload_checkpoint_changed', 'Completion changed before retry scheduling.')
        else:
            try:
                failure = proof(self.config, self.codex, directory, source, legacy=legacy)
            except ControlError as exc:
                attempt = json_read(directory / 'attempt.json') or {}
                eligible = exc.code in ('retry_effects_unproven', 'retry_status_unknown', 'retry_workspace_changed')
                if attempt.get('continuation') and exc.code == 'retry_source_unproven':
                    eligible = True
                if legacy or not eligible:
                    raise
                failure = continuation.proof(self.config, self.codex, directory, source)
        if failure.get('mode') == 'continuation':
            previous = ledger.retry_info(source['sha256'])
            attempt = json_read(directory / 'attempt.json')
            if not attempt or attempt.get('number') != (previous['number'] if previous else 0):
                raise ControlError('continuation_dispatch_unproven', 'Continuation attempt does not match its durable budget.')
        self.exchange.source(source)
        self.exchange.assert_current(source, ledger.known_runs())
        if self.eligible_patches(source):
            raise ControlError("retry_patch_present", "Bound output exists; recover the output instead of replaying.")
        if checkpoint and fingerprint(self.config.repository) != checkpoint['workspace_sha256']:
            raise ControlError('overload_checkpoint_changed', 'Workspace changed during the final source checks.')
        pending = ledger.schedule_retry(failure, self.config.retry_delays_seconds, self.clock())
        self.update(stage="retry_wait", error="serverOverloaded", source_sha256=source["sha256"],
                    retry_mode=failure.get('mode', 'readonly'),
                    retry_attempt=pending["number"], retry_at=pending["due"],
                    turn_status="failed", turn_id=failure["turn_id"], codex_error="serverOverloaded", codex_will_retry=False)
        record("retry_decision", source_sha256=source["sha256"], turn_id=failure["turn_id"],
               codex_error="serverOverloaded", codex_will_retry=False, turn_status="failed", decision="scheduled",
               retry_mode=failure.get('mode', 'readonly'),
               retry_attempt=pending["number"], retry_at=pending["due"], wait_seconds=pending["due"]-self.clock())
        return pending

    def check_retry(self, source, retry, *, ledger=None):
        if ledger is None:
            opened = Ledger(self.paths.state / "automation.sqlite3", scope(self.config))
            try:
                return self.check_retry(source, retry, ledger=opened)
            finally:
                opened.close()
        evidence = retry['evidence']
        directory = ledger.attempt_directory(self.paths, source['sha256'], retry['number'] - 1)
        if evidence.get('mode') == 'continuation':
            attempt = json_read(directory / 'attempt.json')
            if not attempt or attempt.get('number') != retry['number'] - 1:
                raise ControlError('continuation_dispatch_unproven', 'The failed attempt number is not bound.')
            return continuation.proof(self.config, self.codex, directory, source, saved=evidence)
        return proof(self.config, self.codex, directory, source,
                     legacy=evidence['legacy'], guard=evidence['workspace_sha256'])

    def confirm_terminal(self, evidence):
        if not callable(getattr(self.codex, 'inspect_continuation', None)):
            raise ControlError('continuation_inactive_unproven', 'Complete inactivity observation is unavailable.')
        return continuation.terminal(self.codex.inspect_continuation(evidence['turn_id']), evidence['turn_id'],
                                     history=evidence.get('history_sha256'))

    def adopt_failed_output(self, ledger, source, directory, *, checkpoint=None):
        patches = self.eligible_patches(source)
        if len(patches) > 1:
            raise ControlError('ambiguous_patch', 'Several bundles match the failed source.')
        if not patches:
            return False
        from .retry_proof import load_failure
        evidence = load_failure(directory, self.config, source)
        if checkpoint:
            evidence['history_sha256'] = checkpoint['history_sha256']
        self.confirm_terminal(evidence)
        if checkpoint and fingerprint(self.config.repository) != checkpoint['workspace_sha256']:
            raise ControlError('overload_checkpoint_changed', 'Preserved work changed before output adoption.')
        self.exchange.source(source)
        ledger.change('waiting_result', patch_sha=patches[0]['sha256'])
        self.update(stage='waiting_result', error=None, retry_at=None)
        record('retry_decision', source_sha256=source['sha256'], decision='adopt_output')
        return True

    def source_for_check(self):
        ledger = Ledger(self.paths.state / "automation.sqlite3", scope(self.config))
        try:
            return self.exchange.source(ledger.current()["source"])
        finally:
            ledger.close()

    def eligible_patches(self, source):
        return [patch for patch in self.exchange.patches(source) if patch["sha256"] not in self.excluded]

    def authorize(self, ledger, source, *, request_guard=None, thread_preflight=None):
        # The IPC thread can pause while native checks run. Acquire Gate only at
        # the final durable dispatch boundary, without long network work inside.
        self.exchange.source(source)
        if ledger.current()["stage"] == "retry_wait":
            retry = ledger.retry_info(source["sha256"])
            if self.clock() < retry["due"]:
                return False
            patches = self.eligible_patches(source)
            if len(patches) > 1:
                raise ControlError('ambiguous_patch', 'Several bound outputs appeared at dispatch.')
            if patches:
                if retry['evidence'].get('mode') == 'continuation':
                    self.confirm_terminal(retry['evidence'])
                else:
                    self.check_retry(source, retry, ledger=ledger)
                ledger.change('waiting_result', patch_sha=patches[0]['sha256'])
                self.update(stage='waiting_result', error=None, retry_at=None)
                record('retry_decision', source_sha256=source['sha256'], decision='adopt_output')
                return False
            self.check_retry(source, retry, ledger=ledger)
        self.exchange.assert_current(source, ledger.known_runs())
        from .handoff_rebase import candidate, require_current
        if (ledger.request_contract() or {}).get('version') == 4 and candidate(source):
            require_current(self, source, ledger.known_runs())
        from .blocked_authorization import guard_dispatch
        guard_dispatch(self, ledger, source)
        from .current_acceptance import guard_dispatch as guard_current
        guard_current(self, ledger, source)
        if thread_preflight is not None:
            thread_preflight()
        def claim():
            if request_guard is not None:
                request_guard()
            ledger.change('running')
        allowed = self.gate.enter(claim)
        if allowed:
            self.update(stage="running", source_sha256=source["sha256"], error=None)
        return allowed

    def authorize_request(self, ledger, source, directory, attempt, selected):
        # authorize() performs the full Apply proofs once, before Gate.enter.
        # They can take minutes: the earlier transport preflight is not a fresh
        # activity observation at the durable claim boundary.
        def guard():
            from .blocked_authorization import guard_original
            guard_original(self, ledger, source)
            from .current_acceptance import guard_original as guard_accepted
            guard_accepted(self, ledger, source)
            if ledger.request_contract() != selected or json_read(directory/'attempt.json') != attempt:
                raise ControlError('request_contract_changed', 'Request authority changed during thread preflight.')
        guard()
        return self.authorize(ledger, source, request_guard=guard,
                              thread_preflight=None if attempt.get('continuation') else self.codex.check)

    def accept(self, ledger, source, answer):
        if not isinstance(answer, dict) or set(answer) != set(SCHEMA["required"]) or not all(isinstance(v, str) for v in answer.values()) or answer["source_result_sha256"] != source["sha256"]:
            raise ControlError("codex_receipt_invalid", "Structured response does not match its exact source.")
        selected = ledger.request_contract()
        if selected is not None and selected['version'] in (2, 3, 4):
            retry = ledger.retry_info(source['sha256'])
            directory = ledger.attempt_directory(self.paths, source['sha256'], retry['number'] if retry else 0)
            attempt = json_read(directory/'attempt.json')
            if not attempt or contract(attempt.get('request_contract')) != selected:
                raise ControlError('request_contract_changed', 'Completion authority does not match its original attempt.')
            continuation.request_prompt(attempt, source)
        if answer["status"] in ("no_work", "blocked") and answer["patch_sha256"] == "":
            if self.eligible_patches(source):
                raise ControlError("codex_receipt_conflict", "Codex reports no patch but a bound package exists.")
            ledger.change("no_work" if answer["status"] == "no_work" else "uncertain", error=None if answer["status"] == "no_work" else "dev_blocked")
            return
        if answer['status'] == MIXED and (not selected or selected['version'] != 4 or not (selected['clarification_allowed'] or selected['clarification_continuation'])):
            raise ControlError('clarification_limit', 'No new or proven pending mixed handoff is authorized.')
        if answer['status'] == 'spec_clarification' and (selected is None or selected['version'] not in (2, 3) or not selected['clarification_allowed']):
            raise ControlError('clarification_limit', 'This request cannot hand off a specification clarification.')
        if answer["status"] not in ("patch_ready", "spec_clarification", MIXED) or len(answer["patch_sha256"]) != 64:
            raise ControlError("codex_receipt_invalid", "No unambiguous patch handoff.")
        patches = self.eligible_patches(source)
        if len(patches) != 1 or patches[0]["sha256"] != answer["patch_sha256"]:
            raise ControlError("patch_handoff_unproven", "The claimed patch is missing, ambiguous or not correctly bound.")
        if selected and selected['version'] == 4:
            verify_handoff(self, source, patches[0], selected, answer['status'])
        ledger.change("waiting_result", patch_sha=patches[0]["sha256"], output_kind=answer['status'])

    def close(self):
        self.stack.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()
