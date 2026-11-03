"""Source-only field, graph and historical-binding rules over owned values.

Shared Core primitives validate unchanged value contracts, never a relabelled
0.2 artifact. Stored approval labels do not authenticate their actors.
"""
from functools import lru_cache
from hashlib import sha256
from importlib import resources
from types import SimpleNamespace

from ...model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ...model.errors import ModelError
from ...model.record_schemas import _validate_local_record
from ...model.domain_schemas import _milestone_release
from ...model.language_registry import LanguageRegistry
from ...graph.scope_descriptors import ScopeDescriptor
from ...graph.relation_types import relation_pair_allowed
from ...graph._graph_traversal import _cycle_witness
from ...verification.evaluation import VerificationEvaluation
from ...planning._readiness_policy import readiness_policy
from ...srx import parse_program
from .reader import SourceError, require, path_name, context_sha256, _schema, classification


@lru_cache(maxsize=1)
def _languages():
    raw = resources.files('specroad.reference01_data').joinpath('registry.txt').read_bytes()
    return LanguageRegistry(raw,
        expected_sha256='3016607e64244c05b1ee2f9d469e399377fda86169c6f255bffd995b838c2fd4',
        expected_version=raw.decode('utf-8').splitlines()[0].split(': ', 1)[1])


def _identity(value, assets, prefix=None):
    import re
    require(type(value) is str and re.fullmatch(r'[A-Z][A-Z0-9]{1,7}-[A-Z]+-[0-9]{4}', value),
            'source_identity_conflict')
    project, token, _ = value.split('-')
    require(token in {row['prefix'] for row in assets['artifact_types'].values()}
            and (prefix is None or project == prefix), 'source_identity_conflict')


def _unique(items, path):
    keys = [jcs(v) for v in items]
    require(len(set(keys)) == len(keys), 'source_identity_conflict', path)


def local_fields(value, path, assets):
    try:
        kind = value['artifact_type']
        _validate_local_record(value)
        if kind == 'milestone':
            _milestone_release(value)
        for field in ('language',):
            if field in value:
                assessment = _languages().inspect(value[field])
                require(assessment.syntax_valid and not assessment.unknown_subtags,
                        'source_schema_invalid', path, 'unregistered_language')
        for row in [value, *value['relations']]:
            _unique([[v['source_system'], v['source_document'], v['external_id']]
                     for v in row.get('external_identities', ())], path)
        if 'applicability' in value:
            parse_program(jcs(value['applicability']), rule_id='reference01-applicability')
        if kind != 'baseline' and 'scope_descriptor' in value:
            ScopeDescriptor(value['scope_descriptor'])
        waiver = value.get('verification_waiver')
        if waiver is not None:
            ScopeDescriptor(waiver['scope_descriptor'])
        if kind == 'view':
            from ...documents._view_definition import plan_view
            plan_view(value, SimpleNamespace(path=path), 0, ModelError)
        if kind == 'content_block' and value['block_kind'] == 'query' and 'query' in value['payload']:
            from ...query import NormalizedQuery
            query = value['payload']['query']
            if set(query) == {'language', 'version', 'expression'}:
                parse_program(jcs(query), rule_id='reference01-block-query')
            else:
                NormalizedQuery(**query)
        if kind == 'release':
            readiness_policy(value['readiness_policy'])
        if kind == 'baseline' and 'verification_evaluation' in value:
            VerificationEvaluation(jcs(value['verification_evaluation']))
        if kind == 'test' and 'path' in value['test_identity']:
            path_name(value['test_identity']['path'])
        if kind == 'proposal':
            from .stored_plans import proposal_fields
            proposal_fields(value, path, assets)
    except SourceError:
        raise
    except (ModelError, ValueError, TypeError, RecursionError) as error:
        raise SourceError('source_schema_invalid', path=path,
                          detail=getattr(error, 'reason', str(error))) from error


def prose_payloads(value, path):
    """Parse only the inherited inert Markdown subset, without a current loader."""
    if value['artifact_type'] != 'content_block' or value['block_kind'] not in ('prose','admonition'):
        return ()
    from ...documents.prose import _parse_markdown
    _, node = _parse_markdown(value['payload']['markdown'], path=path)
    pending, names = [node], set()
    while pending:
        current = pending.pop()
        if 'attachment_path' in current:
            names.add(path_name(current['attachment_path']))
        pending.extend(current.get('children', ()))
    return tuple(sorted(names, key=lambda p: p.encode('utf-8')))


def code_selection(value, raw, path):
    from ...verification._code_selection_hash import normalized_text, selection_utf8
    from ...verification._code_selection_cursor import stored_line_span
    kind = value['reference_kind']
    if kind not in ('line_range', 'text_anchor'):
        return
    selector = value['anchor'] if kind == 'text_anchor' else value
    if kind == 'text_anchor' and selector['kind'] == 'byte_range':
        start, end = int(selector['start_offset']), int(selector['end_offset'])
        require(0 <= start <= end <= len(raw), 'source_schema_invalid', path, 'byte_range')
        selected = raw[start:end]
    else:
        text = normalized_text(raw, selector['encoding'])
        start, end, _ = stored_line_span(text, int(selector['start_line']), int(selector['end_line']))
        require(end is not None, 'source_schema_invalid', path, 'line_range')
        selected = selection_utf8(text[start:end])
    require(sha256(selected).hexdigest() == value['selection_sha256'],
            'source_hash_mismatch', path, 'code_selection')


def references(snapshot, assets):
    index = snapshot['index']
    edges, parents, included = {}, {}, []
    def target(identity, kind=None):
        require(identity in index, 'source_closure_incomplete', detail=identity)
        value = index[identity][1]
        require(kind is None or value['artifact_type'] == kind, 'source_identity_conflict', detail=identity)
        return value
    for identity, (path, value) in index.items():
        kind = value['artifact_type']; seen = set()
        for i, rel in enumerate(value['relations']):
            other = target(rel['target']); key = rel['type'], rel['target']
            require(key not in seen and rel['target'] != identity and
                    relation_pair_allowed(rel['type'], kind, other['artifact_type']),
                    'source_identity_conflict', path, 'relation_endpoint_or_duplicate')
            seen.add(key)
            if rel['type'] in ('duplicates', 'conflicts_with'):
                require(identity.encode('utf-8') < rel['target'].encode('utf-8'),
                        'source_identity_conflict', path, 'symmetric_relation_owner')
            edges.setdefault(rel['type'], []).append((identity, rel['target']))
            if rel['type'] == 'contains':
                require(rel['target'] not in parents, 'source_closure_incomplete', path,
                        'multiple_document_parents')
                parents[rel['target']] = identity
        if kind == 'interface':
            target(value['source_component'], 'component'); target(value['target_component'], 'component')
        if kind == 'verification':
            for subject in value['subjects']:
                target(subject)
            for slot in value['evidence_slots']:
                if slot['test_id'] is not None:
                    target(slot['test_id'], 'test')
        if kind == 'configuration' and value.get('parent') is not None:
            target(value['parent'], 'configuration')
            edges.setdefault('configuration_parent', []).append((identity, value['parent']))
        for provenance in value.get('provenance', ()):
            if 'source_id' in provenance:
                target(provenance['source_id'], 'source')
        if kind == 'content_block' and value['block_kind'] == 'include_document':
            included.extend((identity, r['target']) for r in value['relations'] if r['type'] == 'references')
        waiver = value.get('verification_waiver')
        if waiver and 'format_version' not in waiver:
            target(waiver['human_review_id'], 'relation_review')
        if value['maturity'] == 'approved':
            outgoing = value['relations']
            types = {r['type'] for r in outgoing}
            if kind in ('need', 'capability', 'requirement'):
                require(bool(types & {'addresses', 'derived_from', 'refines'}) or
                        kind == 'capability' and bool(value.get('provenance')),
                        'source_state_invalid', path, 'origin_required')
            if kind == 'requirement':
                require('verified_by' in types, 'source_state_invalid', path, 'verification_required')
            if kind == 'component':
                require(bool(outgoing), 'source_state_invalid', path, 'component_relation_required')
            if kind == 'task':
                require(any(v['artifact_type'] in ('requirement', 'decision') and
                    any(r['type'] == 'implemented_by' and r['target'] == identity for r in v['relations'])
                    for _, v in index.values()), 'source_state_invalid', path, 'task_implementation_required')
            if kind == 'risk':
                require(bool(value.get('acceptance_rationale')) or any(
                    r['type'] == 'mitigates' and r['target'] == identity
                    for _, v in index.values() for r in v['relations']),
                    'source_state_invalid', path, 'risk_mitigation_required')
    for identity, (path, value) in index.items():
        if value['artifact_type'] in ('section', 'content_block'):
            require(identity in parents, 'source_closure_incomplete', path, 'document_parent_required')
    for name in ('refines', 'part_of', 'supersedes', 'contains', 'configuration_parent'):
        require(_cycle_witness(edges.get(name, ()), source_id=lambda e: e[0],
            target_id=lambda e: e[1], edge_id=lambda e: e) is None,
            'source_closure_incomplete', detail='cycle:' + name)
    require(_cycle_witness([*edges.get('contains', ()), *included], source_id=lambda e: e[0],
            target_id=lambda e: e[1], edge_id=lambda e: e) is None,
            'source_closure_incomplete', detail='document_include_cycle')
    _configurations(index)


def _configurations(index):
    names = set()
    for identity, (path, value) in index.items():
        if value['artifact_type'] != 'configuration':
            continue
        require(value['name'] not in names, 'source_identity_conflict', path)
        names.add(value['name'])
        chain, cursor = [], value
        while cursor is not None:
            chain.append(cursor)
            cursor = index[cursor['parent']][1] if cursor.get('parent') else None
        dimensions, selection = {}, {}
        for current in reversed(chain):
            for dim in current['dimensions']:
                require(dim['name'] not in dimensions or jcs(dim) == jcs(dimensions[dim['name']]),
                        'source_schema_invalid', path, 'inherited_dimension_changed')
                dimensions[dim['name']] = dim
            for name, choice in current['selection'].items():
                require(name in dimensions and any(jcs(choice) == jcs(v)
                    for v in dimensions[name]['allowed_values']), 'source_schema_invalid', path)
                selection[name] = choice
        require(all(name in selection or 'default' in dim for name, dim in dimensions.items()),
                'source_closure_incomplete', path, 'configuration_selection_incomplete')


def release_selection(baseline, snapshot):
    identity = baseline.get('release_id')
    require(identity in snapshot['index'], 'source_closure_incomplete', detail='release_selection')
    release = snapshot['index'][identity][1]
    require(release['artifact_type'] == 'release', 'source_identity_conflict')
    expected = release['readiness_policy'].get('verification_evaluation')
    require(expected is not None, 'source_closure_incomplete', detail='release_evaluation_missing')
    require(jcs(expected) == jcs(baseline.get('verification_evaluation')),
            'source_hash_mismatch', detail='release_evaluation_mismatch')
    evaluation = VerificationEvaluation(jcs(expected))
    require(evaluation.data['configuration_hash'] is None, 'source_schema_invalid',
            detail='unconfigured_release_snapshot_required')
    # The input manifest and selected recorded runs are retained original proof,
    # not a new release approval. Every declared original must be present.
    for row in evaluation.data['evaluated_subject']['manifest']:
        raw = snapshot['files'].get(row['logical_path'])
        require(raw is not None, 'source_payload_missing', row['logical_path'])
        require(len(raw) == row['size'] and sha256(raw).hexdigest() == row['sha256'],
                'source_hash_mismatch', row['logical_path'])
    for run in evaluation.data['required_runs']:
        require(run['subject_artifact_id'] in snapshot['index'] and run['contract_id'] in snapshot['index'],
                'source_closure_incomplete', detail='release_run_contract_missing')
        for run_id in run['run_ids']:
            matches = [v for _, v in snapshot['index'].values() if v['artifact_type'] == 'evidence'
                and v['run_context'] is not None and v['run_context']['run_id'] == run_id
                and v['run_context']['check_id'] == run['check_id']
                and v['run_context']['test_id'] == run['test_id']
                and v['run_context']['subject_id'] == evaluation.data['evaluated_subject']['subject_id']
                and v['run_context']['subject_state_sha256'] == evaluation.data['evaluated_subject']['state_sha256']
                and any(s['artifact_id'] == run['subject_artifact_id'] for s in v['subjects'])]
            require(bool(matches) and all(v['result'] == 'passed' for v in matches),
                    'source_state_invalid', detail='release_required_run_not_passed')


def historical_bindings(snapshots, assets):
    def original(identity, revision, full_hash, root=None):
        found = []
        for snapshot in snapshots:
            if root is not None and root != snapshot['root']:
                continue
            candidate = snapshot['index'].get(identity)
            if candidate and candidate[1]['revision'] == revision and digest(candidate[1]) == full_hash:
                found.append(candidate[1])
        require(bool(found), 'source_closure_incomplete', detail='historical_original:' + identity)
        return found[0]
    for snapshot in snapshots:
        for path, value in snapshot['index'].values():
            kind = value['artifact_type']
            if kind == 'evidence':
                for subject in value['subjects']:
                    source = original(subject['artifact_id'], subject['revision'], subject['artifact_sha256'])
                    require(context_sha256(source) == subject['verification_context_sha256'],
                            'source_hash_mismatch', path, 'evidence_context')
                if value['run_context'] is not None and value['run_context']['test_id'] is not None:
                    require(any(value['run_context']['test_id'] in s['index'] for s in snapshots),
                            'source_closure_incomplete', path)
            if kind == 'relation_review':
                source = original(value['source_id'], value['source_revision'], value['source_artifact_sha256'])
                target = original(value['target_id'], value['target_revision'], value['target_artifact_sha256'])
                locator = value['relation_locator']
                require(locator['source_id'] == source['id'] and locator['index'] < len(source['relations']),
                        'source_closure_incomplete', path, 'review_locator')
                relation = source['relations'][int(locator['index'])]
                require(relation['target'] == target['id'] and digest(relation) == value['relation_content_sha256']
                    and context_sha256(source) == value['source_context_sha256']
                    and context_sha256(target) == value['target_context_sha256'],
                    'source_hash_mismatch', path, 'review_original_binding')
            if kind == 'proposal':
                from .stored_plans import proposal_history
                proposal_history(value, path, snapshots, assets)
