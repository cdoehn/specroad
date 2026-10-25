"""Explicit partial validation using the existing assessment/error contract.

Native closure verification precedes member semantics. Required semantic gates
remain required; unavailable services never become a successful validation.
"""
from dataclasses import replace

from ..bundles.errors import BundleError
from ..cli.results import OperationFailure
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..query._read_errors import read_failure, read_details
from ..validation import validate_model, assess_validation
from ..validation.result_adapter import validation_command_result
from ..documents._read_model import PartialDocumentModel
from ._partial_read import partial_read_snapshot


def validate_partial_project(root, *, selected_ids=None, gates=(), fail_on='error', strict=False):
    try:
        snapshot = partial_read_snapshot(root)
        if snapshot is None:
            raise ModelError('partial_validation_partial_root_required')
        model = PartialDocumentModel(snapshot)
        report = validate_model(model.documents, profile=model.profile, selected_ids=selected_ids,
                                gates=gates, partial=snapshot)
        assessment = assess_validation(report, fail_on=fail_on, strict=strict, documents=model.documents)
        result = validation_command_result('validate', assessment)
        snapshot.verify_current()
        return replace(result, details={**result.details, **snapshot.details},
            project={'project_root': str(snapshot.boundary.root),
                     'project_id': snapshot.configuration.project_id})
    except (BundleError, OperationFailure, ModelError, SafetyViolation, OSError) as error:
        return read_failure('validate', error, None, read_details())


def validate_command(invocation):
    root = invocation.resolved.project_root
    selected = invocation.arguments.get('id')
    selected = None if selected is None else [selected]
    policy = {key: invocation.resolved.values[key] for key in ('fail_on', 'strict')}
    if invocation.options.get('--partial') is True:
        return validate_partial_project(root, selected_ids=selected, **policy)
    try:
        from ..authoring._inspection_snapshot import InspectionSnapshot
        from ..changes._target_materialization import validation_resources
        from ..runtime.preflight import require_project_read_preflight
        from ..storage.preflight_metadata import MetadataPhases
        snapshot = InspectionSnapshot(root, None)
        source, model = snapshot.source, snapshot.model
        require_project_read_preflight(source.boundary, source.configuration_bytes, MetadataPhases())
        report = validate_model(model.documents, profile=model.profile, selected_ids=selected,
                                resources=validation_resources(model))
        assessment = assess_validation(report, documents=model.documents, **policy)
        snapshot.verify_current()
        return replace(validation_command_result('validate', assessment),
            project={'project_root': str(source.boundary.root),
                     'project_id': model.configuration.project_id})
    except (BundleError, OperationFailure, ModelError, SafetyViolation, OSError) as error:
        return read_failure('validate', error, None, read_details())
