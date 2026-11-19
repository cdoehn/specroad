"""Native scope and snapshot adapter; no alternate traversal or authority."""
from ..bundles._partial_read import partial_read_snapshot
from ..query.selection import NormalizedQuery, select_query
from ..query.show import _preflight, _verify_current
from ..storage.project import ProjectSource
from ..storage._relation_snapshot import _capture_sources
from ._values import require


def _observe(root):
    partial = partial_read_snapshot(root)
    if partial is not None:
        return partial, partial, partial.records
    source = ProjectSource(root)
    _preflight(source)
    snapshot = _capture_sources(source)
    return source, snapshot, snapshot.records

def _finish(source, snapshot):
    if source is snapshot:
        source.verify_current()
    else:
        _preflight(source)
        _verify_current(source, snapshot.binding)

def _selected(source, snapshot, records, subject_ids, configuration_id):
    selected = select_query(records, NormalizedQuery(
        filters={'type':['requirement']} if subject_ids is None else {}),
        project=source.configuration.data, configuration_id=configuration_id,
        partial=source if source is snapshot else None)
    wanted = set(selected.artifact_ids) if subject_ids is None else set(subject_ids)
    require(wanted <= set(selected.artifact_ids), 'analyzer_subject_outside_scope')
    require(bool(wanted), 'analyzer_empty_selection')
    return sorted((r for r in records if r.identity.id in wanted), key=lambda r:r.identity.id)
