"""Original-bound native adapters; no implicit measurements or external fetch."""
from copy import deepcopy
from hashlib import sha256
from ..model.canonical import canonical_json_sha256
from ..storage.json_syntax import parse_json_object
from ..verification.imports import prepare_generic_import, prepare_sarif_import, prepare_junit_import
from .target_values import TargetError


def prepare_native_import(model, raw, targets, policy, format_name, extras):
    allowed = {'generic': {'run_context'},
        'sarif': {'mapping_path','mapping_sha256','run_context'},
        'junit': {'mapping_path','mapping_sha256','measurements_path','measurements_sha256',
                 'external_identifiers_path','external_identifiers_sha256','tool','run_context'}}
    if format_name not in allowed or set(extras) - allowed[format_name]:
        raise TargetError('evidence_import_format_inputs_mismatch')
    descriptors = {v.path:v.data for v in model.attachment_descriptors}
    originals = []
    def read(role, required=True):
        path, bound = extras.get(role+'_path'), extras.get(role+'_sha256')
        if path is None and bound is None and not required:
            return None
        if type(path) is not str or type(bound) is not str:
            raise TargetError('evidence_import_original_binding_required')
        descriptor = descriptors.get(path); content = model.source_files.get(path)
        if (descriptor is None or content is None or sha256(content).hexdigest()!=bound
                or descriptor['sha256']!=bound or descriptor['size']!=len(content)):
            raise TargetError('evidence_import_original_binding_changed')
        originals.append(descriptor)
        return content
    target_values = list(targets.values())
    if format_name=='generic':
        prepared = prepare_generic_import(raw,targets=target_values,policy=policy)
        data, binding = prepared.data, prepared.sha256
    elif format_name=='sarif':
        prepared = prepare_sarif_import(raw,read('mapping'),targets=target_values,policy=policy)
        data, binding = prepared.data, prepared.sha256
    else:
        from ..verification.junit import JUnitDocument
        from ..verification.junit_mapping import JUnitMapping, JUnitMappingRules, JUnitExternalIdentifiers
        mapping_raw=read('mapping'); measured_raw=read('measurements'); sidecar=read('external_identifiers',False)
        mapping_type = JUnitMappingRules if parse_json_object(mapping_raw).get('format_version')=='junit-mapping-rules-v1' else JUnitMapping
        # JUnit contains no reliable producer, subject-state or run binding.
        # An explicit complete Exchange supplies those fields, never the clock.
        mapped = prepare_junit_import(JUnitDocument(raw),mapping_type(mapping_raw),
            targets=[v for v in target_values if v.data['artifact_type'] in ('verification','test')],
            policy=policy,tool=extras.get('tool'),
            external_identifiers=None if sidecar is None else JUnitExternalIdentifiers(sidecar))
        measured = prepare_generic_import(measured_raw,targets=target_values,policy='abort_import')
        data = deepcopy(measured.data)
        observations=mapped.data
        if observations['decision']!='prepared' or data['decision']!='prepared':
            raise TargetError('evidence_import_aborted')
        if len(data['candidates'])!=len(observations['candidates']):
            raise TargetError('evidence_import_complete_preparation_mismatch')
        for full, occurrence in zip(data['candidates'],observations['candidates']):
            target=occurrence['target']['artifact_id']
            declared=full['target']['artifact_id'] if occurrence['target']['artifact_type']=='verification' else full['run_context']['test_id']
            if target!=declared or full['result']!=occurrence['result'] or full['tool']!=extras['tool']:
                raise TargetError('evidence_import_measurement_mapping_mismatch')
            full.update(origin='imported_junit',source_pointer=occurrence['testcase_pointer'])
        data['provenance'] = observations['provenance']
        data['diagnostics'] = observations['diagnostics']
        binding=canonical_json_sha256({'junit_preparation':mapped.sha256,'measurements_preparation':measured.sha256})
    if 'run_context' in extras and any(v['run_context']!=extras['run_context'] for v in data['candidates']):
        raise TargetError('evidence_import_run_context_conflict')
    return data,binding,tuple(originals)
