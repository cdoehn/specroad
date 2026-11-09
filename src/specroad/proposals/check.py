"""Isolated Proposal inspection, using native services and no command chaining."""
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PurePosixPath
import os
import shutil
import tempfile

from .._metadata import __version__
from ..authoring._inspection_snapshot import InspectionSnapshot
from ..bundles.errors import BundleError
from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, OperationFailure
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..query._read_errors import read_details, read_failure
from ..security import SafetyViolation
from ..srx.errors import SrxError
from ..storage.project import ProjectSource
from ._validation_input import ProposalInput
from ._validation_result import validation_failure
from .context import ProposalContext, reconstruct_proposal_target
from .project_validation import _preflight
from .scope import specification_manifest
from .validation import validate_proposal
from .values import require


class CheckWorkspace:
    """Fresh private directory, never a project-selected program or output path."""
    def __init__(self, project_root, keep):
        require(type(keep) is bool, 'proposal_debug_boolean_required', exit_code=2)
        self.path = None
        self.keep = keep
        self.state = dict(retained=False, path=None, cleanup='not_created')
        self.project_root = Path(project_root).resolve()

    def create(self):
        # gettempdir() probes candidate directories by writing a file. Check
        # each stdlib candidate BEFORE any such write, including the cwd fallback.
        candidates = ((tempfile.tempdir,) if tempfile.tempdir is not None
                      else tempfile._candidate_tempdir_list())
        last_error = None
        for candidate in candidates:
            parent = Path(os.fsdecode(candidate)).resolve()
            require(parent != self.project_root and self.project_root not in parent.parents,
                    'proposal_workspace_inside_project', exit_code=7)
            try:
                self.path = Path(tempfile.mkdtemp(prefix='specroad-proposal-check-', dir=parent))
                break
            except OSError as error:
                last_error = error
        else:
            raise last_error or OSError('No usable private Proposal workspace parent')
        return self

    def materialize(self, name, files):
        root = self.path / name
        root.mkdir(mode=0o700)
        for path, raw in sorted(files.items()):
            parts = PurePosixPath(path)
            require(type(path) is str and parts.as_posix() == path and not parts.is_absolute()
                    and not any(p in ('', '.', '..') for p in path.split('/')) and '\\' not in path,
                    'proposal_workspace_path_invalid', exit_code=7)
            target = root / path
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(raw)
            target.chmod(0o600)
        return root

    def close(self):
        if self.path is None:
            return
        if self.keep:
            self.state.update(retained=True, path=str(self.path), cleanup='retained')
        else:
            self.state.update(path=str(self.path), cleanup='failed')
            shutil.rmtree(self.path)
            self.state.update(path=None, cleanup='removed')


def _now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _initial():
    return dict(format_version='proposal-check-v1', passed=False, observed_status=None,
        eligible_transition=None, binding=None, proposal_sha256=None, context_sha256=None,
        target_model_root_sha256=None, target_sources_sha256=None, checks={},
        audit=dict(proposal_id=None, base=None, tool_version=__version__, started_at=_now(),
            ended_at=None, outcome='failed', diagnostics=[], created_ids=[], changed_ids=[], removed_ids=[]),
        workspace=dict(retained=False, path=None, cleanup='not_created'),
        full_semantic_validation=False, approval_granted=False, write_authorized=False)


def _specification_files(model, files):
    from ..storage.json_syntax import parse_json_object
    # Reuse the fixed closure check before removing its excluded control records.
    specification_manifest(model)
    excluded = {d.path for d in model.documents
                if parse_json_object(d.content)['artifact_type'] in ('proposal', 'baseline')}
    return {p: raw for p, raw in files.items() if p not in excluded}


def _qualify(files, checks, side, services):
    from ..recovery._validation import project_validation_report
    model, _, report = project_validation_report(files, services=services)
    checks.setdefault('validation', {})[side] = report.data
    for stage in report.data['stages']:
        require(stage['status'] != 'unavailable', 'proposal_' + stage['stage'] + '_provider_required')
        if stage['status'] == 'failed':
            diagnostic = stage['diagnostics'][0]
            require(False, diagnostic['reason'], path=diagnostic.get('path'))
    require(report.complete and report.passed, 'proposal_full_validation_required')
    return model


def _services(basis, target, report):
    from ..documents.rendering import render_document, render_view
    from ..documents.tables import resolve_table_block
    from ..documents.views import resolve_view
    from ..graph.comparison_values import ComparisonInputs
    from ..graph.relations import SourceRelations
    from ..graph._impact_projection import _impact_rows, _artifact_observations
    from ..lint import lint_core
    from ..query.semantic_diff import compare_semantic
    checks = report['checks']
    left = tuple(SourceRelations(d.content, path=d.path) for d in basis.documents)
    right = tuple(SourceRelations(d.content, path=d.path) for d in target.documents)
    checks['lint'] = lint_core(right, profile=target.profile)
    require(checks['lint']['core_checks_passed'], 'proposal_lint_failed')
    queries, renders = [], []
    checks.update(queries=queries, renders=renders)
    for item in sorted(target.artifacts, key=lambda a: a['id']):
        kind, identifier = item['artifact_type'], item['id']
        if kind == 'view':
            queries.append(dict(artifact_id=identifier, result=resolve_view(target, identifier).data))
        elif kind == 'content_block' and item['block_kind'] in ('query', 'table'):
            queries.append(dict(artifact_id=identifier, result=resolve_table_block(target, identifier).data))
        if kind in ('document', 'view'):
            formats = (item.get('render_policy', {}).get('formats', ['markdown']) if kind == 'document'
                       else item.get('formats', ['markdown']))
            for output_format in formats:
                rendered = (canonical_json_bytes(resolve_view(target, identifier).data)
                            if kind == 'view' and output_format == 'json' else
                            (render_document if kind == 'document' else render_view)(
                                target, identifier, output_format=output_format))
                renders.append(dict(artifact_id=identifier, format=output_format,
                                    size=len(rendered), sha256=sha256(rendered).hexdigest()))
    diff = compare_semantic(ComparisonInputs(basis.configuration.project_id, left),
        ComparisonInputs(target.configuration.project_id, right),
        before_configuration=basis.configuration, after_configuration=target.configuration).data
    checks['diff'] = diff
    report['audit']['created_ids'] = diff['inventory_delta']['added_ids']
    report['audit']['removed_ids'] = diff['inventory_delta']['removed_ids']
    report['audit']['changed_ids'] = sorted(row['artifact_id'] for row in diff['changes'])
    checks['impact'] = impacts = []
    for identifier in report['audit']['changed_ids']:
        observation = dict(artifact_id=identifier, depth=1, transitive=False, before=None, after=None)
        for side, records in (('before', left), ('after', right)):
            if identifier in {r.identity.id for r in records}:
                groups, reviews, findings = _impact_rows(records, identifier)
                observation[side] = dict(groups=groups, review_groups=reviews,
                    artifact_observations=_artifact_observations(records, identifier, groups),
                    diagnostics=[f.as_dict() for f in findings])
                report['audit']['diagnostics'].extend(observation[side]['diagnostics'])
                require(not any(f.severity == 'error' for f in findings), 'proposal_impact_failed')
        impacts.append(observation)


def _isolated(snapshot, original, workspace, report, services):
    basis_root = workspace.materialize('basis', snapshot.raw)
    private = InspectionSnapshot(basis_root, None, include_archive_objects=True)
    context = ProposalContext(original, private.model)
    validate_proposal(context)
    target = reconstruct_proposal_target(context)
    # Preserve packages which have native identities but no TargetModel source path.
    extra = {p: raw for p, raw in private.raw.items() if p not in private.model.source_files}
    target_root = workspace.materialize('target', {**extra, **target.source_files})
    actual = InspectionSnapshot(target_root, None, include_archive_objects=True)
    require(actual.model._sources_sha256 == target._sources_sha256,
            'proposal_materialized_target_changed', exit_code=6)
    report['target_model_root_sha256'] = specification_manifest(actual.model).sha256
    report['target_sources_sha256'] = actual.model._sources_sha256
    basis = _qualify(_specification_files(private.model, private.raw), report['checks'], 'basis', services)
    final = _qualify(_specification_files(actual.model, actual.raw), report['checks'], 'target', services)
    _services(basis, final, report)
    private.verify_current()
    actual.verify_current()


def check_proposal_project(root, operand, *, cwd=None, keep_workspace=False, services=None):
    """Return bound observations; no caller-supplied check result grants authority."""
    project = None
    source = snapshot = supplied = context = workspace = None
    report = _initial()
    details = read_details()
    try:
        from ..recovery.services import native_services
        services = native_services(services)
        source = ProjectSource(root)
        project = dict(project_root=str(source.boundary.root), project_id=source.configuration.project_id)
        _preflight(source)
        supplied = ProposalInput(source, operand, cwd)
        try:
            original = supplied.original()
            snapshot = InspectionSnapshot(root, None, include_archive_objects=True)
            context = ProposalContext(original, snapshot.model)
            report.update(observed_status=original.data['proposal_status'], binding=original.binding.data,
                proposal_sha256=original.sha256, context_sha256=context.sha256)
            report['audit'].update(proposal_id=original.data['id'], base=original.data['base'])
            workspace = CheckWorkspace(source.boundary.root, keep_workspace)
            try:
                workspace.create()
                _isolated(snapshot, original, workspace, report, services)
            finally:
                workspace.close()
                report['workspace'] = dict(workspace.state)
        finally:
            _preflight(source)
            source.check_current()
            supplied.verify_current()
            if snapshot is not None:
                snapshot.verify_current()
        report.update(passed=True, full_semantic_validation=True,
            eligible_transition='checked' if report['observed_status'] == 'validated' else None)
        result = CommandResult('proposal.check', project=project, details={**details,
            'full_semantic_validation': True, 'validation_scope': 'proposal_specification_basis_and_target'})
    except (ModelError, OperationFailure, SafetyViolation, OSError, SrxError, BundleError) as error:
        result = read_failure('proposal.check', error, project, details)
        observed = validation_failure(None if supplied is None else supplied.raw, context,
            getattr(error, 'reason', None) or 'proposal_check_failed')
        report.update(observed_status=observed['observed_status'], proposal_sha256=observed['proposal_sha256'])
        report['audit']['diagnostics'] = [d.as_dict() for d in result.diagnostics]
        if workspace is not None:
            report['workspace'] = dict(workspace.state)
    report['audit']['diagnostics'] += [d for value in report['checks'].get('validation', {}).values()
        for stage in value['stages'] for d in stage['diagnostics']]
    report['audit']['diagnostics'] += report['checks'].get('lint', {}).get('diagnostics', [])
    report['audit'].update(ended_at=_now(), outcome='passed' if report['passed'] else 'failed')
    report['result_sha256'] = canonical_json_sha256(report)
    validate_result_document('proposal-check-v1', report)
    return replace(result, result=report)


def check_command(invocation):
    return check_proposal_project(invocation.resolved.project_root, invocation.arguments['proposal'],
        cwd=invocation.resolved.working_directory,
        keep_workspace=invocation.options.get('--keep-workspace', False), services=invocation.restore_services)
