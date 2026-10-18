"""Versioned, non-normative exports of the native selected view columns.

JSON retains typed cells, including missing and nested values. CSV admits them
only with an explicit per-column typed JSON declaration. Neither adapter evaluates a second
query, reads project paths, imports values, or authorizes a normative write.
"""
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from .views import resolve_view
from ._export_data import csv_view_bytes, view_export_data, view_export_schema


class ViewExportError(ModelError):
    def __init__(self, reason, *, path=None, pointer='', exit_code=3):
        super().__init__(reason, path=path, pointer=pointer)
        self.exit_code = exit_code


def export_view(model, view_id, *, output_format='json', configuration_id=None):
    """Return owned UTF-8 data bytes; presentation rendering remains separate.

CSV uses RFC-4180 records of equal width: a header, one metadata record, then
data records. The metadata includes column types and ordered row bindings.
Only selected cells are exported; unselected fields, groups and auxiliary
projections are outside this explicitly declared export scope.
"""
    from ..changes.target_model import TargetModel
    if type(output_format) is not str or output_format not in ('json', 'csv'):
        raise ViewExportError('view_export_format_not_supported', pointer='/output_format')
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    model = model.snapshot()
    data = resolve_view(model, view_id, configuration_id=configuration_id).data
    if output_format not in data['formats']:
        raise ViewExportError('view_export_format_not_declared',
                              path=data['view']['path'], pointer='/formats')
    exported = view_export_data(model, view_id, data)
    if output_format == 'json':
        return canonical_json_bytes(exported)
    return csv_view_bytes(exported, source_path=data['view']['path'], error_type=ViewExportError)
