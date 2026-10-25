"""Prepare document/release bytes from a retained, complete origin observation.

Configuration context retains the native parent-chain bytes without changing
scope membership. The returned container never grants extraction, authenticity
or write authority; independent input-bundle verification is a separate step.
"""
from .. import __version__
from ..cli.results import OperationFailure
from ..configurations import evaluate_applicability, resolve_configuration
from ..exchange._export_scope import export_scope, resource_identity
from ..graph.relations import SourceRelations
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


def _configuration_context(model, selection):
    if selection['configuration_id'] is None:
        return (), None
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    effective = resolve_configuration(records, selection['configuration_id'])
    kind = selection['scope_kind']
    anchor_id = selection['selector'][kind + '_id']
    anchor = next((r for r in records if r.identity.id == anchor_id), None)
    require(anchor is not None and anchor.identity.artifact_type == kind,
            'bundle_partial_anchor_missing')
    require(evaluate_applicability(anchor, effective, require_configuration=True).status == 'applicable',
            'bundle_partial_anchor_excluded')
    paths = tuple(artifact_path('configuration', item['id'], model.configuration.id_prefix)
                  for item in effective.manifest['configurations'])
    return paths, effective.scope_sha256(model.configuration)


def _selected_payloads(origin, closure, artifacts, context_paths):
    model = origin.model
    paths = {'specroad.json', *context_paths}
    require(paths <= origin.payloads.keys(), 'bundle_partial_configuration_context_missing')
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
    # Reuse the full native origin guard, including empty-receipt observation.
    # A partial marker is never promoted, nor is a missing origin target guessed.
    origin = ProjectBundleSnapshot(root)
    context_paths, configuration_sha256 = _configuration_context(origin.model, selection)
    closure, native, artifacts, _ = export_scope(origin.model, descriptor)
    if configuration_sha256 is not None:
        require(configuration_sha256 == native.data['configuration_sha256'],
                'bundle_partial_configuration_binding', code='SRV060')
    payloads = _selected_payloads(origin, closure, artifacts, context_paths)
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

    The descriptor selects a document/release with partial boundaries and an
    optional native configuration. All omitted weak targets are present and
    hashed in the complete origin. A partial target never substitutes for it.
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
