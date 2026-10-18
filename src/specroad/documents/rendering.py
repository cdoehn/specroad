"""Read-only document/view presentation over the native owned data services.

These APIs return UTF-8 bytes. They neither discover inputs nor write outputs,
execute templates, determine approval, or replace the CLI's later providers.
"""
from .._metadata import __version__, MODEL_SCHEMA_VERSION
from ..model.errors import ModelError
from ..model.content_language import ContentLanguage
from .blocks import ContentBlock
from .includes import compose_document
from .prose import parse_prose
from .references import resolve_artifact_reference
from .table_presentation import resolve_table_presentation, resolve_view_presentation
from ._render_formats import Emitter
from ._render_assets import resolve_render_attachment
from .requirement_presentation import resolve_requirement_presentation


class RenderError(ModelError):
    exit_code = 3


def _snapshot(model, output_format):
    from ..changes.target_model import TargetModel
    if type(output_format) is not str or output_format not in ('markdown', 'html'):
        raise RenderError('render_format_not_supported', pointer='/output_format')
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    return model.snapshot()


def _metadata(model, data):
    return {'model_root_sha256': data['model_root_sha256'],
            'tool_version': __version__, 'schema_version': MODEL_SCHEMA_VERSION,
            'profiles': list(model.profile.profile_chain), 'project_id': data['project_id']}


def _render_policy(policy, output_format, path):
    if not policy:
        return
    if set(policy) != {'formats'}:
        raise RenderError('render_policy_provider_required', path=path, pointer='/render_policy')
    formats = policy['formats']
    if (type(formats) is not list or not formats
            or any(type(item) is not str or item not in ('markdown', 'html') for item in formats)
            or len(set(formats)) != len(formats)):
        raise RenderError('render_policy_formats_invalid', path=path, pointer='/render_policy/formats')
    if output_format not in formats:
        raise RenderError('render_document_format_not_declared', path=path, pointer='/render_policy/formats')


def render_document(model, document_id, *, output_format='markdown'):
    """Render validated composition, preserving repeated includes and data errors.

    Raster attachments are embedded only from exact declared resource bytes.
    Other media and executable render policies remain unsupported. Neither
    declaration is silently ignored or used to read a filesystem path.
    """
    model = _snapshot(model, output_format)
    composed = compose_document(model, document_id)
    data = composed.data
    sources = composed.source_files
    nodes = []
    linked = {}
    assets = {}
    presentations = {}
    def record_node(target, mode, level):
        node = {'type': 'record', 'record': target, 'mode': mode, 'level': level,
                'content_language': ContentLanguage(target.get('language'),
                    target.get('text_direction', 'auto')).as_dict()}
        if target['artifact_type'] == 'requirement':
            if target['id'] not in presentations:
                presentations[target['id']] = resolve_requirement_presentation(model, target['id'])
            node['presentation'] = presentations[target['id']].data
        return node
    shown = set(data['records'])
    for occurrence in data['occurrences']:
        identifier = occurrence['artifact_id']
        bound = data['records'][identifier]
        record = bound['record']
        level = min(occurrence['depth'] + 1, 6)
        if occurrence['artifact_type'] in ('document', 'section'):
            _render_policy(record.get('render_policy', {}), output_format, bound['path'])
            nodes.append({'type': 'heading', 'id': identifier, 'title': record['title'], 'level': level,
                'content_language': ContentLanguage(record.get('language'),
                    record.get('text_direction', 'auto')).as_dict()})
            continue
        block = ContentBlock(sources[bound['path']], path=bound['path'])
        kind = block.block_kind
        if kind in ('prose', 'admonition'):
            content = parse_prose(block).data['content']
            pending = [content]
            while pending:
                node = pending.pop()
                if node['type'] in ('link', 'image'):
                    path = node['attachment_path']
                    if path not in assets:
                        assets[path] = resolve_render_attachment(model, path, source_path=bound['path'], error_type=RenderError)
                    node['attachment'] = assets[path]
                pending.extend(node.get('children', ()))
            nodes.append({'type': 'prose', 'id': identifier, 'content': content,
                'content_language': ContentLanguage(record.get('language'),
                    record.get('text_direction', 'auto')).as_dict()})
        elif kind in ('query', 'table'):
            presentation = resolve_table_presentation(model, identifier).data
            nodes.append({'type': 'table', 'id': identifier, 'data': presentation['projection'],
                          'presentation': presentation})
        elif kind == 'artifact_ref':
            reference = resolve_artifact_reference(model, identifier).data
            target = reference['target']['record']
            nodes.append({'type': 'anchor', 'id': identifier})
            nodes.append(record_node(target, reference['render_mode'], level))
            if reference['render_mode'] == 'link':
                linked[target['id']] = target
            else:
                shown.add(target['id'])
        elif kind == 'page_break':
            nodes.append({'type': 'page_break', 'id': identifier})
        elif kind == 'include_document':
            # The native occurrence sequence already contains every expansion.
            nodes.append({'type': 'anchor', 'id': identifier})
        else:
            raise RenderError('render_block_provider_required', path=bound['path'], pointer='/block_kind')
    # Local link targets outside the composed tree get an actual source summary.
    for target in sorted(linked.values(), key=lambda r: (r['artifact_type'], r['id'])):
        if target['id'] not in shown:
            nodes.append(record_node(target, 'summary', 2))
    metadata = {**_metadata(model, data), 'document_id': document_id,
                'document_revision': data['document_revision']}
    return Emitter(output_format).output(metadata, data['records'][document_id]['record']['title'], nodes)


def render_view(model, view_id, *, output_format='markdown', configuration_id=None):
    """Render the exact selected columns, rows and groups without new query rules."""
    model = _snapshot(model, output_format)
    resolved = resolve_view_presentation(model, view_id, configuration_id=configuration_id)
    presentation = resolved.data
    data = presentation['projection']
    if output_format not in data['formats']:
        raise RenderError('render_view_format_not_declared', path=data['view']['path'], pointer='/formats')
    from ..storage.json_syntax import parse_json_object
    value = parse_json_object(resolved.source_bytes)
    title = value['title']
    metadata = {**_metadata(model, data), 'view_id': view_id,
                'view_revision': data['view']['revision']}
    nodes = [{'type': 'heading', 'id': view_id, 'title': title, 'level': 1,
              'content_language': ContentLanguage(value.get('language'), value.get('text_direction', 'auto')).as_dict()},
             {'type': 'table', 'id': view_id, 'data': data, 'presentation': presentation}]
    return Emitter(output_format).output(metadata, title, nodes)
