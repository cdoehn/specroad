"""Prepare formatting for explicitly named current resources; never write them."""

from ..model.errors import ModelError
from ..model.paths import CURRENT_JSON_CLASSES, project_path
from ..model.representation import NormalizationCandidate
from ..model._representation_scope import _validate_format_input
from .project import ProjectSource


def prepare_normalization(source: ProjectSource, path: str) -> NormalizationCandidate:
    """Read and propose bytes only; no normalizer writes or source fallback."""
    if not isinstance(source, ProjectSource):
        raise TypeError("A bound ProjectSource is required")
    path = project_path(path)
    kind = source.classify(path)
    if kind not in CURRENT_JSON_CLASSES:
        raise ModelError("resource_not_formatable", path=path)
    raw = source.read_normative(path)
    try:
        _validate_format_input(source.configuration, path, raw, kind)
        candidate = NormalizationCandidate(path, raw)
    except ModelError as error:
        error.path = path
        raise
    candidate.require_current(source.read_normative(path))
    source.check_current()
    return candidate


def check_normalization_current(source: ProjectSource, candidate: NormalizationCandidate) -> None:
    """Recheck a candidate read-only; this is NOT the later transaction lock.

    Never use cached classification or previous eligibility as write permission.
    A future writer must perform its own check under its transaction boundary.
    """
    if not isinstance(candidate, NormalizationCandidate):
        raise TypeError("A NormalizationCandidate is required")
    current = prepare_normalization(source, candidate.path)
    candidate.require_current(current.source_bytes)


def prepare_normalizations(source: ProjectSource, paths) -> tuple[NormalizationCandidate, ...]:
    """Complete result for an explicit set, or an error; no inventory/scan/write.

    Every original is checked again after collection. This detects observed
    changes but does not claim an atomic multi-file snapshot without a lock.
    """
    if not isinstance(source, ProjectSource):
        raise TypeError("A bound ProjectSource is required")
    if isinstance(paths, (str, bytes, dict)):
        raise ModelError("path_sequence_required")
    try:
        names = tuple(project_path(path) for path in paths)
    except TypeError as error:
        raise ModelError("path_sequence_required") from error
    if len(set(names)) != len(names):
        raise ModelError("duplicate_resource_path")
    source.check_current()
    candidates = tuple(prepare_normalization(source, path) for path in sorted(names))
    for candidate in candidates:
        candidate.require_current(source.read_normative(candidate.path))
    source.check_current()
    return candidates
