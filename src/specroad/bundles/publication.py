"""Publish a generated project or partial ZIP from a retained native observation."""
import os
import secrets

from ..changes._lock_files import LockFiles
from ..changes._publication_io import replace_bound_image
from ..changes._staging_files import _write_new
from ..cli.command_errors import CommandUsageError
from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..diagnostics import Diagnostic
from ..documents._export_targets import _check_external, _output_boundary, _target_path
from ..graph.scope_descriptors import ScopeDescriptor
from ..model._bundle_scope_contract import PARTIAL, PROJECT
from ..model.errors import ModelError
from ..query._read_errors import read_details, read_failure
from ..query.read_work import complete_read_steps
from ..security import SafetyViolation
from ..security import paths as guards
from ..srx.errors import SrxError
from .errors import BundleError
from .partial import _prepare_partial
from .project import _prepare


_PROJECT_SCOPE = object()


def _publish(container, source, verify_current, output, output_root):
    if output_root is None and (not isinstance(output, str)
            or not output.startswith(source.configuration.generated_path + '/')):
        raise BundleError('bundle_output_target_forbidden', code='SRV083', exit_code=7)
    try:
        path, parts = _target_path(output, source, output_root)
        boundary = _output_boundary(output_root, source)
    except ModelError as error:
        if error.reason in ('unsafe_path', 'reserved_path'):
            raise BundleError('unsafe_bundle_output_path', code='SRV083', exit_code=7) from error
        raise

    def check_location():
        verify_current()
        boundary._check_root()
        if output_root is not None:
            _check_external(boundary, source)

    check_location()
    # The directory-inode mutex and native image writer create no SpecRoad
    # writer lock, journal or receipt. Noncooperating writers are not sandboxed.
    with LockFiles(boundary.root) as files:
        if files.boundary._root_identity != boundary._root_identity:
            raise BundleError('bundle_output_root_changed', code=None, exit_code=6)
        files.acquire()

        def check_namespace():
            for index, name in enumerate(parts):
                with files.directory(parts[:index]) as parent:
                    if parent is None:
                        return
                    if any(n != name and n.casefold() == name.casefold() for n in os.listdir(parent)):
                        raise BundleError('bundle_output_name_collision', code='SRV083', exit_code=7)
                    if index == len(parts) - 1:
                        try:
                            os.stat(name, dir_fd=parent, follow_symlinks=False)
                        except FileNotFoundError:
                            return
                        raise BundleError('bundle_output_exists', code=None, exit_code=6)

        check_namespace()
        check_location()
        with files.directory(parts[:-1], create=True) as parent:
            directory_identity = guards._identity(os.fstat(parent))

            def check_target():
                check_location()
                check_namespace()
                with files.directory(parts[:-1]) as current:
                    if current is None or guards._identity(os.fstat(current)) != directory_identity:
                        raise BundleError('bundle_output_directory_changed', code=None, exit_code=6)

            check_target()
            pending = '.specroad-bundle-' + secrets.token_hex(16) + '.tmp'
            image_identity = _write_new(parent, pending, container.source_bytes)
            try:
                replace_bound_image(parent, pending, parent, parts[-1],
                    size=len(container.source_bytes), digest=container.sha256, identity=image_identity,
                    create_only=True, before_replace=check_target,
                    source_changed=lambda: BundleError('bundle_output_image_changed', code=None, exit_code=6))
            except FileExistsError as error:
                raise BundleError('bundle_output_exists', code=None, exit_code=6) from error
        check_location()
        if boundary.read_bytes(path) != container.source_bytes:
            raise BundleError('bundle_published_bytes_changed', code=None, exit_code=6)
        check_location()
    # The ZIP hash stays outside its manifest. Publication is neither a verifier
    # for arbitrary input bundles nor extraction, approval or write admission.
    return {'format_version': 'bundle-create-v1', 'manifest': container.manifest,
            'file': {'path': path, 'size': len(container.source_bytes), 'sha256': container.sha256},
            'generated': True, 'normative': False, 'atomic_snapshot': False,
            'source_bytes_rechecked': True, 'full_semantic_validation': False,
            'approval_granted': False, 'write_authorized': False}


def _steps(root, *, output, output_root=None, descriptor=_PROJECT_SCOPE, exclude_operational_receipts=False):
    project = None
    try:
        container, source, verify_current = (_prepare(root, exclude_operational_receipts=exclude_operational_receipts)
                                            if descriptor is _PROJECT_SCOPE
                                            else _prepare_partial(root, descriptor))
        project = {'project_root': str(source.boundary.root), 'project_id': source.configuration.project_id}
        yield 'evaluated'
        result = _publish(container, source, verify_current, output, output_root)
        validate_result_document('bundle-create-v1', result)
        return CommandResult('bundle.create', result=result, project=project, details=read_details())
    except BundleError as error:
        kind = FailureKind(error.exit_code)
        diagnostic = Diagnostic(error.code or 'CORE_' + kind.name, 'error', 'bundle',
                                'Bundle creation failed.', rationale=error.reason)
        return CommandResult.failed('bundle.create', kind, project=project, diagnostics=(diagnostic,),
                                    details={**read_details(), 'bundle_failure': error.as_dict()})
    except (OperationFailure, ModelError, SafetyViolation, SrxError, OSError) as error:
        return read_failure('bundle.create', error, project, read_details())


def create_project_bundle(root, *, output, output_root=None, exclude_operational_receipts=False):
    """Generate one ZIP under generated/ or an explicit separate output root.

    Existing targets are never replaced. Failed publication retains its actual
    complete/private images; it never reports success or deletes others' files.
    Explicit receipt exclusion is reflected in the local_only manifest.
    """
    return complete_read_steps(_steps(root, output=output, output_root=output_root,
                                     exclude_operational_receipts=exclude_operational_receipts))


def create_command(invocation):
    options = invocation.options
    if '--scope' not in options or '--output' not in options:
        raise CommandUsageError('Bundle creation requires scope and output')
    kind, selector = options['--scope'], {}
    for scope in PARTIAL.scope_kinds:
        flag = '--' + scope
        if kind == scope:
            if flag not in options:
                raise CommandUsageError('Selected bundle scope requires its selector')
            selector = {scope + '_id': options[flag]}
        elif flag in options:
            raise CommandUsageError('Bundle selector does not match scope')
    if kind in PROJECT.scope_kinds and '--configuration' in options:
        raise CommandUsageError('A full project bundle cannot be configuration filtered')
    descriptor = _PROJECT_SCOPE
    if kind not in PROJECT.scope_kinds:
        try:
            descriptor = ScopeDescriptor({'scope_version': 'scope-v1', 'scope_kind': kind,
                'selector': selector, 'configuration_id': options.get('--configuration'),
                'closure_profile': 'core-closure-v1', 'boundary_policy': PARTIAL.boundary_policy})
        except ModelError as error:
            return read_failure('bundle.create', error, None, read_details())
    return complete_read_steps(_steps(invocation.resolved.project_root,
        output=options['--output'], output_root=options.get('--output-root'), descriptor=descriptor,
        exclude_operational_receipts=options.get('--exclude-operational-receipts', False)),
        call=invocation.consumption_call)


def create_partial_bundle(root, descriptor, *, output, output_root=None):
    """Publish the selected read-only document/release through the native guard.

    Configuration context is transported without extending the selected scope.
    Publication uses the same create-only and freshness rules as project bundles.
    """
    return complete_read_steps(_steps(root, output=output, output_root=output_root,
                                     descriptor=descriptor))
