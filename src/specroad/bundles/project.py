"""Prepare a closed project from actual native bytes, without publishing files.

This first live provider supports projects with an explicitly checked empty
receipt inventory. Nonempty history needs the later portable receipt provider;
it must never be silently omitted or advertised as an empty portable history.
Extraction, arbitrary-bundle verification and write admission remain separate.
"""
import os

from .. import __version__
from ..authoring._inspection_snapshot import InspectionSnapshot, InspectionChanged
from ..changes.target_model import _default_scope
from ..cli.results import OperationFailure
from ..exchange._export_scope import export_scope, resource_identity
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_bytes
from ..model.domain_schemas import DOMAIN_TYPES, validate_domain_fields
from ..model.errors import ModelError
from ..model.operational_paths import REQUESTS_ROOT, RECEIPTS_ROOT
from ..model.paths import PathClass
from ..model.record_schemas import validate_record_fields
from ..query.show import _preflight
from ..security import SafetyViolation
from ..security.resource_access import opened_resource, directory_entries, resource_is_directory
from ..storage.json_syntax import parse_json_object
from ..storage.project import ProjectSource
from ..srx.errors import SrxError
from .container import BundleContainer, encode_bundle
from .errors import BundleError
from .manifest import MANIFEST_NAME, owned_metadata, check_entries, require


def _empty_receipts(source):
    # Shallow read preflight deliberately skips passive histories. Absence or
    # emptiness is therefore observed here, through guarded directory handles.
    for path in (REQUESTS_ROOT, RECEIPTS_ROOT):
        with opened_resource(source.boundary, path, directory=True, missing_ok=True) as (fd, _):
            if fd is not None and os.listdir(fd):
                raise BundleError('bundle_portable_receipt_provider_required', code=None, exit_code=5)


def _previous_manifest(source):
    # An extracted partial project may happen to have a closed-looking model.
    # Its marker still prohibits promotion to a writable full bundle.
    with opened_resource(source.boundary, MANIFEST_NAME, missing_ok=True) as (fd, _):
        if fd is None:
            return None
        raw = source.boundary.read_bytes(MANIFEST_NAME)
    value = parse_json_object(raw)
    require('entries' in value, 'bundle_entries_missing')
    check_entries(value['entries'])
    metadata = owned_metadata({key: item for key, item in value.items() if key != 'entries'})
    require(raw == canonical_json_bytes(value), 'noncanonical_bundle_manifest', code='SRV060')
    require(metadata['project_id'] == source.configuration.project_id, 'bundle_configuration_binding')
    if metadata['bundle_kind'] != 'project':
        raise BundleError('bundle_partial_project_source', code=None, exit_code=2)
    return raw


def _archive_paths(source):
    """Observe managed archive names, including deliberately omitted objects."""
    pending = [(p, True) for p in source.configuration.managed_paths if p.split('/')[0] == 'archive']
    seen, paths = set(), set()
    while pending:
        path, optional = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        directory = resource_is_directory(source.boundary, path, missing_ok=optional)
        if directory is None:
            continue
        if directory:
            pending.extend((path + '/' + name, False) for name, _ in directory_entries(source.boundary, path))
        else:
            require(source.classify(path) is PathClass.ARCHIVE_OBJECT, 'bundle_archive_path_invalid')
            paths.add(path)
    return tuple(sorted(paths, key=lambda p: p.encode('utf-8')))


def _prepare(root):
    source = ProjectSource(root)
    _preflight(source)
    _empty_receipts(source)
    previous_manifest = _previous_manifest(source)
    snapshot = InspectionSnapshot(root, None, include_archive_objects=True)
    if (snapshot.source.boundary._root_identity != source.boundary._root_identity
            or snapshot.source.configuration_bytes != source.configuration_bytes):
        raise BundleError('bundle_project_changed', code=None, exit_code=6)
    archives = _archive_paths(source)
    descriptor = ScopeDescriptor(_default_scope())
    model = snapshot.model
    for artifact in model.artifacts:
        (validate_domain_fields if artifact['artifact_type'] in DOMAIN_TYPES else
         validate_record_fields)(artifact)
    closure, native, artifacts, _ = export_scope(model, descriptor)
    require(set(closure.artifact_ids) == {a['id'] for a in model.artifacts}
            and set(closure.resource_ids) == {resource_identity(r) for r in model.resources}
            and not closure.boundary_references, 'bundle_project_closure_incomplete')
    require(native.sha256 == model.manifest(artifacts, descriptor.data).sha256,
            'bundle_project_manifest_mismatch', code='SRV060')
    # Snapshot.raw also retains the actual declarative language-package files;
    # TargetModel.source_files alone would lose those required source bytes.
    payloads = dict(snapshot.raw)
    require(set(snapshot.payload_paths).intersection(archives) ==
            {p for p in snapshot.payload_paths if p.startswith('archive/')},
            'bundle_archive_inventory_incomplete')
    metadata = {
        'bundle_format_version': '1.0.0', 'bundle_kind': 'project', 'read_only': False,
        'project_id': model.configuration.project_id, 'schema_version': '0.2.0',
        'tool_version': __version__, 'scope_descriptor': descriptor.data,
        'origin_model_root_sha256': native.sha256, 'bundle_model_root_sha256': native.sha256,
        'profile_sha256': native.data['profile_sha256'],
        'configuration_sha256': native.data['configuration_sha256'],
        'boundary_references': [], 'idempotency_scope': 'portable',
        'excluded_contents': [{'path': p, 'reason': 'unreferenced_archive_object'}
                              for p in archives if p not in payloads],
    }
    container = BundleContainer(encode_bundle(metadata, payloads))
    # Compare the decoded product with the complete selected input, not merely
    # an internally consistent ZIP inventory. In particular inactive resources
    # and declarative language-package source bytes must not disappear.
    require(container.files == payloads, 'bundle_project_payload_incomplete', code='SRV060')
    require({key: container.manifest[key] for key in metadata} == metadata,
            'bundle_project_metadata_changed', code='SRV060')

    def verify_current():
        snapshot.verify_current()
        if _archive_paths(source) != archives or _previous_manifest(source) != previous_manifest:
            raise InspectionChanged('bundle_inventory_changed')
        _empty_receipts(source)
        _preflight(source)
        source.check_current()

    verify_current()
    # The publisher retains this exact observation until the final atomic move;
    # a fresh snapshot cannot legitimize stale, previously encoded bytes.
    return container, source, verify_current


def prepare_project_bundle(root):
    """Return owned canonical bytes after native project selection and closure.

    All current artifact/resource bytes and required snapshot/attachment bytes
    are retained. Profile selection comes from the project; configuration-filtered
    and partial sources are not promoted. No lock, journal, cache or output is
    created. Final rereads detect observed changes, not an atomic disk snapshot.
    The returned container does not grant authenticity, approval or write access.
    """
    try:
        return _prepare(root)[0]
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
