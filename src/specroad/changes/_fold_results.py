"""One pre-metadata candidate per touched artifact after ordered evaluation."""
from ._patch_values import _snapshot
from .folding_values import FoldedArtifact, OperationFold


def _finish(state, base, touched, operations_applied, preconditions_checked, *, hasher):
    candidates = tuple(FoldedArtifact(target, _snapshot(state[target]),
        hasher(base[target]) if target in base else None,
        hasher(state[target]), tuple(touched[target]))
        for target in sorted(touched, key=lambda name: name.encode("utf-8")))
    ordered = [state[target] for target in sorted(state, key=lambda name: name.encode("utf-8"))]
    return OperationFold(_snapshot(ordered), candidates, operations_applied, preconditions_checked)
