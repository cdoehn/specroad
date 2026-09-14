"""Replaceable human presentation. Never use its text or layout as an oracle."""

import json

from .results import CommandResult, FailureKind, ResultStatus, normalize_result, thaw
from .terminal import DisplayPolicy, TerminalWriter


class PrettyRenderer:
    """Narrow, append-only phases, progress, diagnostics and final summaries.

    Progress is supplied by actual work, never a fabricated percentage. This
    presenter neither executes commands nor changes their outcomes.
    """

    def __init__(self, out, err, *, no_color=False, quiet=False):
        self.out = out
        self.err = err
        policy = DisplayPolicy.from_streams(out, err, no_color=no_color, quiet=quiet)
        self.width = policy.width
        self.unicode = policy.unicode
        self.quiet = policy.quiet
        self._terminal = TerminalWriter(policy)

    def _line(self, stream, text="", *, style=None, prefix=""):
        self._terminal.line(stream, text, style=style, prefix=prefix)

    def phase(self, label):
        if not self.quiet:
            mark = "◌" if self.unicode else ">"
            self._line(self.err, label, style="phase", prefix=mark + " ")

    def progress(self, completed, total=None, *, label="Work"):
        if self.quiet:
            return
        if type(completed) is not int or completed < 0:
            return
        if total is None:
            message = f"{label}: {completed} units completed"
        elif type(total) is int and total >= completed and total > 0:
            message = f"{label}: {completed}/{total} units ({100 * completed // total}%)"
        else:
            message = f"{label}: {completed} units completed"
        self.phase(message)

    def _help(self, payload):
        self._line(self.out, "Usage", style="title")
        self._line(self.out, payload["usage"], prefix="  ")
        self._line(self.out)
        self._line(self.out, "Options", style="title")
        for option in payload.get("options", ()):
            suffix = " | ".join(option.get("values", ()))
            self._line(self.out, option["flag"] + ("  " + suffix if suffix else ""), prefix="  ")
        self._line(self.out)
        self._line(self.out, "Exit codes", style="title")
        for code, meaning in payload.get("exit_codes", {}).items():
            self._line(self.out, f"{code}: {meaning}", prefix="  ")
        self._line(self.out)
        self._line(self.out, "Examples", style="title")
        for example in payload.get("examples", ()):
            self._line(self.out, example, prefix="  ")
        if payload.get("scope"):
            self._line(self.out)
            self._line(self.out, payload["scope"], style="muted")

    def finish(self, outcome: CommandResult):
        # Immutable semantic data is projected, never modified for display.
        payload = thaw(outcome.result)
        # Operational failures without a result document are stderr messages.
        # Actual domain results (including failed policy reports) remain stdout.
        operational = (outcome.status is ResultStatus.FAILED
                       and outcome.failure is not FailureKind.POLICY
                       and payload is None and outcome.result_ref is None)
        stream = self.err if operational else self.out
        if not self.quiet:
            self._line(stream, "SpecRoad  /  " + outcome.command, style="title")
            self._line(stream, ("─" if self.unicode else "-") * self.width, style="muted")
        if outcome.command == "help" and isinstance(payload, dict) and "usage" in payload:
            self._help(payload)
        elif payload is not None:
            self._line(stream, json.dumps(payload, ensure_ascii=True, indent=2, allow_nan=False))
        if outcome.result_ref is not None:
            reference = outcome.result_ref.as_dict()
            self._line(stream, "Complete external result", style="title")
            for name, value in reference.items():
                self._line(stream, f"{name}: {value}", prefix="  ")
        for diagnostic in outcome.diagnostics:
            style = {"error": "error", "warning": "warning", "info": "phase"}[diagnostic.severity]
            self._line(stream, f"{diagnostic.severity.upper()} [{diagnostic.code}] {diagnostic.message}", style=style)
            if diagnostic.path:
                self._line(stream, diagnostic.path, prefix="  ")
            if diagnostic.remediation:
                self._line(stream, "Next: " + diagnostic.remediation, prefix="  ")
        if outcome.details:
            self._line(stream, "Details", style="title")
            self._line(stream, json.dumps(thaw(outcome.details), ensure_ascii=True, indent=2, allow_nan=False))
        if outcome.partial_scope is not None:
            self._line(stream, "Explicit partial scope: " + outcome.partial_scope, style="warning")
        if outcome.continuation is not None:
            claim = outcome.continuation.claim
            self.progress(claim.completed_units, claim.total_units)
            self._line(stream, "Checkpoint: " + claim.checkpoint)
            self._line(stream, "Next action: work.resume; work_dir=" + claim.work_dir)
        if not self.quiet or outcome.status in (ResultStatus.FAILED, ResultStatus.CONTINUATION_REQUIRED):
            states = {
                ResultStatus.SUCCESS: ("success", "✓" if self.unicode else "+", "Completed"),
                ResultStatus.PARTIAL: ("warning", "!", "Completed explicit partial scope"),
                ResultStatus.FAILED: ("error", "×" if self.unicode else "X", "Failed"),
                ResultStatus.CONTINUATION_REQUIRED: ("warning", "↻" if self.unicode else ">", "Continuation required"),
            }
            style, symbol, label = states[outcome.status]
            if outcome.failure is not None:
                label += " / " + outcome.failure.name.lower()
            counts = {severity: sum(item.severity == severity for item in outcome.diagnostics)
                      for severity in ("error", "warning", "info")}
            self._line(self.out)
            self._line(stream, label + f"  |  {counts['error']} errors, {counts['warning']} warnings",
                       prefix=symbol + " ", style=style)


def render(status: int, out, err) -> None:
    """Compatibility entry for the original bootstrap presenter."""
    PrettyRenderer(out, err).finish(normalize_result(status, "help" if status == 0 else "unknown"))
