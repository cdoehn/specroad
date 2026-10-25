"""15.f.W: actual partial Show, exact boundaries and no context promotion."""
import json
import shutil

import pytest

from specroad.bundles import BundleContainer, prepare_partial_bundle
from specroad.bundles.extraction import extract_bundle
from specroad.bundles.manifest import MANIFEST_NAME
from specroad.bundles._extraction_record import COMPLETED
from specroad.authoring._bootstrap_io import STAGING
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.result_schemas import validate_result_document
from specroad.model.canonical import canonical_json_bytes
from specroad.query import show_artifact
from specroad.query.read_work import ReadCommandWork
from specroad.security import SafetyViolation
from specroad.storage.project import ProjectSource
from support.inspection import inspection_project
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from test_bundle_verification import rebind
from test_bundle_verification_right import reviewed, path, context_path
from test_partial_bundle import scope
from test_partial_bundle_right import configured


def extracted(tmp_path, kind='document', context='review'):
    origin = tmp_path / 'origin'
    if context == 'review':
        values, review = reviewed(origin, kind)
        members, hidden = [*values[:-2], review], [values[-2]]
        selected = scope(kind)
    else:
        values, chain, _ = configured(origin, kind)
        members, hidden = values[:-2], chain
        selected = scope(kind, configuration_id=chain[-1]['id'])
    bundle = prepare_partial_bundle(origin, selected)
    target = tmp_path / 'partial'
    extract_bundle(bundle.source_bytes, target)
    shutil.rmtree(origin)  # No origin lookup or implicit rehydration is possible.
    return target, bundle, values, members, hidden


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('context', ['review', 'configuration'])
@pytest.mark.parametrize('route', ['python', 'cli', 'alias', 'request'])
def test_show_returns_exact_member_with_explicit_partial_scope(tmp_path, kind, context, route):
    root, bundle, values, members, hidden = extracted(tmp_path, kind, context)
    source = values[-3]
    before = inventory(root)
    with no_write_attempts():
        if route == 'python': result = show_artifact(root, source['id'])
        elif route == 'request':
            result = execute_request({'command_id': 'artifact.show', 'arguments': {'id': source['id']},
                'options': {'--project': str(root)}}).result
        else:
            command = ['artifact', 'show'] if route == 'cli' else ['show']
            result = dispatch_result([*command, source['id'], '--project', str(root)])
    assert result.exit_code == 0 and result.complete, result.as_dict()
    assert result.status.value == 'partial' and result.partial_scope == 'partial_bundle_artifacts'
    payload = result.as_dict()['result']; summary = result.as_dict()['summary']
    validate_result_document('artifact-show-v1', payload)
    assert payload['artifact'] == source
    assert payload['coverage']['scope'] == 'partial_bundle_artifacts'
    assert payload['coverage']['validation_scope'] == 'partial_payload_model'
    assert payload['coverage']['source_count'] == len(members)
    assert payload['coverage']['relation_count'] == sum(len(v['relations']) for v in members)
    assert not payload['coverage']['atomic_snapshot']
    assert summary['scope_descriptor'] == bundle.manifest['scope_descriptor']
    assert summary['boundary_references'] == bundle.manifest['boundary_references']
    assert summary['read_only'] and summary['bundle_kind'] == 'partial'
    assert not any(summary[k] for k in ('write_authorized', 'project_complete', 'origin_root_verified',
                                       'full_semantic_validation', 'approval_granted'))
    assert inventory(root) == before


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('context', ['review', 'configuration'])
def test_context_is_not_a_show_object_and_complete_reader_stays_closed(tmp_path, kind, context):
    root, bundle, values, members, hidden = extracted(tmp_path, kind, context)
    before = inventory(root)
    with no_write_attempts():
        for value in members:
            result = show_artifact(root, value['id'])
            assert result.exit_code == 0 and result.as_dict()['result']['artifact'] == value
        for value in hidden:
            result = show_artifact(root, value['id'])
            assert result.exit_code == 3 and result.as_dict()['result'] is None
        with pytest.raises(SafetyViolation): ProjectSource(root)
        result = dispatch_result(['bundle', 'create', '--scope', 'project', '--project', str(root),
                                  '--output', str(tmp_path / 'full.zip')])
    assert result.exit_code == 7 and not (tmp_path / 'full.zip').exists()
    assert inventory(root) == before


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_boundary_edge_is_visible_without_fabricated_target_or_incoming_sources(tmp_path, kind):
    root, bundle, values, members, hidden = extracted(tmp_path, kind)
    source, target = values[-3:-1]
    with no_write_attempts(): result = show_artifact(root, source['id'], strategy='scan')
    payload = result.as_dict()['result']
    relation = source['relations'][0]
    assert {'relation_id': relation['relation_id'], 'type': relation['type'],
        'source': source['id'], 'target': target['id'], 'inverse': False,
        'stored_source': source['id'], 'stored_relation': relation} in payload['outgoing']
    assert {v['relation_id'] for v in payload['outgoing']} == {r['relation_id'] for r in source['relations']}
    expected = [(v['id'], r) for v in members for r in v['relations'] if r['target'] == source['id']]
    assert {(v['target'], v['relation_id']) for v in payload['incoming']} == {
        (identifier, r['relation_id']) for identifier, r in expected}
    assert not (root / path(target)).exists() and (root / context_path(target)).exists()


@pytest.mark.parametrize('fault', ['payload', 'proof_payload', 'configuration', 'missing', 'extra', 'extra_proof'])
def test_changed_extracted_inventory_never_returns_partial_success(tmp_path, fault):
    root, bundle, values, _, _ = extracted(tmp_path)
    if fault == 'payload': put(root, path(values[-3]), b'{}')
    elif fault == 'proof_payload': put(root, context_path(values[-2]), b'{}')
    elif fault == 'configuration':
        config = json.loads((root / 'specroad.json').read_bytes()); config['project_id'] += '-changed'
        put(root, 'specroad.json', canonical_json_bytes(config))
    elif fault == 'missing': (root / path(values[-3])).unlink()
    elif fault == 'extra': put(root, path(values[-2]), canonical_json_bytes(values[-2]))
    else: put(root, context_path(values[-1]), canonical_json_bytes(values[-1]))
    before = inventory(root)
    with no_write_attempts(): result = show_artifact(root, values[-3]['id'])
    assert result.exit_code == 3 and result.as_dict()['result'] is None, result.as_dict()
    assert inventory(root) == before


@pytest.mark.parametrize('fault', ['missing_boundary', 'extra_boundary', 'relation_type', 'target', 'strong_target'])
def test_self_consistent_transport_does_not_replace_native_boundary_verification(tmp_path, fault):
    root, original, values, _, _ = extracted(tmp_path)
    boundaries = original.manifest['boundary_references']; files = original.files
    if fault == 'missing_boundary': boundaries = []
    elif fault == 'extra_boundary':
        boundaries = [*boundaries, {**boundaries[0], 'relation_id': boundaries[0]['relation_id'][:-1] + '9'}]
        boundaries.sort(key=lambda b: (b['source_id'], b['relation_id'], b['target_id']))
    elif fault == 'relation_type': boundaries[0]['relation_type'] = 'conflicts_with'
    elif fault == 'target': boundaries[0]['target_id'] = ref('REQ', '2')
    else:
        source = values[-3]; source['relations'][0]['type'] = 'depends_on'
        files[path(source)] = canonical_json_bytes(source)
    changed = BundleContainer(rebind(original, files, boundary_references=boundaries))
    # A copied root without a bootstrap proof is untrusted too. A self-consistent
    # hash list is not closure or permission to use the complete-project reader.
    shutil.rmtree(root)
    for name, raw in {**changed.files, MANIFEST_NAME: changed.manifest_bytes}.items(): put(root, name, raw)
    before = inventory(root)
    with no_write_attempts():
        result = show_artifact(root, values[-3]['id'])
        with pytest.raises(SafetyViolation): ProjectSource(root)
    assert result.exit_code == 3 and result.as_dict()['result'] is None, result.as_dict()
    assert inventory(root) == before


@pytest.mark.parametrize('fault', ['marker_removed', 'marker_changed', 'proof_changed', 'symlink', 'staging'])
def test_partial_origin_and_path_guards_fail_before_success(tmp_path, fault):
    root, _, values, _, _ = extracted(tmp_path)
    if fault == 'marker_removed': (root / MANIFEST_NAME).unlink()
    elif fault == 'marker_changed': put(root, MANIFEST_NAME, b'{}')
    elif fault == 'proof_changed': put(root, '/'.join((*COMPLETED, 'journal.json')), b'{}')
    elif fault == 'staging': (root / STAGING).mkdir()
    else:
        target = root / path(values[-3]); raw = target.read_bytes(); target.unlink()
        outside = tmp_path / 'outside'; outside.write_bytes(raw); target.symlink_to(outside)
    before = inventory(root)
    with no_write_attempts(): result = show_artifact(root, values[-3]['id'])
    assert result.exit_code == 7 and result.as_dict()['result'] is None, result.as_dict()
    assert inventory(root) == before


@pytest.mark.parametrize('fault', ['payload', 'proof_payload', 'new_member'])
def test_retained_read_rechecks_all_bytes_and_membership_before_delivery(tmp_path, fault):
    root, _, values, _, _ = extracted(tmp_path)
    with ReadCommandWork('artifact.show', root, artifact_id=values[-3]['id']) as work:
        with no_write_attempts(): assert not work.advance()
        assert work.state['phase'] == 'loaded'
        if fault == 'payload': put(root, path(values[-3]), b'{}')
        elif fault == 'proof_payload': put(root, context_path(values[-2]), b'{}')
        else: put(root, path(values[-2]), canonical_json_bytes(values[-2]))
        before = inventory(root)
        with no_write_attempts(): assert work.advance(3)
        assert work.result.exit_code == 6 and work.result.as_dict()['result'] is None
    assert inventory(root) == before


def test_closed_looking_partial_still_has_partial_status_and_no_write_capability(tmp_path):
    value = record_value('document'); origin = tmp_path / 'origin'
    inspection_project(origin, artifacts=[value])
    bundle = prepare_partial_bundle(origin, scope()); root = tmp_path / 'partial'
    extract_bundle(bundle.source_bytes, root)
    assert bundle.manifest['boundary_references'] == []
    with no_write_attempts():
        result = show_artifact(root, value['id'])
        with pytest.raises(SafetyViolation): ProjectSource(root)
    assert result.exit_code == 0 and result.status.value == 'partial'
    assert result.as_dict()['result']['coverage']['source_count'] == 1


@pytest.mark.parametrize('fault,code', [('unsafe_path', 7), ('alias', 3), ('version', 3)])
def test_untrusted_root_metadata_is_checked_before_payload_paths(tmp_path, fault, code):
    root, bundle, values, _, _ = extracted(tmp_path)
    (root.joinpath(*COMPLETED) / 'journal.json').unlink()
    manifest = bundle.manifest
    if fault == 'unsafe_path': manifest['entries'][0]['path'] = '../outside.json'
    elif fault == 'alias': manifest['bundle_kind'] = 'document'
    else: manifest['bundle_format_version'] = '9000.0.0'
    put(root, MANIFEST_NAME, canonical_json_bytes(manifest))
    before = inventory(root)
    with no_write_attempts(): result = show_artifact(root, values[-3]['id'])
    assert result.exit_code == code and result.as_dict()['result'] is None
    assert result.diagnostics[0].code == ('SRV083' if code == 7 else 'SRV003' if fault == 'version' else 'SRV002')
    assert inventory(root) == before


def test_copied_partial_without_bootstrap_proof_is_read_only_too(tmp_path):
    root, _, values, _, _ = extracted(tmp_path)
    shutil.rmtree(root / '.specroad')
    before = inventory(root)
    with no_write_attempts():
        result = show_artifact(root, values[-3]['id'])
        with pytest.raises(SafetyViolation): ProjectSource(root)
    assert result.exit_code == 0 and result.status.value == 'partial'
    assert inventory(root) == before


def test_unresolved_transaction_prevents_model_read_and_does_not_recover(tmp_path):
    root, _, values, _, _ = extracted(tmp_path)
    put(root, '.specroad/transactions/active/journal.json', b'not a trusted journal')
    put(root, path(values[-3]), b'not model bytes')
    before = inventory(root)
    with no_write_attempts(): result = show_artifact(root, values[-3]['id'])
    assert result.exit_code == 5 and result.as_dict()['result'] is None, result.as_dict()
    assert inventory(root) == before
