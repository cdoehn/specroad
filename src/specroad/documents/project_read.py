"""Fresh project/partial adapters for the existing pure document readers."""
from hashlib import sha256

from ..bundles.errors import BundleError
from ..cli.results import CommandResult, OperationFailure, FailureKind
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..srx.errors import SrxError
from ..query._read_errors import read_details, read_failure
from ..query.read_work import complete_read_steps
from ..bundles._partial_read import partial_read_snapshot
from ..bundles._read_context import PartialReadContext
from ._read_model import PartialDocumentModel


def document_read_steps(root, operation, identifier=None, **options):
    details = read_details()
    try:
        if operation == 'render' and ((identifier is None) == (options.get('view') is None)):
            raise OperationFailure(FailureKind.USAGE, 'Render requires either a document ID or a built-in view.')
        partial = partial_read_snapshot(root)
        if partial is None:
            from ..authoring._inspection_snapshot import InspectionSnapshot
            from ..runtime.preflight import require_project_read_preflight
            from ..storage.preflight_metadata import MetadataPhases
            snapshot = InspectionSnapshot(root, None)
            require_project_read_preflight(snapshot.source.boundary,
                snapshot.source.configuration_bytes, MetadataPhases())
            model = snapshot.model
        else:
            snapshot, model = partial, PartialDocumentModel(partial)
        yield 'loaded'
        content = None
        if operation == 'render':
            from .includes import compose_document
            from .rendering import render_document
            from .builtin_views import resolve_builtin_view, render_builtin_view
            view = options.pop('view', None)
            if view is None:
                data = compose_document(model, identifier).data
                content = render_document(model, identifier, **options)
            else:
                data = resolve_builtin_view(model, view).data
                content = render_builtin_view(model, view, **options)
        elif operation == 'view.render':
            from .views import resolve_view
            from .rendering import render_view
            data = resolve_view(model, identifier, configuration_id=options.get('configuration_id')).data
            content = render_view(model, identifier, **options)
        elif operation == 'diagram':
            from .diagrams import resolve_diagram, render_diagram
            output_format = options.pop('output_format', None)
            data = resolve_diagram(model, identifier, **options).data
            if output_format is not None:
                content = render_diagram(model, identifier, output_format=output_format, **options)
        else:
            raise ModelError('document_read_operation_invalid')
        payload = {'format_version': 'document-read-v1', 'operation': operation, 'data': data,
            'rendered': None if content is None else {'utf8': content.decode('utf-8'),
                'size': len(content), 'sha256': sha256(content).hexdigest()},
            'generated': True, 'normative': False, 'write_authorized': False,
            'approval_granted': False, 'full_semantic_validation': False}
        yield 'evaluated'
        snapshot.verify_current()
        if partial is not None:
            return PartialReadContext(partial).finish(operation, 'document-read-v1', payload, details)
        require_project_read_preflight(snapshot.source.boundary,
            snapshot.source.configuration_bytes, MetadataPhases())
        from ..cli.result_schemas import validate_result_document
        validate_result_document('document-read-v1', payload)
        return CommandResult(operation, result=payload, details=details,
            project={'project_root': str(snapshot.source.boundary.root),
                     'project_id': model.configuration.project_id})
    except (BundleError, OperationFailure, ModelError, SafetyViolation, SrxError, OSError) as error:
        return read_failure(operation, error, None, details)


def read_document_project(root, operation, identifier=None, **options):
    return complete_read_steps(document_read_steps(root, operation, identifier, **options))


def document_read_command(invocation):
    command = invocation.command.command_id
    options = invocation.options
    if command == 'diagram':
        values = {}
        for name in ('max-depth', 'max-nodes', 'max-edges'):
            raw = options['--' + name]
            if not raw or any(c not in '0123456789' for c in raw):
                from ..cli.command_errors import CommandUsageError
                raise CommandUsageError('Diagram limits require nonnegative decimal integers')
            try:
                values[name.replace('-', '_')] = int(raw)
            except ValueError as error:
                from ..cli.command_errors import CommandUsageError
                raise CommandUsageError('Diagram limit is not a supported integer') from error
        values.update(start_id=invocation.arguments['id'], direction=options['--direction'],
                      output_format=options.get('--output-format'))
        identifier = invocation.arguments['kind']
    else:
        identifier = invocation.arguments.get('id')
        values = {'output_format': options.get('--output-format', 'markdown')}
        if command == 'render':
            values['view'] = options.get('--view')
        else:
            values['configuration_id'] = options.get('--configuration')
    return complete_read_steps(document_read_steps(invocation.resolved.project_root,
        command, identifier, **values), call=invocation.consumption_call)
