"""Direct native services for the isolated basis and planned specification."""
from hashlib import sha256
from ..model.canonical import canonical_json_bytes
from .scope import specification_manifest
from .values import require


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
