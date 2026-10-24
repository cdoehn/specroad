"""Prepare document/release bytes from a retained, complete origin observation.

This first partial provider is unconfigured and read-only. Publication,
configuration selection and independent verification are separate steps; the
returned container never grants extraction, authenticity or write authority.
"""
from .. import __version__
from ..cli.results import OperationFailure
from ..exchange._export_scope import export_scope, resource_identity
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.errors import ModelError
from ..model.language_package_values import LanguagePackage
from ..model.manifest_resources import project_json_resource
from ..model.paths import PathClass, artifact_path
from ..security import SafetyViolation
from ..srx.errors import SrxError
from ._project_snapshot import ProjectBundleSnapshot
from .container import BundleContainer, encode_bundle
from .errors import BundleError
from .manifest import require


def _selected_payloads(origin, closure, artifacts):
    model = origin.model
    paths = {'specroad.json'}
    paths.update(artifact_path(a['artifact_type'], a['id'], model.configuration.id_prefix)
                 for a in artifacts)
    by_path = {r.data['path']: r for r in model.resources if 'path' in r.data}
    included_resources = set()
    for document in model.resource_files:
        resource = by_path.get(document.path)
        if resource is None:
            resource = project_json_resource(model.configuration, document.path,
                                             document.content, model.binding)
        key = resource_identity(resource)
        if key in closure.resource_ids:
            paths.add(document.path)
            included_resources.add(key)
    require(included_resources == set(closure.resource_ids), 'bundle_partial_resource_missing')
    # Declarative package files are retained by the native observation but are
    # not independent model-manifest rows. Include the configured packages that
    # actually contribute to the bound effective profile, with original bytes.
    ordinary = set(model.source_files)
    packages = {p.key: p for p in model.language_packages}
    included_packages = set()
    for path, raw in origin.payloads.items():
        if path in ordinary:
            continue
        require(origin.source.classify(path) is PathClass.PROFILE, 'bundle_partial_source_unclassified')
        package = LanguagePackage(raw)
        if package.key in packages:
            require(package.source_bytes == packages[package.key].source_bytes,
                    'bundle_partial_package_changed', code='SRV060')
            paths.add(path)
            included_packages.add(package.key)
    require(included_packages == set(packages), 'bundle_partial_package_missing')
    return {p: origin.payloads[p] for p in sorted(paths, key=lambda p: p.encode('utf-8'))}


def _prepare_partial(root, descriptor):
    require(type(descriptor) is ScopeDescriptor, 'bundle_scope_descriptor_required')
    selection = descriptor.data
    require(selection['scope_kind'] in ('document', 'release')
            and selection['boundary_policy'] == 'partial', 'bundle_scope_combination')
    if selection['configuration_id'] is not None:
        raise BundleError('bundle_partial_configuration_provider_required', code=None, exit_code=2)
    # Reuse the full native origin guard, including empty-receipt observation.
    # A partial marker is never promoted, nor is a missing origin target guessed.
    origin = ProjectBundleSnapshot(root)
    closure, native, artifacts, _ = export_scope(origin.model, descriptor)
    payloads = _selected_payloads(origin, closure, artifacts)
    exclusions = {p: 'outside_scope' for p in origin.payloads if p not in payloads}
    exclusions.update({p: 'unreferenced_archive_object' for p in origin.archives
                       if p not in origin.payloads})
    metadata = {
        'bundle_format_version': '1.0.0', 'bundle_kind': 'partial', 'read_only': True,
        'project_id': origin.model.configuration.project_id, 'schema_version': '0.2.0',
        'tool_version': __version__, 'scope_descriptor': selection,
        'origin_model_root_sha256': origin.native.sha256,
        'bundle_model_root_sha256': native.sha256,
        'profile_sha256': native.data['profile_sha256'],
        'configuration_sha256': native.data['configuration_sha256'],
        'boundary_references': native.data['boundary_references'],
        'idempotency_scope': 'local_only',
        'excluded_contents': [{'path': p, 'reason': exclusions[p]}
                              for p in sorted(exclusions, key=lambda p: p.encode('utf-8'))],
    }
    container = BundleContainer(encode_bundle(metadata, payloads))
    require(container.files == payloads, 'bundle_partial_payload_incomplete', code='SRV060')
    require({key: container.manifest[key] for key in metadata} == metadata,
            'bundle_partial_metadata_changed', code='SRV060')
    origin.verify_current()
    return container, origin.source, origin.verify_current


def prepare_partial_bundle(root, descriptor):
    """Return owned canonical partial bytes without creating files or locks.

    The descriptor must select an unconfigured document/release with partial
    boundaries. All omitted weak targets are present and hashed in the complete
    origin. Stored partial targets are never used as a substitute origin.
    Nonempty receipt histories remain outside this initial provider's support.
    """
    try:
        return _prepare_partial(root, descriptor)[0]
    except SafetyViolation as error:
        raise BundleError('unsafe_bundle_project_source', code='SRV083', exit_code=7) from error
    except ModelError as error:
        raise BundleError(error.reason, exit_code=getattr(error, 'exit_code', 3)) from error
    except SrxError as error:
        raise BundleError(error.reason, code=error.code) from error
    except OperationFailure as error:
        raise BundleError('bundle_project_preflight_failed', code=None, exit_code=int(error.kind)) from error
    except OSError as error:
        raise BundleError('bundle_project_io', code=None, exit_code=5) from error
