"""Complete direct impact and Appendix J observations over current artifacts."""
from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..diagnostics import Diagnostic, from_model_error
from ..graph.review_status import RelationReviewStatuses
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage._relation_snapshot import _capture_sources
from ..storage.project import ProjectSource
from .show import _preflight, _verify_current


def _impact_rows(records, artifact_id):
    statuses = RelationReviewStatuses(records)
    identities = {record.identity.id for record in records}
    if type(artifact_id) is not str or artifact_id not in identities:
        raise ModelError('unknown_impact_artifact')
    observed = {value.relation_id: value for value in statuses.statuses}
    groups, selected = {}, {}
    for source in records:
        for relation in source.relations:
            status = observed[relation.identity.id]
            for direction, start, related in (
                ('outgoing', source.identity.id, relation.target),
                ('incoming', relation.target, source.identity.id),
            ):
                if start != artifact_id:
                    continue
                selected[status.relation_id] = status
                connection = {'relation_id': status.relation_id,
                    'source_id': status.source_id, 'target_id': status.target_id,
                    'related_id': related, 'direction': direction, 'related_present': related in identities,
                    'review_status': status.status, 'review_reason': status.reason,
                    'selected_review_id': status.selected_review_id,
                    'matching_review_ids': list(status.matching_review_ids),
                    'historical_review_ids': list(status.historical_review_ids)}
                groups.setdefault(relation.type, []).append(connection)
    rows = []
    for kind in sorted(groups):
        connections = sorted(groups[kind], key=lambda c: (c['related_id'], c['direction'], c['relation_id']))
        rows.append({'relation_type': kind, 'artifact_ids': sorted({c['related_id'] for c in connections}),
                     'connections': connections})
    review_groups = {}
    for state in ('unreviewed', 'current', 'suspect', 'invalid'):
        values = [value for value in selected.values() if value.status == state]
        review_groups[state] = {'relation_ids': sorted(value.relation_id for value in values),
                               'affected_ids': sorted({name for value in values
                                                       for name in (value.source_id, value.target_id)})}
    findings = tuple(finding for finding in statuses.diagnostics
                     if any(name in selected for name in finding.related_ids))
    return rows, review_groups, findings


def impact_artifact(root, artifact_id):
    """Report both physical directions, retaining invalid direct bindings.

    This reports the existing Appendix J observation with Core diagnostic
    defaults. It is not full semantic approval, profile-policy evaluation,
    authenticated review history or a prediction of transitive consequences.
    """
    project = None
    details = dict(atomic_snapshot=False, full_semantic_validation=False,
                   approval_granted=False, write_authorized=False, recovery_performed=False,
                   profile_policy_applied=False, diagnostic_policy='core_defaults')
    try:
        source = ProjectSource(root)
        project = {'project_root': str(source.boundary.root), 'project_id': source.configuration.project_id}
        _preflight(source)
        snapshot = _capture_sources(source)
        groups, review_groups, findings = _impact_rows(snapshot.records, artifact_id)
        payload = {'format_version': '1.0.0', 'artifact_id': artifact_id, 'depth': 1,
                   'transitive': False, 'groups': groups, 'review_groups': review_groups,
                   'coverage': {'scope': 'current_project_artifacts', 'source_count': len(snapshot.records),
                       'relation_count': sum(len(record.relations) for record in snapshot.records),
                       'review_record_count': sum(record.identity.artifact_type == 'relation_review'
                                                  for record in snapshot.records),
                       'observation_sha256': snapshot.binding.sha256,
                       'validation_scope': 'artifact_fields_and_relation_review_status_only',
                       'atomic_snapshot': False}}
        _preflight(source)
        _verify_current(source, snapshot.binding)
        validate_result_document('artifact-impact-v1', payload)
        if any(finding.severity == 'error' for finding in findings):
            return CommandResult.failed('impact', FailureKind.POLICY, complete=True,
                result=payload, diagnostics=findings, project=project, details=details)
        return CommandResult('impact', result=payload, diagnostics=findings, project=project, details=details)
    except OperationFailure as error:
        return CommandResult.failed('impact', error.kind, project=project,
            diagnostics=(Diagnostic('CORE_' + error.kind.name, 'error', 'preflight', str(error)),),
            details={**error.details, **details})
    except (ModelError, SafetyViolation, OSError) as error:
        if isinstance(error, ModelError):
            changed = {'configuration_changed', 'relation_source_changed',
                       'relation_index_membership_changed', 'relation_index_source_changed',
                       'show_source_changed', 'show_source_disappeared'}
            code = 6 if error.reason in changed else getattr(error, 'exit_code', 3)
            diagnostic = from_model_error(error)
        else:
            code = 7 if isinstance(error, SafetyViolation) else 5
            diagnostic = Diagnostic('CORE_SECURITY' if code == 7 else 'CORE_ENVIRONMENT',
                'error', 'runtime', 'Impact could not safely read its inputs.')
        return CommandResult.failed('impact', FailureKind(code), project=project,
                                    diagnostics=(diagnostic,), details=details)


def impact_command(invocation):
    return impact_artifact(invocation.resolved.project_root, invocation.arguments['id'])
