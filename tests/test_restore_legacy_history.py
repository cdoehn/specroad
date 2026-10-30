"""Restore's declared-format boundary uses synthetic unsupported inputs.

No fixture here claims a defined historical 0.1 schema or an actual old release.
Unsupported declarations remain exact original bytes, not disposable damage.
"""
from hashlib import sha256
import json

import pytest

from specroad.bundles.container import BundleContainer, encode_bundle
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.recovery import RestoreError, prepare_restore_plan
from support.domain import domain_value
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import record_value
from support.restore import restore_case
from test_restore_plan import decode_files
from test_restore_plan_right import retained_case


VERSIONS = ['0.1.0', '9.8.7']


def unsupported(version):
    return canonical_json_bytes(record_value('evidence', schema_version=version))


def legacy_registration():
    return canonical_json_bytes({'schema_version': '0.2.0', 'mapping_id': 'legacy-preservation',
        'mapping_version': '1.0.0', 'legacy_manifest_version': '1.0.0'})


def refuse(options, path, *, legacy=False):
    before = inventory(options['project_root'].parent)
    with no_write_attempts(), pytest.raises(RestoreError) as caught:
        prepare_restore_plan(**options)
    assert caught.value.exit_code == 3
    assert caught.value.reason == ('restore_legacy_source_contract_required' if legacy else
                                   'restore_unsupported_source_schema_version')
    assert caught.value.path == path
    if not legacy:
        assert caught.value.diagnostic()['highest_supported'] == '0.2.0'
        assert caught.value.diagnostic()['pointer'] == '/schema_version'
    assert not caught.value.mutation_possible
    assert inventory(options['project_root'].parent) == before


@pytest.mark.parametrize('version', VERSIONS)
@pytest.mark.parametrize('path', ['spec/evidence/SR-EVD-' + '0' * 26 + '.json',
                                 'profiles/unknown.json', 'rules/unknown.json', 'mappings/unknown.json'])
def test_current_declared_normative_format_is_not_discardable_damage(tmp_path, version, path):
    options, _, _ = restore_case(tmp_path)
    put(options['project_root'], path, unsupported(version))
    refuse(options, path)


@pytest.mark.parametrize('version', VERSIONS)
@pytest.mark.parametrize('configuration', [True, False], ids=['configuration', 'retained-baseline'])
def test_retained_history_cannot_mask_unsupported_configuration_or_baseline(tmp_path, version, configuration):
    options, _, _ = retained_case(tmp_path)
    path = 'specroad.json' if configuration else options['source_path']
    value = json.loads((options['project_root'] / path).read_bytes())
    value['schema_version'] = version
    put(options['project_root'], path, canonical_json_bytes(value))
    if not configuration:
        put(options['project_root'], 'specroad.json', b'damaged configuration')
    refuse(options, path)


@pytest.mark.parametrize('path', ['mappings/legacy-manifest.json', 'mappings/renamed.json'])
def test_current_legacy_manifest_registration_requires_its_actual_source_contract(tmp_path, path):
    options, _, _ = restore_case(tmp_path)
    put(options['project_root'], path, legacy_registration())
    refuse(options, path, legacy=True)


@pytest.mark.parametrize('version', VERSIONS)
def test_owned_current_archive_cannot_hide_an_unsupported_normative_original(tmp_path, version):
    options, _, _ = restore_case(tmp_path)
    raw = unsupported(version); digest = sha256(raw).hexdigest()
    path = f'archive/objects/{digest[:2]}/{digest}'
    put(options['project_root'], path, raw)
    refuse(options, path)


def attach_current_evidence(options, raw):
    from test_evidence_construction import inputs
    from specroad.storage.record_artifact import RecordArtifact
    from specroad.verification import prepare_evidence_record
    subjects, contract, args = inputs()
    # These real native subject/verification contracts support the new Evidence.
    for artifact in [*subjects, contract]:
        put(options['project_root'], artifact_path(artifact.data['artifact_type'], artifact.data['id'], 'SR'), artifact.source_bytes)
    evidence = prepare_evidence_record(subjects, contract, **{**args, 'result': 'failed'})
    path = 'attachments/original.json'
    descriptor = {'path': path, 'media_type': 'application/json', 'size': len(raw),
                  'sha256': sha256(raw).hexdigest()}
    evidence = RecordArtifact(canonical_json_bytes({**evidence.data, 'attachments': [descriptor]}))
    put(options['project_root'], artifact_path('evidence', evidence.id, 'SR'), evidence.source_bytes)
    put(options['project_root'], path, raw)
    return path


@pytest.mark.parametrize('version', VERSIONS)
def test_required_current_attachment_cannot_hide_unsupported_normative_original(tmp_path, version):
    options, _, _ = restore_case(tmp_path)
    path = attach_current_evidence(options, unsupported(version))
    refuse(options, path)


@pytest.mark.parametrize('version', VERSIONS)
@pytest.mark.parametrize('location', ['artifact', 'profile', 'attachment', 'archive', 'registration'])
def test_bound_full_bundle_payload_cannot_hide_an_unsupported_source(tmp_path, version, location):
    options, _, original = restore_case(tmp_path)
    bundle = BundleContainer(original); files = bundle.files
    raw = legacy_registration() if location == 'registration' else unsupported(version)
    digest = sha256(raw).hexdigest()
    path = {'artifact': 'spec/evidence/SR-EVD-' + '0' * 26 + '.json',
            'profile': 'profiles/unsupported.json', 'attachment': 'attachments/unsupported.json',
            'archive': f'archive/objects/{digest[:2]}/{digest}',
            'registration': 'mappings/legacy-manifest.json'}[location]
    files[path] = raw
    # The real codec proves transport integrity; semantic qualification must
    # still reject the declared resource before it trusts the claimed root.
    metadata = {k: v for k, v in bundle.manifest.items() if k != 'entries'}
    put(options['source_root'], options['source_path'], encode_bundle(metadata, files))
    refuse(options, path, legacy=location == 'registration')


@pytest.mark.parametrize('version', VERSIONS)
@pytest.mark.parametrize('location', ['baseline', 'object'])
def test_baseline_source_and_bound_object_use_the_same_declared_format_boundary(tmp_path, version, location):
    options, _, raw = restore_case(tmp_path, 'baseline')
    value = json.loads(raw)
    if location == 'baseline':
        value['schema_version'] = version
        expected = 'source:baseline'
    else:
        row = next(r for r in value['manifest'] if r['role'] == 'artifact')
        content = unsupported(version); digest = sha256(content).hexdigest()
        expected = f'archive/objects/{digest[:2]}/{digest}'
        row.update(object_path=expected, sha256=digest, size=len(content))
        put(options['source_root'], expected, content)
    put(options['source_root'], options['source_path'], canonical_json_bytes(value))
    refuse(options, expected)


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
def test_supported_02_legacy_ids_and_real_damaged_bytes_remain_recoverable(tmp_path, kind):
    values = [record_value('document', id='SR-DOC-0001', id_scheme='legacy-sequential-v1'),
              domain_value('goal', id='SR-GOAL-0001', id_scheme='legacy-sequential-v1')]
    options, original, _ = restore_case(tmp_path, kind, values=values)
    path = 'spec/goals/SR-GOAL-0001.json'
    damaged = b'{broken\xff\x00'
    put(options['project_root'], path, damaged)
    before = inventory(tmp_path)
    with no_write_attempts():
        plan = prepare_restore_plan(**options)
    assert decode_files(plan)[path] == original[path]
    assert decode_files(plan, 'backup')[path] == damaged
    assert inventory(tmp_path) == before


def test_foreign_attachment_version_and_legacy_named_extensions_are_opaque(tmp_path):
    from test_restore_history import evidence_case
    options, _, _, history = evidence_case(tmp_path)
    evidence_path = next(p for p in history if p.startswith('spec/'))
    value = json.loads(history[evidence_path])
    foreign = canonical_json_bytes({'schema_version': 'vendor-4.7', 'value': 'raw measurement', 'project_id': 'vendor-measurement',
        'legacy_manifest_version': 'third-party'})
    descriptor = value['attachments'][0]
    descriptor.update(size=len(foreign), sha256=sha256(foreign).hexdigest())
    value['extensions'] = {'example.legacy': {'schema_version': '0.1.0'}}
    put(options['project_root'], evidence_path, canonical_json_bytes(value))
    put(options['project_root'], descriptor['path'], foreign)
    before = inventory(tmp_path)
    with no_write_attempts():
        plan = prepare_restore_plan(**options)
    assert decode_files(plan)[descriptor['path']] == foreign
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('version', VERSIONS)
@pytest.mark.parametrize('identity', ['artifact_type', 'profile_id', 'rule_id', 'mapping_id'])
def test_incomplete_declared_normative_archive_is_not_reclassified_as_damage(tmp_path, version, identity):
    options, _, _ = restore_case(tmp_path)
    raw = canonical_json_bytes({'schema_version': version, identity: 'evidence' if identity == 'artifact_type' else 'old'})
    digest = sha256(raw).hexdigest()
    path = f'archive/objects/{digest[:2]}/{digest}'
    put(options['project_root'], path, raw)
    refuse(options, path)


@pytest.mark.parametrize('version', VERSIONS)
@pytest.mark.parametrize('field,value', [('id_prefix', 'SR'), ('project_name', 'Historical project'),
                                         ('validation_policy', {})])
def test_declared_archived_configuration_without_coverage_is_not_discardable(tmp_path, version, field, value):
    options, _, _ = restore_case(tmp_path)
    raw = canonical_json_bytes({'schema_version': version, 'project_id': 'sample', field: value})
    digest = sha256(raw).hexdigest()
    path = f'archive/objects/{digest[:2]}/{digest}'
    put(options['project_root'], path, raw)
    refuse(options, path)
