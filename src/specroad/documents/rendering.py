"""Read-only document/view presentation over the native owned data services.

These APIs return UTF-8 bytes. They neither discover inputs nor write outputs,
execute templates, determine approval, or replace the CLI's later providers.
"""
from .._metadata import __version__, MODEL_SCHEMA_VERSION
from ..model.errors import ModelError
from .blocks import ContentBlock
from .includes import compose_document
from .prose import parse_prose
from .references import resolve_artifact_reference
from .tables import resolve_table_block
from .views import resolve_view
from ._render_formats import Emitter


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


def render_document(model, document_id, *, output_format='markdown'):
    """Render validated composition, preserving repeated includes and data errors.

    Attachments require an explicit safe embedding provider and are rejected in
    this first slice. Nonempty document render policies likewise need a provider;
    neither declaration is silently ignored or used to read a filesystem path.
    """
    model = _snapshot(model, output_format)
    composed = compose_document(model, document_id)
    data = composed.data
    sources = composed.source_files
    nodes = []
    linked = {}
    shown = set(data['records'])
    for occurrence in data['occurrences']:
        identifier = occurrence['artifact_id']
        bound = data['records'][identifier]
        record = bound['record']
        level = min(occurrence['depth'] + 1, 6)
        if occurrence['artifact_type'] in ('document', 'section'):
            if record.get('render_policy'):
                raise RenderError('render_policy_provider_required', path=bound['path'], pointer='/render_policy')
            nodes.append({'type': 'heading', 'id': identifier, 'title': record['title'], 'level': level})
            continue
        block = ContentBlock(sources[bound['path']], path=bound['path'])
        kind = block.block_kind
        if kind in ('prose', 'admonition'):
            content = parse_prose(block).data['content']
            pending = [content]
            while pending:
                node = pending.pop()
                if node['type'] in ('link', 'image'):
                    raise RenderError('render_attachment_provider_required', path=bound['path'], pointer='/payload/markdown')
                pending.extend(node.get('children', ()))
            nodes.append({'type': 'prose', 'id': identifier, 'content': content})
        elif kind in ('query', 'table'):
            nodes.append({'type': 'table', 'id': identifier, 'data': resolve_table_block(model, identifier).data})
        elif kind == 'artifact_ref':
            reference = resolve_artifact_reference(model, identifier).data
            target = reference['target']['record']
            nodes.append({'type': 'anchor', 'id': identifier})
            nodes.append({'type': 'record', 'record': target, 'mode': reference['render_mode'], 'level': level})
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
            nodes.append({'type': 'record', 'record': target, 'mode': 'summary', 'level': 2})
    metadata = {**_metadata(model, data), 'document_id': document_id,
                'document_revision': data['document_revision']}
    return Emitter(output_format).output(metadata, data['records'][document_id]['record']['title'], nodes)


def render_view(model, view_id, *, output_format='markdown', configuration_id=None):
    """Render the exact selected columns, rows and groups without new query rules."""
    model = _snapshot(model, output_format)
    resolved = resolve_view(model, view_id, configuration_id=configuration_id)
    data = resolved.data
    if output_format not in data['formats']:
        raise RenderError('render_view_format_not_declared', path=data['view']['path'], pointer='/formats')
    from ..storage.json_syntax import parse_json_object
    title = parse_json_object(resolved.view_source_bytes)['title']
    metadata = {**_metadata(model, data), 'view_id': view_id,
                'view_revision': data['view']['revision']}
    nodes = [{'type': 'heading', 'id': view_id, 'title': title, 'level': 1},
             {'type': 'table', 'id': view_id, 'data': data}]
    return Emitter(output_format).output(metadata, title, nodes)
