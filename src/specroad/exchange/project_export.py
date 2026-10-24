"""Live export and checked generated-file publication, without normative writes."""
from hashlib import sha256
from pathlib import Path
import os
import secrets

from ..authoring._inspection_snapshot import InspectionSnapshot
from ..changes._lock_files import LockFiles
from ..changes._publication_io import replace_bound_image
from ..changes._staging_files import _write_new
from ..cli.command_errors import CommandUsageError
from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, OperationFailure
from ..documents._export_targets import _check_external, _output_boundary, _target_path
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.errors import ModelError
from ..query._read_errors import read_failure, read_details
from ..query.read_work import complete_read_steps
from ..query.show import _preflight
from ..security import ProjectBoundary, SafetyViolation
from ..security import paths as guards
from ..srx.errors import SrxError
from ..storage.json_syntax import parse_json_object
from ..storage.project import ProjectSource
from .exporting import ExportError, prepare_export


def _publish(snapshot, prepared, path, output_root, input_bindings=()):
    source = snapshot.source
    path, _ = _target_path(path, source, output_root)
    boundary = _output_boundary(output_root, source)
    directory = path.rpartition('/')[0]
    prefix = directory + '/' if directory else ''
    manifest_path = path + '.manifest.json'
    files_to_write = [(prefix + p, raw) for p, raw in prepared.attachment_files]
    files_to_write.extend(((path, prepared.output_bytes), (manifest_path, prepared.manifest_bytes)))
    folded = {p.casefold() for p, _ in files_to_write}
    if len(folded) != len(files_to_write) or any(
            '/'.join(parts[:index]) in folded
            for p in folded for parts in (p.split('/'),) for index in range(1, len(parts))):
        raise ExportError('export_output_collision', exit_code=6)
    targets = [(p, _target_path(p, source, output_root)[1], raw) for p, raw in files_to_write]

    def check_location():
        snapshot.verify_current()
        for input_boundary, name, raw in input_bindings:
            if input_boundary.read_bytes(name) != raw:
                raise ExportError('export_input_changed', exit_code=6)
        _preflight(source)
        boundary._check_root()
        if output_root is not None:
            _check_external(boundary, source)

    check_location()
    publications = []
    # The shared directory-inode mutex and native atomic image writer need no
    # lock file, operational journal, receipt or normative transaction.
    with LockFiles(boundary.root) as files:
        if files.boundary._root_identity != boundary._root_identity:
            raise ExportError('export_directory_changed', exit_code=6)
        files.acquire()
        for p, parts, _ in targets:
            with files.directory(parts[:-1]) as parent:
                if parent is not None:
                    try:
                        os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                    except FileNotFoundError:
                        continue
                    raise ExportError('export_target_exists', path=p, exit_code=6)
        # Publish the manifest last. Failure preserves any complete images and
        # private remnants; a partial set is never returned as a success.
        for p, parts, raw in targets:
            check_location()
            with files.directory(parts[:-1], create=True) as parent:
                identity = guards._identity(os.fstat(parent))

                def check_target():
                    check_location()
                    with files.directory(parts[:-1]) as fresh:
                        if fresh is None or guards._identity(os.fstat(fresh)) != identity:
                            raise ExportError('export_directory_changed', path=p, exit_code=6)
                    try:
                        os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                    except FileNotFoundError:
                        return
                    raise ExportError('export_target_exists', path=p, exit_code=6)

                check_target()
                pending = '.exchange-export-' + secrets.token_hex(16) + '.tmp'
                image_identity = _write_new(parent, pending, raw)
                digest = sha256(raw).hexdigest()
                try:
                    replace_bound_image(parent, pending, parent, parts[-1], size=len(raw), digest=digest,
                        identity=image_identity, create_only=True, before_replace=check_target,
                        source_changed=lambda: ExportError('export_output_image_changed', exit_code=6))
                except FileExistsError as error:
                    raise ExportError('export_target_exists', path=p, exit_code=6) from error
                publications.append({'path': p, 'size': len(raw), 'sha256': digest})
        check_location()
        for p, _, raw in targets:
            if boundary.read_bytes(p) != raw:
                raise ExportError('export_published_bytes_changed', path=p, exit_code=6)
        check_location()
    return {'format_version': 'exchange-export-publication-v1', 'manifest': prepared.manifest,
            'files': publications, 'manifest_path': manifest_path, 'generated': True, 'normative': False,
            'atomic_snapshot': False, 'source_bytes_rechecked': True, 'approval_granted': False}


def _steps(root, descriptor, *, output, output_root=None, profiles=None, input_bindings=(), **options):
    project = None
    try:
        source = ProjectSource(root)
        _preflight(source)
        project = {'project_root': str(source.boundary.root), 'project_id': source.configuration.project_id}
        snapshot = InspectionSnapshot(root, profiles, include_archive_objects=True)
        yield 'loaded'
        prepared = prepare_export(snapshot.model, descriptor, **options)
        yield 'evaluated'
        result = _publish(snapshot, prepared, output, output_root, input_bindings)
        validate_result_document('exchange-export-v1', result)
        return CommandResult('export', result=result, project=project, details=read_details())
    except (OperationFailure, ModelError, SafetyViolation, SrxError, OSError) as error:
        details = read_details()
        if isinstance(error, ExportError) and error.manifest is not None:
            details['unpublished_export_manifest'] = parse_json_object(error.manifest)
        return read_failure('export', error, project, details)


def export_project(root, descriptor, **options):
    return complete_read_steps(_steps(root, descriptor, **options))


def export_command(invocation):
    try:
        return _export_command(invocation)
    except (ModelError, SafetyViolation, SrxError, OSError) as error:
        return read_failure('export', error, None, read_details())


def _export_command(invocation):
    from .reqif import ReqIFLimits
    options = invocation.options
    required = ('--scope', '--output', '--mapping', '--mapping-sha256')
    if any(key not in options for key in required):
        raise CommandUsageError('Export requires scope, output and an exact mapping/hash binding')
    bindings = []

    def read_json(filename):
        path = Path(filename)
        if not path.is_absolute():
            path = (invocation.resolved.working_directory or Path.cwd()) / path
        boundary = ProjectBoundary(path.parent)
        raw = boundary.read_bytes(path.name)
        bindings.append((boundary, path.name, raw))
        return parse_json_object(raw)

    kind, selector = options['--scope'], {}
    for scope, flag in (('document', '--document'), ('release', '--release'), ('query', '--query')):
        if kind == scope:
            if flag not in options:
                raise CommandUsageError('Selected export scope requires its selector')
            selector = {'query': read_json(options[flag])} if scope == 'query' else {scope + '_id': options[flag]}
        elif flag in options:
            raise CommandUsageError('Export selector does not match scope')
    descriptor = ScopeDescriptor({'scope_version': 'scope-v1', 'scope_kind': kind, 'selector': selector,
        'configuration_id': options.get('--configuration'), 'closure_profile': 'core-closure-v1',
        'boundary_policy': options.get('--boundary-policy', 'closed')})
    fmt = invocation.arguments['exchange_format']
    limits = None
    if fmt in ('reqif', 'reqifz'):
        if '--xml-limits' not in options:
            raise CommandUsageError('ReqIF requires explicit XML safety limits')
        value = read_json(options['--xml-limits'])
        from dataclasses import fields
        if set(value) != {field.name for field in fields(ReqIFLimits)}:
            raise CommandUsageError('ReqIF XML limits must supply every defined bound')
        limits = ReqIFLimits(**value)
    elif '--xml-limits' in options or '--max-archive-bytes' in options:
        raise CommandUsageError('XML/archive limits require a ReqIF format')
    maximum = options.get('--max-archive-bytes')
    if maximum is not None:
        from ..query.project_query import _number
        maximum = _number(maximum)
    if fmt == 'reqifz' and maximum is None:
        raise CommandUsageError('ReqIFZ requires its explicit uncompressed-byte safety bound')
    return complete_read_steps(_steps(invocation.resolved.project_root, descriptor,
        output=options['--output'], output_root=options.get('--output-root'),
        profiles=options.get('--profile'), input_bindings=bindings,
        output_format=fmt, mapping_key=options['--mapping'], expected_mapping_sha256=options['--mapping-sha256'],
        csv_profile_key=options.get('--csv-profile'), expected_csv_profile_sha256=options.get('--csv-profile-sha256'),
        include_attachments=options.get('--include-attachments', False), fail_on_loss=options.get('--fail-on-loss', False),
        reqif_limits=limits, max_archive_bytes=maximum), call=invocation.consumption_call)
