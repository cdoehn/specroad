"""Prepare the complete format scope of a supplied project, with no I/O.

Live completeness, source freshness, locking and authority remain obligations
of the existing publication path. This is not a registered format CLI command.
"""
from ..model.errors import ModelError
from ..model.paths import CURRENT_JSON_CLASSES, classify_path
from ..model.representation import NormalizationCandidate
from ..storage.representation import _validate_format_input
from .target_model import TargetModel
from .target_values import TargetError
from .target import prepare_change_target


def prepare_format_target(model, **inputs):
    """Select eligible current files; never normalize protected original records.

    Invalid current resources fail the complete preparation, rather than being
    silently omitted. Explicit representation operations against a protected
    record are errors; automatic scope selection excludes those records.
    """
    if type(model) is not TargetModel:
        raise TargetError('target_model_required')
    model = model.snapshot()
    operations = []
    registry = model.configuration.data.get('language_registry', {}).get('path')
    for path, raw in sorted(model.source_files.items()):
        kind = classify_path(path, model.configuration)
        if kind not in CURRENT_JSON_CLASSES or path == registry:
            continue
        try:
            _validate_format_input(model.configuration, path, raw, kind)
        except ModelError as error:
            if error.reason == 'protected_original_resource':
                continue
            raise
        candidate = NormalizationCandidate(path, raw)
        operations.append({'op': 'representation_normalize', 'path': path,
            'expected_byte_sha256': candidate.expected_byte_sha256,
            'target_byte_sha256': candidate.result_byte_sha256})
    return prepare_change_target(model, operations, **inputs)
