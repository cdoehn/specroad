"""Bound native-scope export to existing format codecs and a separate manifest.

The pure preparation API accepts owned model bytes. The live publication API
owns inventory discovery and final currentness checks; neither grants a write
to normative project files or a release approval.
"""
from dataclasses import dataclass, replace
from hashlib import sha256
import json

from ..changes.target_model import TargetModel
from ..graph.scope_descriptors import ScopeDescriptor
from ..mappings import ExchangeMapping, select_mapping
from ..mappings.csv_profile import CSVProfile
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ._export_manifest import ExportLosses, manifest_bytes
from ._export_scope import export_scope


class ExportError(ModelError):
    def __init__(self, reason, *, exit_code=3, manifest=None, **location):
        super().__init__(reason, **location)
        self.exit_code = exit_code
        self.manifest = manifest


@dataclass(frozen=True)
class PreparedExport:
    output_bytes: bytes
    manifest_bytes: bytes
    attachment_files: tuple

    @property
    def manifest(self):
        return json.loads(self.manifest_bytes)


def _mappings(model):
    mappings, profiles = [], []
    for document in model.resource_files:
        from ..model.paths import PathClass, classify_path
        if classify_path(document.path, model.configuration) is not PathClass.MAPPING:
            continue
        value = parse_json_object(document.content)
        kind = value.get('mapping_format_version')
        if kind == 'exchange-mapping-v1':
            mappings.append(ExchangeMapping(document.content))
        elif kind == 'csv-profile-v1':
            profiles.append(CSVProfile(document.content))
    return mappings, profiles


def _pointer(field):
    return '/' + field.replace('~', '~0').replace('/', '~1')


def _csv(artifacts, mapping, profiles, key, expected, losses):
    from .csv import select_csv_profile
    codec = select_csv_profile([*profiles, mapping], key=key, expected_sha256=expected)
    profile = codec.profile
    p = profile.data
    native_type = next(t['artifact_type'] for t in mapping.data['types'] if t['external_type'] == p['external_type'])
    rules = [r for r in mapping.data['fields'] if r['external_type'] == p['external_type']]
    represented, rows = [], []
    for artifact in artifacts:
        if artifact['artifact_type'] != native_type:
            losses.add(artifact['id'], '', 'csv_artifact_type_unmapped')
            continue
        if p['identity']['kind'] == 'native_id':
            identity = artifact['id']
        else:
            # No source context is guessed from an output path or mapping name.
            identities = [i for i in artifact.get('external_identities', [])
                          if i.get('mapping_id') == mapping.key]
            if len(identities) != 1:
                raise ExportError('csv_external_identity_ambiguous', exit_code=6)
            identity = identities[0]['external_id']
        fields = codec.external_fields({r['target_field']: artifact[r['target_field']]
                                       for r in rules if r['target_field'] in artifact})
        rows.append({'identity': {'kind': p['identity']['kind'], 'value': identity},
                     'external_type': p['external_type'], 'fields': fields})
        represented.append(artifact)
        retained = {'id', 'artifact_type'} | {r['target_field'] for r in rules}
        for field in artifact.keys() - retained:
            losses.add(artifact['id'], _pointer(field), 'csv_field_unmapped')
    return codec.encode(rows), tuple(represented), profile.binding()


def _attachment_files(model, attachments, include_attachments, losses):
    """Verify selected bytes even when transport of attachments is disabled."""
    payloads = dict(model.source_files)
    files = []
    for attachment in attachments:
        raw = payloads.get(attachment.path)
        if (type(raw) is not bytes or len(raw) != attachment.size
                or sha256(raw).hexdigest() != attachment.sha256):
            raise ExportError('export_attachment_bytes_changed', exit_code=6)
        if include_attachments:
            files.append((attachment.path, raw))
        else:
            losses.add(attachment.path, '', 'attachments_disabled')
    return files


def _reqif_bounds(model, output_format, reqif_limits, max_archive_bytes):
    from .reqif import ReqIFLimits
    if type(reqif_limits) is not ReqIFLimits:
        raise ExportError('typed_xml_limits_required', exit_code=2)
    # Explicit caller limits may tighten, never raise project/profile
    # hard boundaries. Other fields keep their existing codec contract.
    hard = model.profile.data['merge']['hard_limits']
    configured = model.configuration.data.get('resource_limits', {})
    depth = min(reqif_limits.max_depth, configured.get('xml_depth', reqif_limits.max_depth),
                hard.get('xml_depth', reqif_limits.max_depth))
    reqif_limits = replace(reqif_limits, max_depth=depth)
    if output_format == 'reqifz':
        if type(max_archive_bytes) is not int or max_archive_bytes < 1:
            raise ExportError('reqifz_expansion_limit_required', exit_code=2)
        max_archive_bytes = min(max_archive_bytes,
            configured.get('archive_uncompressed_bytes', max_archive_bytes),
            hard.get('archive_uncompressed_bytes', max_archive_bytes))
    return reqif_limits, max_archive_bytes


def prepare_export(model, descriptor, *, output_format, mapping_key, expected_mapping_sha256,
                   csv_profile_key=None, expected_csv_profile_sha256=None,
                   include_attachments=False, fail_on_loss=False, reqif_limits=None,
                   max_archive_bytes=None):
    """Derive all declarations from actual source, format and attachment bytes."""
    if type(model) is not TargetModel or type(descriptor) is not ScopeDescriptor:
        raise ExportError('export_model_scope_required', exit_code=2)
    if (type(output_format) is not str or output_format not in ('reqif', 'reqifz', 'csv', 'ndjson')
            or descriptor.data['scope_kind'] not in ('project', 'document', 'query', 'release')
            or type(include_attachments) is not bool or type(fail_on_loss) is not bool):
        raise ExportError('export_options_invalid', exit_code=2)
    if output_format not in ('reqif', 'reqifz') and reqif_limits is not None:
        raise ExportError('export_xml_limits_not_applicable', exit_code=2)
    if output_format != 'reqifz' and max_archive_bytes is not None:
        raise ExportError('export_archive_limit_not_applicable', exit_code=2)
    model = model.snapshot()
    mappings, profiles = _mappings(model)
    mapping = select_mapping(mappings, key=mapping_key, expected_sha256=expected_mapping_sha256).resource
    if mapping.data['source_format'] != ('reqif' if output_format == 'reqifz' else output_format):
        raise ExportError('export_mapping_format_mismatch', exit_code=2)
    if output_format != 'csv' and (csv_profile_key is not None or expected_csv_profile_sha256 is not None):
        raise ExportError('export_csv_profile_not_applicable', exit_code=2)
    closure, native, artifacts, resources = export_scope(model, descriptor)
    losses = ExportLosses()
    attachments = tuple(closure.attachments)
    files = _attachment_files(model, attachments, include_attachments, losses)
    profile = None
    if output_format == 'ndjson':
        from .ndjson import encode_ndjson
        represented = artifacts
        output = encode_ndjson([{'format_version': '1.0.0', 'object_kind': 'artifact',
                                 'object': value} for value in artifacts])
    elif output_format == 'csv':
        output, represented, profile = _csv(artifacts, mapping, profiles, csv_profile_key,
                                            expected_csv_profile_sha256, losses)
    else:
        reqif_limits, max_archive_bytes = _reqif_bounds(model, output_format, reqif_limits, max_archive_bytes)
        from ._export_reqif import export_reqif
        output, represented = export_reqif(artifacts, mapping, model, losses,
            attachments=tuple(files), scope_attachments=attachments,
            resource_ids=closure.resource_ids, limits=reqif_limits)
        if output_format == 'reqifz':
            from .reqifz import encode_reqifz
            output = encode_reqifz({'exchange.reqif': output, **dict(files)},
                document_paths=('exchange.reqif',), limits=reqif_limits,
                max_uncompressed_bytes=max_archive_bytes)
            files = []  # Actual attachment bytes now live in the primary ZIP.
    # Format codecs carry native artifacts, not the complete project resource
    # set. A mapping hash or profile hash is not preservation of its payload.
    for key in closure.resource_ids:
        if resources[key].data['kind'] != 'attachment':
            losses.add(key, '', 'native_resource_not_in_exchange_format')
    manifest = manifest_bytes(output_format=output_format, mapping=mapping, format_profile=profile,
        native=native, artifacts=represented, losses=losses, attachments=attachments,
        include_attachments=include_attachments, fail_on_loss=fail_on_loss, output=output)
    if fail_on_loss and losses.rows:
        raise ExportError('export_information_loss', manifest=manifest)
    return PreparedExport(output, manifest, tuple(files))
