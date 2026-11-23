"""Adapt owned Markdown projections to the existing source/edge model.

There is one graph. Derived ownership, binding and prerequisite edges keep
their stored relation identities; they are never copied into source metadata.
"""
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.plan_inventory import PlanProjectionInventory
from ..storage.plan_markdown import PlanSource, parse_plan
from .relation_values import SourceRelations, Relation


def own_sources(sources):
    if type(sources) not in (list, tuple) or any(type(s) is not PlanSource or type(s.path) is not str for s in sources):
        raise ModelError('plan_sources_required')
    owned = tuple(parse_plan(s.source_bytes, path=s.path) for s in sources)
    paths = [s.path for s in owned]
    if len(set(p.casefold() for p in paths)) != len(paths):
        raise ModelError('duplicate_plan_source')
    return tuple(sorted(owned, key=lambda s: s.path))


def _edge(identity, kind, target, **extra):
    return {'relation_id': identity, 'id_scheme': 'random128-v1', 'type': kind,
            'target': target, 'external_identities': [], 'extensions': {}, **extra}


def projection_records(values, paths=None, hashes=None):
    """The same derived edges for owned projections and isolated target folds."""
    paths, hashes = paths or {}, hashes or {}
    if values:
        PlanProjectionInventory(values, id_prefix=values[0]['id'].split('-')[0])
    index = {v['id']: v for v in values}
    result = []
    for value in values:
        record = SourceRelations(canonical_json_bytes(value), path=paths.get(value['id']))
        derived = []
        for position, child_id in enumerate(value['children']):
            child = index[child_id]
            derived.append(_edge(child['parent_relation_id'], 'contains', child_id, position=position))
        for row in value['prerequisites']:
            derived.append(_edge(row['relation_id'], 'requires_entry', row['entry_id']))
        for row in value.get('requirement_bindings', []):
            derived.append(_edge(row['relation_id'], 'plans', row['requirement_id']))
        object.__setattr__(record, 'relations', record.relations + tuple(Relation(record.identity, row) for row in derived))
        object.__setattr__(record, 'validation_scope', 'plan_markdown_projection_and_relations')
        object.__setattr__(record, 'carrier_sha256', hashes.get(value['id']))
        result.append(record)
    return tuple(result)


def records(sources):
    sources = own_sources(sources)
    return projection_records([p.data for s in sources for p in s.projections],
        {p.data['id']:s.path for s in sources for p in s.projections},
        {p.data['id']:s.file_sha256 for s in sources for p in s.projections})


def resource(source, binding):
    from ..model.model_manifest import ManifestResource
    return ManifestResource(binding, {'kind': 'plan_source',
        'id': source.projections[0].data['id'], 'version': 'plan-markdown-v1',
        'path': source.path, 'size': len(source.source_bytes), 'sha256': source.file_sha256,
        'projections': sorted(({'id': p.data['id'], 'sha256': p.sha256}
                              for p in source.projections), key=lambda p: p['id'])})


def check_references(records):
    """Qualified references retain their owner, even with a globally unique ID."""
    index = {r.identity.id: r.data for r in records}
    for identity, value in index.items():
        if value['artifact_type'] not in ('implementation_plan', 'plan_entry'):
            continue
        for ref in [*value['prerequisites'], *(ref for claim in value.get('coverage_claims', [])
                                              for ref in claim['contributors'])]:
            entry = index.get(ref['entry_id'])
            if entry is None or entry.get('plan_id') != ref['plan_id']:
                raise ModelError('plan_qualified_reference_mismatch', pointer='/prerequisites')
        for claim in value.get('coverage_claims', []):
            target = index.get(claim['requirement_id'])
            if target is None or target['artifact_type'] != 'requirement':
                raise ModelError('plan_requirement_target_missing')
