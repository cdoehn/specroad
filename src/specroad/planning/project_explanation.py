"""Public read-only Roadmap explanation over a freshly rechecked inventory.

The pure provider remains an observation of supplied inputs. This adapter adds
live source checks, not atomicity, applicability, readiness or write authority.
"""
from ..authoring._inspection_snapshot import InspectionChanged, InspectionSnapshot
from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, OperationFailure
from ..model.errors import ModelError
from ..query._read_errors import read_details, read_failure
from ..query.read_work import complete_read_command, complete_read_steps
from ..query.show import _preflight
from ..security import SafetyViolation
from ..storage.project import ProjectSource
from .explanation import explain_roadmap


COMMAND = 'roadmap.explain'


def _explain_steps(root, artifact_id):
    project = None
    details = read_details()
    try:
        source = ProjectSource(root)
        project = {'project_root': str(source.boundary.root),
                   'project_id': source.configuration.project_id}
        _preflight(source)
        if 'trace_depth' not in source.configuration.data.get('resource_limits', {}):
            raise ModelError('roadmap_explanation_depth_not_configured', path='specroad.json',
                             pointer='/resource_limits/trace_depth')
        snapshot = InspectionSnapshot(source.boundary.root, None)
        if (snapshot.source.boundary._root_identity != source.boundary._root_identity or
                snapshot.source.configuration_bytes != source.configuration_bytes):
            raise InspectionChanged('roadmap_explanation_source_changed')
        yield 'loaded'
        explanation = explain_roadmap(snapshot.model, artifact_id)
        payload = {'format_version': '1.0.0', 'explanation': explanation.data,
            'explanation_sha256': explanation.sha256,
            'coverage': {'scope': 'configured_project_inventory',
                'source_count': len(snapshot.raw), 'artifact_count': len(snapshot.model.documents),
                'input_sha256': snapshot.model._sources_sha256,
                'source_bytes_rechecked': True, 'atomic_snapshot': False}}
        yield 'evaluated'
        snapshot.verify_current()
        _preflight(source)
        snapshot.verify_current()
        validate_result_document('roadmap-explain-v1', payload)
        return CommandResult(COMMAND, result=payload, project=project, details=details)
    except (OperationFailure, ModelError, SafetyViolation, OSError) as error:
        return read_failure(COMMAND, error, project, details)


def explain_project_roadmap(root, artifact_id):
    """Explain actual project bytes without caches, locks, writes or recovery."""
    return complete_read_steps(_explain_steps(root, artifact_id))


def roadmap_explain_command(invocation):
    return complete_read_command(invocation, _explain_steps, invocation.arguments['id'])
