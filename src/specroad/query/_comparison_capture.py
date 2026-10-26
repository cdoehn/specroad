"""Internal source-adapter result and its original observation boundary."""
from dataclasses import dataclass
from typing import Callable

from ..model.configuration import ProjectConfiguration


@dataclass(frozen=True)
class SourceCapture:
    """Owned inputs with adapter-specific checks, not a live source resolver."""
    configuration: ProjectConfiguration
    resources: tuple[tuple[str, bytes], ...]
    source_root: str
    commit_id: str | None = None
    check: Callable[[], bytes | None] | None = None
    evidence_key: str | None = None
    recheck_before_result: bool = False

    def finish(self):
        """Complete the original observation after shared input validation."""
        return self.check() if self.check is not None else None
