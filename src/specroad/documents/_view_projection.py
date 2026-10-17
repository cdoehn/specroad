"""Typed view rows and bounded nested projections over an already selected graph."""
from collections import deque
from hashlib import sha256

from ..model.canonical import canonical_json_sha256
from ..model.domain_schemas import DOMAIN_TYPES
from ..srx import MISSING
from ..srx.pointers import resolve_tokens
from ..srx.types import value_type
from ..storage.domain_artifact import DomainArtifact
from ..storage.record_artifact import RecordArtifact


def project_view_rows(index, graph, projections, columns, projection_columns, page, fail):
    def related(start, projection):
        # IDs, not walks or inverse edge views, are counted. The source is not
        # its own related target, even when a cycle leads back to it.
        seen, frontier = {start}, deque([(start, 0)])
        while frontier:
            current, depth = frontier.popleft()
            if depth >= projection['max_depth']:
                continue
            for edge in graph.neighbours(current, projection['direction'], projection['types']):
                target = edge.target.id
                if target not in seen:
                    seen.add(target)
                    frontier.append((target, depth + 1))
        return sorted(seen - {start})

    artifacts = {}
    projected_values = {}

    def bound_row(artifact_id, planned_columns):
        record = index[artifact_id]
        if artifact_id not in artifacts:
            reader = DomainArtifact if record.identity.artifact_type in DOMAIN_TYPES else RecordArtifact
            artifacts[artifact_id] = reader(record.source_bytes, path=record.path).data
        artifact = artifacts[artifact_id]
        cells = []
        for kind, selector, declared, missing, at in planned_columns:
            cell = (resolve_tokens(artifact, selector, rule_id='document-view', at=at)
                    if kind == 'artifact_field' else projected_values[artifact_id, selector])
            if cell is MISSING:
                if missing == 'error':
                    fail('view_column_value_missing', at)
                cells.append({'type': 'missing'})
                continue
            actual = value_type(cell, rule_id='document-view')
            if actual != declared:
                fail('view_column_value_type', at)
            cells.append({'type': actual, 'value': cell})
        return {'artifact_id': artifact_id, 'artifact_type': record.identity.artifact_type,
            'revision': artifact['revision'], 'source_sha256': sha256(record.source_bytes).hexdigest(),
            'record_sha256': canonical_json_sha256(artifact), 'cells': cells}

    def project(start, name):
        # Definition cycles are rejected by the planner. Evaluate the remaining
        # DAG iteratively, including shared children, without Python recursion.
        pending = [(start, name, None)]
        while pending:
            current, selected, targets = pending.pop()
            key = current, selected
            if key in projected_values:
                continue
            projection = projections[selected]
            if targets is None:
                targets = related(current, projection)
                if projection['aggregation'] != 'records':
                    projected_values[key] = (len(targets) if projection['aggregation'] == 'count' else targets)
                    continue
                pending.append((current, selected, targets))
                dependencies = [selector for kind, selector, _, _, _ in projection_columns[selected]
                                if kind == 'relation_projection']
                pending.extend((target, dependency, None)
                               for target in reversed(targets) for dependency in reversed(dependencies))
            else:
                projected_values[key] = [bound_row(target, projection_columns[selected]) for target in targets]
        return projected_values[start, name]

    rows = []
    for item in page.data['items']:
        projected = {name: project(item['id'], name) for name in projections}
        rows.append({**bound_row(item['id'], columns), 'relation_projections': projected})

    return rows
