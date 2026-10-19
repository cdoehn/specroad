"""Pure metadata/check projections shared by explicit and implicit contracts."""

from hashlib import sha256

from ..model.canonical import canonical_json_sha256
from ..storage.json_syntax import parse_json_object


def record_binding(raw, path):
    value = parse_json_object(raw, path=path)
    return {'artifact_id': value['id'], 'artifact_type': value['artifact_type'],
            'revision': value['revision'], 'path': path,
            'source_sha256': sha256(raw).hexdigest(),
            'record_sha256': canonical_json_sha256(value), 'record': value}


def required_checks(subject_id, contract_id, slots):
    checks = [{'subject_artifact_id': subject_id, 'contract_id': contract_id,
               'test_id': slot['test_id'], 'check_id': slot['check_id'],
               'dimension': slot['dimension']} for slot in slots]
    checks.sort(key=lambda item: ((item['test_id'] or '').encode('utf-8'),
                                  item['check_id'].encode('utf-8')))
    return checks


def resolution_data(model, source, contract, edges, tests, checks, *,
                    validation_scope, implicit_contract=None):
    """Project already checked inputs; no additional validation or authority."""
    from ..changes.target_model import _default_scope
    descriptor = _default_scope()
    data = {'format_version': 'verification-contract-v1', 'project_id': model.binding.project_id,
            'scope_descriptor': descriptor,
            'model_root_sha256': model.manifest(model.artifacts, descriptor).sha256,
            'input_sha256': model._sources_sha256,
            'validation_scope': validation_scope,
            'subject': record_binding(source.source_bytes, source.path), 'contract': contract,
            'relations': [{'relation_id': relation.identity.id,
                           'pointer': '/relations/' + str(position),
                           'record': relation.data,
                           'record_sha256': canonical_json_sha256(relation.data)}
                          for position, relation in edges],
            'tests': tests, 'required_checks': checks,
            'project_files_verified': False, 'full_validation_passed': False,
            'project_required_checks_complete': False, 'configuration_applicability_evaluated': False,
            'evidence_evaluated': False, 'test_code_executed': False,
            'write_authorized': False, 'approval_granted': False}
    if implicit_contract is not None:
        data['implicit_contract'] = implicit_contract
    return data
