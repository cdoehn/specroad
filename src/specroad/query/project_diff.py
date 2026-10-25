"""Public semantic Diff over a pinned Git or explicitly selected local base."""
from pathlib import Path

from ..cli.result_schemas import validate_result_document
from ..bundles.errors import BundleError
from ..srx.errors import SrxError
from ..cli.results import CommandResult, FailureKind, OperationFailure, ResultStatus
from ..diagnostics import Diagnostic
from ..model.errors import ModelError
from ..security import SafetyViolation
from ._read_errors import read_details, read_failure
from .comparison_sources import ComparisonSourceSnapshot, compare_sources
from .read_work import complete_read_command, complete_read_steps


def _diff_steps(root, against, *, against_kind='git', configuration_id=None,
                before_currentness=None, after_currentness=None):
    project = None
    details = read_details()
    try:
        if type(against_kind) is not str or against_kind not in ('git', 'local'):
            raise ModelError('comparison_source_unavailable')
        if type(against) is not str or not against.strip() or '\0' in against:
            raise ModelError('comparison_reference_required')
        before = (ComparisonSourceSnapshot(root, kind='git', reference=against)
                  if against_kind == 'git' else ComparisonSourceSnapshot(against, allow_partial=True))
        after = ComparisonSourceSnapshot(root, expected_project_id=before.configuration.project_id, allow_partial=True)
        project = {'project_root': after.source_root, 'project_id': after.configuration.project_id}
        yield 'loaded'
        compared = compare_sources(before, after, before_configuration_id=configuration_id,
            after_configuration_id=configuration_id,
            before_currentness=before_currentness, after_currentness=after_currentness)
        payload = compared.data
        details.update(before_source_sha256=before.sha256, after_source_sha256=after.sha256,
            base_commit=before.commit_id, comparison_sha256=compared.sha256,
            comparison_scope=('project_configuration_and_artifacts' if before.partial is None and after.partial is None
                              else 'supplied_artifact_sets'),
            before_source=before.binding, after_source=after.binding)
        for snapshot in (before, after):
            if snapshot.partial is not None:
                snapshot.partial.verify_current()
        yield 'evaluated'
        for snapshot in (before, after):
            if snapshot.partial is not None:
                snapshot.partial.verify_current()
        if against_kind == 'local':
            current_base = ComparisonSourceSnapshot(before.source_root,
                expected_project_id=before.configuration.project_id, allow_partial=True)
            if current_base.sha256 != before.sha256:
                raise ModelError('diff_source_changed')
        current = ComparisonSourceSnapshot(after.source_root,
            expected_project_id=after.configuration.project_id, allow_partial=True)
        if current.sha256 != after.sha256:
            raise ModelError('diff_source_changed')
        validate_result_document('artifact-diff-v1', payload)
        if payload['configuration_scope']['state'] == 'evaluated':
            diagnostics = tuple(Diagnostic('SRV131', 'error', 'model',
                'An applicable artifact requires an excluded artifact.',
                rule_id='configuration-diff-' + side, artifact_id=item['source_id'],
                related_ids=(item['target_id'],), rationale='configuration_dependency_excluded')
                for side in ('before', 'after')
                for item in payload['configuration_scope'][side]['inconsistent_dependencies'])
            if diagnostics:
                return CommandResult.failed('diff', FailureKind.MODEL, complete=True, result=payload,
                                            project=project, diagnostics=diagnostics, details=details)
        partial = after.partial or before.partial
        if partial is not None:
            return CommandResult('diff', status=ResultStatus.PARTIAL, partial_scope='partial_bundle_artifacts',
                result=payload, project=project, details={**details, **partial.details})
        return CommandResult('diff', result=payload, project=project, details=details)
    except (BundleError, OperationFailure, ModelError, SafetyViolation, OSError) as error:
        return read_failure('diff', error, project, details)


def diff_project(root, against, *, against_kind='git', configuration_id=None,
                 before_currentness=None, after_currentness=None):
    """Compare exact captured sources, rejecting unsupported resource semantics."""
    return complete_read_steps(_diff_steps(root, against, against_kind=against_kind,
        configuration_id=configuration_id, before_currentness=before_currentness,
        after_currentness=after_currentness))


def diff_command(invocation):
    against = invocation.options['--against']
    kind = invocation.options.get('--against-kind', 'git')
    if kind == 'local' and not Path(against).is_absolute():
        against = str(invocation.resolved.working_directory / against)
    return complete_read_command(invocation, _diff_steps, against, against_kind=kind,
                                 configuration_id=invocation.options.get('--configuration'))
