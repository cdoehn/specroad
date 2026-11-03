"""No process killing, scheduling or model calls: just lifecycle decisions."""
from dataclasses import dataclass
from .errors import ControlError

@dataclass
class Lifecycle:
    desired: str = "running"
    active_job: bool = False
    stopping: bool = False

    @property
    def phase(self) -> str:
        if self.stopping:
            return "stopping" if self.active_job else "stopped"
        if self.active_job:
            return "pausing" if self.desired == "paused" else "working"
        return "paused" if self.desired == "paused" else "idle"

    def request(self, command: str):
        if command == "stop":
            self.stopping = True
        elif command in ("pause", "resume"):
            if self.stopping:
                raise ControlError("stopping", "A pending stop cannot be cancelled.")
            self.desired = "paused" if command == "pause" else "running"
        else:
            raise ControlError("invalid_command", "Unknown lifecycle command.")

    def begin_job(self):
        if self.phase != "idle":
            raise ControlError("not_idle", "No new job is allowed in this lifecycle state.")
        self.active_job = True

    def finish_job(self):
        if not self.active_job:
            raise ControlError("not_working", "No active job to finish.")
        self.active_job = False
