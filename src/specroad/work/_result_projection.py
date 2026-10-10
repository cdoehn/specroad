"""Pure file/result projections from observations checked by the Work adapters.

These functions only form values. Native commit proof, checkpoint validation,
leases, file publication and fresh delivery checks stay with their coordinators.
"""

from hashlib import sha256

from ..cli.result_schemas import ENVELOPE_ID, validate_result_document
from ..cli.results import ResultReference
from ..model.canonical import canonical_json_bytes


def _reference(path, raw, schema):
    return ResultReference(str(path), 'application/json', len(raw),
                           sha256(raw).hexdigest(), schema)


def read_only_result_projection(root_path, value, raw, outcome, exit_code, schema):
    name = 'result-' + sha256(raw).hexdigest() + '.json'
    reference = _reference(root_path / 'results' / name, raw, schema)
    entry = {**reference.as_dict(), 'path': 'results/' + name, 'role': 'result'}
    manifest = canonical_json_bytes({'format_version': 'work-result-files-v1',
        'work_id': value['work_id'], 'command_id': value['command_id'],
        'checkpoint_generation': value['checkpoint_generation'],
        'checkpoint_sha256': value['checkpoint_sha256'],
        'outcome_sha256': sha256(canonical_json_bytes(outcome)).hexdigest(),
        'exit_code': exit_code, 'files': [entry]})
    manifest_name = 'manifest-' + sha256(manifest).hexdigest() + '.json'
    manifest_ref = _reference(root_path / 'results' / manifest_name, manifest, 'work-result-files-v1')
    # The complete diagnostics stay in this envelope. This first adapter does
    # not truncate them or claim a separate large-diagnostic delivery protocol.
    external = {**outcome, 'result': None, 'result_ref': reference.as_dict(),
                'summary': {**outcome['summary'], 'delivery': 'external'}}
    validate_result_document(ENVELOPE_ID, external)
    result = {'format_version': 'work-result-delivery-v1', 'work_id': value['work_id'],
        'checkpoint_generation': value['checkpoint_generation'],
        'checkpoint_sha256': value['checkpoint_sha256'],
        'command_exit_code': exit_code, 'command_outcome': external,
        'delivery_manifest': manifest_ref.as_dict(), 'work_checkpoint_changed': False,
        'project_writes_performed': False, 'handler_executed': False}
    return ((name, raw), (manifest_name, manifest)), result


def native_result_projection(root_path, value, raw):
    name = 'result-' + sha256(raw).hexdigest() + '.json'
    reference = _reference(root_path / 'results' / name, raw, 'normative-request-resolution-v1')
    entry = {**reference.as_dict(), 'path': 'results/' + name, 'role': 'native_request_resolution'}
    manifest = canonical_json_bytes({'format_version': 'work-receipt-files-v1',
        'work_id': value['work_id'], 'command_id': value['command_id'],
        'checkpoint_generation': value['checkpoint_generation'],
        'checkpoint_sha256': value['checkpoint_sha256'], 'request_id': value['request_id'],
        'request_resolution_sha256': sha256(raw).hexdigest(), 'files': [entry]})
    manifest_name = 'manifest-' + sha256(manifest).hexdigest() + '.json'
    manifest_ref = _reference(root_path / 'results' / manifest_name, manifest, 'work-receipt-files-v1')
    result = {'format_version': 'normative-work-result-delivery-v1',
        'work_id': value['work_id'], 'checkpoint_generation': value['checkpoint_generation'],
        'checkpoint_sha256': value['checkpoint_sha256'], 'result_ref': reference.as_dict(),
        'delivery_manifest': manifest_ref.as_dict(), 'work_checkpoint_changed': False,
        'work_completion_recorded': False, 'normative_writes': 0, 'write_authorized': False}
    return ((name, raw), (manifest_name, manifest)), result
