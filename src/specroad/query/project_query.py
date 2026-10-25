"""Live Query with an exact page, explicit SRX files and final source checks."""
from pathlib import Path

from ..cli.command_errors import CommandUsageError
from ..cli.result_schemas import validate_result_document
from ..bundles.errors import BundleError
from ..srx.errors import SrxError
from ..cli.results import CommandResult, OperationFailure
from ..model.errors import ModelError
from ..security import ProjectBoundary, SafetyViolation
from ..srx.errors import SrxError
from ..storage._relation_snapshot import _capture_sources
from ..storage.json_syntax import parse_json_object
from ..storage.project import ProjectSource
from ._read_errors import read_details, read_failure
from .paging import query_records
from .read_work import complete_read_command, complete_read_steps
from .selection import NormalizedQuery
from .show import _preflight, _verify_current

FILTER_FLAGS = ('type', 'maturity', 'implementation-status', 'verification-plan-status',
                'verification-result', 'owner', 'tag', 'release', 'has-relation',
                'missing-relation', 'full-text')


def _number(value):
    if type(value) is not str or not value or any(c not in '0123456789' for c in value):
        raise CommandUsageError('Query pagination requires a nonnegative decimal integer')
    try:
        return int(value)
    except ValueError as error:
        raise CommandUsageError('Query pagination is not a supported integer') from error


def _normalized(source, options, cwd):
    if '--evaluation' in options:
        raise ModelError('query_evaluation_provider_required')
    bindings, expressions = [], []
    for filename in options.get('--filter', ()):
        path = Path(filename)
        if not path.is_absolute():
            path = (Path.cwd() if cwd is None else Path(cwd)) / path
        boundary = ProjectBoundary(path.parent)
        raw = boundary.read_bytes(path.name)
        expressions.append(parse_json_object(raw, path=str(path)))
        bindings.append((boundary, path.name, raw))
    default = source.configuration.data.get('resource_limits', {}).get('query_default_limit', 100)
    query = NormalizedQuery(
        filters={name.replace('-', '_'): list(options['--' + name])
                 for name in FILTER_FLAGS if '--' + name in options},
        srx_filters=expressions, select=options.get('--select', ()), sort=options.get('--sort', ()),
        offset=_number(options.get('--offset', '0')),
        limit=_number(options['--limit']) if '--limit' in options else None, default_limit=default)
    return query, bindings


def _query_steps(root, query=None, *, options=None, cwd=None, configuration_id=None):
    project = None
    details = read_details()
    try:
        if query is not None and type(query) is not NormalizedQuery:
            raise ModelError('normalized_query_required')
        if query is not None and options is not None:
            raise CommandUsageError('An explicit query cannot also use CLI query options')
        if options is not None and '--configuration' in options:
            if configuration_id is not None:
                raise CommandUsageError('Duplicate configuration selection')
            configuration_id = options['--configuration']
        from ..bundles._partial_read import partial_read_snapshot
        partial = partial_read_snapshot(root)
        if partial is not None:
            from ._partial_commands import query_steps
            return (yield from query_steps(partial, query, options=options, cwd=cwd,
                configuration_id=configuration_id, details=details))
        source = ProjectSource(root)
        project = {'project_root': str(source.boundary.root), 'project_id': source.configuration.project_id}
        _preflight(source)
        snapshot = _capture_sources(source)
        bindings = []
        if query is None:
            query, bindings = _normalized(source, {} if options is None else options, cwd)
        yield 'loaded'
        page = query_records(snapshot.records, query, project=source.configuration.data,
                             configuration_id=configuration_id)
        payload = page.data
        details.update(query_sha256=page.query_sha256, inputs_sha256=page.inputs_sha256,
            source_count=page.source_count, observation_sha256=snapshot.binding.sha256,
            validation_scope=page.validation_scope, profile_defaults_applied=False)
        if page.configuration_binding is not None:
            from ..configurations import resolve_configuration
            details['selected_configuration'] = page.configuration_binding
            details['configuration_scope_sha256'] = resolve_configuration(
                snapshot.records, configuration_id).scope_sha256(source.configuration)
        yield 'evaluated'
        for boundary, name, raw in bindings:
            if boundary.read_bytes(name) != raw:
                raise ModelError('query_input_changed', path=name)
        _preflight(source)
        _verify_current(source, snapshot.binding)
        validate_result_document('artifact-query-v1', payload)
        return CommandResult('query', result=payload, project=project, details=details)
    except (BundleError, OperationFailure, ModelError, SrxError, SafetyViolation, OSError) as error:
        return read_failure('query', error, project, details)


def query_project(root, query=None, *, configuration_id=None):
    """Return the exact native Query page over the complete current inventory."""
    return complete_read_steps(_query_steps(root, query, configuration_id=configuration_id))


def query_command(invocation):
    return complete_read_command(invocation, _query_steps, options=invocation.options,
                                 cwd=invocation.resolved.working_directory)
