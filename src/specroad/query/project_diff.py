"""Public semantic Diff over a pinned Git or explicitly selected local base."""
from pathlib import Path

from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, OperationFailure
from ..model.errors import ModelError
from ..security import SafetyViolation
from ._read_errors import read_details, read_failure
from .comparison_sources import ComparisonSourceSnapshot, compare_sources
from .read_work import complete_read_command, complete_read_steps


def _diff_steps(root, against, *, against_kind='git'):
    project = None
    details = read_details()
    try:
        if type(against_kind) is not str or against_kind not in ('git', 'local'):
            raise ModelError('comparison_source_unavailable')
        if type(against) is not str or not against.strip() or '\0' in against:
            raise ModelError('comparison_reference_required')
        before = (ComparisonSourceSnapshot(root, kind='git', reference=against)
                  if against_kind == 'git' else ComparisonSourceSnapshot(against))
        after = ComparisonSourceSnapshot(root, expected_project_id=before.configuration.project_id)
        project = {'project_root': after.source_root, 'project_id': after.configuration.project_id}
        yield 'loaded'
        compared = compare_sources(before, after)
        payload = compared.data
        details.update(before_source_sha256=before.sha256, after_source_sha256=after.sha256,
            base_commit=before.commit_id, comparison_sha256=compared.sha256,
            comparison_scope='project_configuration_and_artifacts')
        yield 'evaluated'
        if against_kind == 'local':
            current_base = ComparisonSourceSnapshot(before.source_root,
                expected_project_id=before.configuration.project_id)
            if current_base.sha256 != before.sha256:
                raise ModelError('diff_source_changed')
        current = ComparisonSourceSnapshot(after.source_root,
            expected_project_id=after.configuration.project_id)
        if current.sha256 != after.sha256:
            raise ModelError('diff_source_changed')
        validate_result_document('artifact-diff-v1', payload)
        return CommandResult('diff', result=payload, project=project, details=details)
    except (OperationFailure, ModelError, SafetyViolation, OSError) as error:
        return read_failure('diff', error, project, details)


def diff_project(root, against, *, against_kind='git'):
    """Compare exact captured sources, rejecting unsupported resource semantics."""
    return complete_read_steps(_diff_steps(root, against, against_kind=against_kind))


def diff_command(invocation):
    against = invocation.options['--against']
    kind = invocation.options.get('--against-kind', 'git')
    if kind == 'local' and not Path(against).is_absolute():
        against = str(invocation.resolved.working_directory / against)
    return complete_read_command(invocation, _diff_steps, against, against_kind=kind)
