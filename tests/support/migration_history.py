"""Small declared synthetic historical records; no real run or approval claim."""
import json
from .migration_plans import vector_source
from .reference01 import artifact, context, digest, put, relation, seal

EVIDENCE = 'spec/evidence/SR-EVD-0001.json'
REQUIREMENT = 'spec/requirements/SR-REQ-0001.json'
VERIFICATION = 'spec/verifications/SR-VER-0001.json'
BASELINE = 'spec/baselines/SR-BASE-0001.json'
PROJECT_ID = 'synthetic-reference-project'


def evidence_source(*, result='passed', nested=False):
    files = vector_source()
    subject = json.loads(files[REQUIREMENT])
    subject['relations'].append(relation('verified_by', 'SR-VER-0001'))
    put(files, subject)
    contract = artifact('verification')
    # No selected configuration: independence must be declared by the
    # synthetic contract as well as its recorded historical Evidence.
    contract['configuration_policy'] = 'independent'; put(files, contract)
    evidence = artifact('evidence')
    evidence.update(result=result, context_hash_algorithm='reference01-verification-context-v1',
        configuration_hash=None, configuration_policy='independent',
        subjects=[{'artifact_id': value['id'], 'revision': value['revision'],
            'artifact_sha256': digest(value), 'verification_context_sha256': context(value)}
            for value in (subject, contract)])
    put(files, evidence); seal(files)
    if nested:
        subject['revision'] += 1
        subject['statement'] += ' Additional requirement.'
        put(files, subject); seal(files, 2)
    return files


def historical_contract_host(observations):
    """Native checks for this draft-only fixture, never a current passed run.

    The writer requires a host service even for a draft Verification contract.
    Only this fixture's contract without executable Test slots is supported;
    unrelated contracts and current Evidence require their own real providers.
    """
    from specroad.migration.history import verify_migrated_history
    from specroad.migration.legacy_values import LegacyManifest
    from specroad.model.errors import ModelError
    from specroad.validation import ModelGate
    from specroad.verification.contracts import VerificationContract

    def dependencies(context):
        return context.dependency_result({i: list(context.all_ids) for i in context.subjects})

    def check(context):
        if type(context.legacy_manifest) is not LegacyManifest or context.subjects != ('SR-VER-0001',):
            raise ModelError('synthetic_history_host_scope')
        files = dict(context.legacy_manifest._files)
        if any(files[d.path] != d.content for d in context.documents if d.path in files):
            raise ModelError('synthetic_history_host_documents_changed')
        raw = next(d.content for d in context.documents if d.path == VERIFICATION)
        contract = VerificationContract(raw, path=VERIFICATION)
        value = contract.data
        if (value['maturity'] != 'draft' or value['subjects'] != ['SR-REQ-0001']
                or value['configuration_policy'] != 'independent'
                or any(slot['test_id'] is not None for slot in value['evidence_slots'])):
            raise ModelError('synthetic_history_host_scope')
        history = verify_migrated_history(files, project_id=PROJECT_ID).data
        observations.append(history)
        # The native reader checked the full original closure. The contract
        # reader checked the actual current contract; no run was performed.
        # Keep the absent current result visible even though retention is valid.
        return context.result([{'reason': 'migration_context_unverified', 'severity': 'info',
                                'artifact_id': value['id'], 'path': VERIFICATION}])

    return ModelGate('evidence_currentness', 'synthetic-historical-contract-v1', dependencies, check)
