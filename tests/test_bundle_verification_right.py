"""15.d.R: independent partial closure and separate original endpoint proofs.

Synthetic review actors below are test fixtures, never real human approvals.
"""
from copy import deepcopy
from hashlib import sha256
import io
import json
from unittest.mock import patch
import zipfile

import pytest

from specroad.bundles import (BundleContainer, BundleError, prepare_partial_bundle,
                              prepare_project_bundle, verify_bundle)
from specroad.cli.application import dispatch_result
from specroad.cli.result_schemas import validate_result_document
from specroad.graph.review_status import RelationReviewStatuses
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.paths import artifact_path
from support.domain import domain_value
from support.inspection import inspection_project
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from test_bundle_verification import rebind
from test_partial_bundle import project, scope, save, edge, records, independent_root
from test_partial_bundle_right import configured, configuration_resources
from test_relation_review_status import review, sources


def path(value):
    return artifact_path(value['artifact_type'], value['id'], 'SR')


def context_path(value):
    return 'bundle-context/boundary-targets/' + value['id'] + '.json'


def reviewed(root, kind='document', *, decision='confirmed', change=None, force=False):
    values = project(root, kind)
    source, target = values[-3:-1]
    record = review(source, target, decision=decision)
    if force:
        # This independent strong path retains historical reviews as members.
        link = record_value('source', relations=[edge('references', record['id'], 13)])
        source['relations'].append(edge('derived_from', link['id'], 12))
        save(root, link); save(root, source)
    if change == 'audit':
        target['revision'] += 1; target['tags'] = ['audit-only']
    elif change == 'semantic':
        target['statement'] += ' Changed statement.'
    elif change == 'relation':
        source['relations'][0]['rationale'] = 'Changed rationale.'
        save(root, source)
    save(root, target); save(root, record)
    return values, record


def verify_without_origin(bundle):
    with no_write_attempts(), patch('specroad.security.ProjectBoundary.read_bytes', side_effect=AssertionError):
        value = verify_bundle(bundle.source_bytes)
    validate_result_document('bundle-verify-v1', value)
    assert value['manifest'] == bundle.manifest
    assert value['validation_scope'] == 'partial_payload_model'
    assert value['container_verified'] and value['closure_verified'] and value['model_root_verified']
    assert not any(value[key] for key in ('creator_authenticated', 'approval_granted',
                                         'write_authorized', 'full_semantic_validation'))
    return value


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('decision', ['confirmed', 'rejected'])
@pytest.mark.parametrize('change', [None, 'audit', 'semantic', 'relation'])
def test_original_endpoint_proof_recomputes_current_and_historical_reviews(tmp_path, kind, decision, change):
    root = tmp_path / 'origin'
    values, record = reviewed(root, kind, decision=decision, change=change, force=True)
    source, target = values[-3:-1]
    before = inventory(root)
    with no_write_attempts():
        bundle = prepare_partial_bundle(root, scope(kind))
    value = verify_without_origin(bundle)
    assert inventory(root) == before
    assert bundle.files[context_path(target)] == (root / path(target)).read_bytes()
    assert path(target) not in bundle.files
    assert path(target) not in {row['path'] for row in bundle.manifest['excluded_contents']}
    assert path(record) in bundle.files
    assert value['manifest']['read_only'] and value['manifest']['idempotency_scope'] == 'local_only'
    # Independently assemble the actual member model, excluding proof bytes.
    assert independent_root(tmp_path / 'oracle', bundle).sha256 == bundle.manifest['bundle_model_root_sha256']
    from specroad.bundles._partial_verification import _review_bindings
    selected = _review_bindings(records(bundle),
        {target['id']: sources(target)[0]}, bundle.manifest['boundary_references'])
    current = change in (None, 'audit')
    assert selected[source['relations'][0]['relation_id']] == ((record['id'],) if current else ())
    observed = RelationReviewStatuses(sources(*values, record)).for_relation(source['id'], record['relation_id'])
    assert observed.status == ('suspect' if not current else 'current' if decision == 'confirmed' else 'invalid')
    assert (record['target_artifact_sha256'] != bundle.manifest['boundary_references'][0]['origin_target_sha256']) == (change in ('audit', 'semantic'))


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_review_membership_is_derived_not_a_transported_currentness_claim(tmp_path, kind):
    root = tmp_path / 'origin'; values, record = reviewed(root, kind)
    original = prepare_partial_bundle(root, scope(kind))
    assert path(record) in original.files
    verify_without_origin(original)
    # Update endpoint bytes and boundary fullhash consistently, but keep a
    # review which no longer matches. The asserted old closure cannot pass.
    files = original.files; target = values[-2]; target['statement'] += ' Different.'
    files[context_path(target)] = canonical_json_bytes(target)
    boundaries = original.manifest['boundary_references']
    boundaries[0]['origin_target_sha256'] = canonical_json_sha256(target)
    with pytest.raises(BundleError) as error:
        verify_bundle(rebind(original, files, boundary_references=boundaries))
    assert error.value.exit_code == 3
    # Native regeneration now omits the historical review and unnecessary proof.
    save(root, target)
    regenerated = prepare_partial_bundle(root, scope(kind))
    assert path(record) not in regenerated.files and context_path(target) not in regenerated.files
    verify_without_origin(regenerated)


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('fault', ['missing', 'extra', 'wrong_name', 'wrong_identity', 'wrong_type',
    'schema', 'full_hash', 'native_duplicate', 'excluded_native', 'nested', 'metadata'])
def test_rehashed_transport_cannot_hide_wrong_endpoint_proof(tmp_path, kind, fault):
    values, _ = reviewed(tmp_path / 'origin', kind)
    original = prepare_partial_bundle(tmp_path / 'origin', scope(kind))
    files = original.files; target = values[-2]; cp = context_path(target); updates = {}
    if fault == 'missing':
        del files[cp]
    elif fault == 'extra':
        files[context_path(values[-1])] = canonical_json_bytes(values[-1])
    elif fault == 'wrong_name':
        files[cp.replace(target['id'], ref('REQ', '2'))] = files.pop(cp)
    elif fault == 'wrong_identity':
        data = deepcopy(target); data['id'] = ref('REQ', '2'); files[cp] = canonical_json_bytes(data)
    elif fault == 'wrong_type':
        files[cp] = canonical_json_bytes(values[-1])
    elif fault in ('schema', 'full_hash'):
        data = deepcopy(target)
        if fault == 'schema': del data['statement']
        else: data['statement'] += ' Altered.'
        files[cp] = canonical_json_bytes(data)
    elif fault == 'native_duplicate':
        files[path(target)] = files[cp]
    elif fault == 'excluded_native':
        updates['excluded_contents'] = sorted([*original.manifest['excluded_contents'],
            {'path': path(target), 'reason': 'outside_scope'}], key=lambda r: r['path'].encode())
    elif fault == 'nested':
        files[cp.replace('boundary-targets/', 'boundary-targets/nested/')] = files.pop(cp)
    else:
        files['bundle-context/metadata.json'] = b'{}'
    with no_write_attempts(), pytest.raises(BundleError) as error:
        raw = rebind(original, files, **updates)
        BundleContainer(raw)
        verify_bundle(raw)
    assert error.value.exit_code == 3
    if fault == 'full_hash': assert error.value.code == 'SRV060'


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('strong', [False, True])
def test_many_boundaries_share_one_proof_unless_target_becomes_a_member(tmp_path, kind, strong):
    root = tmp_path / 'origin'; values, first = reviewed(root, kind)
    source, target = values[-3:-1]
    second = deepcopy(source); second['id'] = ref('REQ', '2')
    second['relations'] = [edge('conflicts_with', target['id'], 6)]
    source['relations'].append(edge('depends_on', second['id'], 7))
    other_review = review(second, target, number=21)
    if strong: second['relations'].append(edge('depends_on', target['id'], 8))
    for record in (source, second, other_review): save(root, record)
    bundle = prepare_partial_bundle(root, scope(kind))
    assert len([p for p in bundle.files if p.startswith('bundle-context/')]) == (0 if strong else 1)
    assert (path(target) in bundle.files) is strong
    assert len(bundle.manifest['boundary_references']) == (0 if strong else 2)
    verify_without_origin(bundle)
    if not strong:
        boundaries = bundle.manifest['boundary_references']; boundaries[-1]['origin_target_sha256'] = 'a' * 64
        with pytest.raises(BundleError) as error: verify_bundle(rebind(bundle, boundary_references=boundaries))
        assert error.value.exit_code == 3 and error.value.code == 'SRV060'


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_strong_target_cannot_be_resolved_from_proof_namespace(tmp_path, kind):
    root = tmp_path / 'origin'; values, _ = reviewed(root, kind)
    bundle = prepare_partial_bundle(root, scope(kind)); files = bundle.files
    source, target = values[-3:-1]
    source['relations'].append(edge('depends_on', target['id'], 9))
    files[path(source)] = canonical_json_bytes(source)
    with pytest.raises(BundleError) as error: verify_bundle(rebind(bundle, files))
    assert error.value.exit_code == 3


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_proof_dependencies_and_attachments_do_not_expand_scope(tmp_path, kind):
    root = tmp_path / 'origin'; values, record = reviewed(root, kind)
    target = values[-2]
    dependent = domain_value('component')
    target['relations'].append(edge('depends_on', dependent['id'], 9))
    source = record_value('source', relations=[edge('references', ref('EVD'), 10)])
    raw = b'outside attachment'
    evidence = record_value('evidence', attachments=[{'path': 'attachments/outside.bin',
        'size': len(raw), 'media_type': 'application/octet-stream', 'sha256': sha256(raw).hexdigest()}])
    target['relations'].append(edge('derived_from', source['id'], 11))
    for value in (target, dependent, source, evidence): save(root, value)
    put(root, 'attachments/outside.bin', raw)
    bundle = prepare_partial_bundle(root, scope(kind))
    assert all(path(v) not in bundle.files for v in (target, dependent, source, evidence))
    assert 'attachments/outside.bin' not in bundle.files
    assert len(bundle.manifest['boundary_references']) == 1
    verify_without_origin(bundle)
    (root / path(dependent)).unlink()
    with pytest.raises(BundleError): prepare_partial_bundle(root, scope(kind))


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('reached', [False, True])
def test_configuration_chain_and_resource_admission_reconstructed_independently(tmp_path, kind, reached):
    root = tmp_path / 'origin'; values, chain, _ = configured(root, kind)
    dependency = domain_value('component')
    chain[-1]['relations'].append(edge('depends_on', dependency['id'], 8))
    members, attachment_path, _ = configuration_resources(root, chain[-1])
    save(root, dependency)
    if reached:
        values[-3]['relations'].append(edge('depends_on', chain[-1]['id'], 7)); save(root, values[-3])
    bundle = prepare_partial_bundle(root, scope(kind, configuration_id=chain[-1]['id']))
    verify_without_origin(bundle)
    assert (attachment_path in bundle.files) is reached
    if reached:
        files = bundle.files; del files[attachment_path]
        with pytest.raises(BundleError): verify_bundle(rebind(bundle, files))
    # Reformat context, retaining all semantic hashes and membership.
    files = bundle.files; files[path(chain[0])] = json.dumps(chain[0], indent=3).encode() + b'\n'
    assert verify_bundle(rebind(bundle, files))['model_root_verified']
    changed = deepcopy(chain[0]); changed['revision'] += 1
    files[path(chain[0])] = canonical_json_bytes(changed)
    with pytest.raises(BundleError) as error: verify_bundle(rebind(bundle, files))
    assert error.value.exit_code == 3 and error.value.code == 'SRV060'


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_configuration_target_has_two_identical_transport_roles(tmp_path, kind):
    root = tmp_path / 'origin'; values, chain, _ = configured(root, kind)
    target = chain[0]
    source = domain_value('capability', relations=[edge('conflicts_with', target['id'], 15)])
    values[-3]['relations'].append(edge('depends_on', source['id'], 16))
    record = review(source, target)
    save(root, values[-3]); save(root, source); save(root, record)
    bundle = prepare_partial_bundle(root, scope(kind, configuration_id=chain[-1]['id']))
    assert bundle.files[path(target)] == bundle.files[context_path(target)]
    verify_without_origin(bundle)
    files = bundle.files; files[context_path(target)] = json.dumps(target, indent=3).encode()
    with pytest.raises(BundleError) as error: verify_bundle(rebind(bundle, files))
    assert error.value.exit_code == 3


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('fault', ['missing_parent', 'unrelated_config', 'extra_artifact', 'extra_mapping',
                                  'boundary_missing', 'boundary_extra', 'root', 'profile'])
def test_payload_union_and_boundary_set_are_exact(tmp_path, kind, fault):
    root = tmp_path / 'origin'; values, chain, other = configured(root, kind)
    bundle = prepare_partial_bundle(root, scope(kind, configuration_id=chain[-1]['id']))
    files = bundle.files; updates = {}
    if fault == 'missing_parent': del files[path(chain[0])]
    elif fault == 'unrelated_config': files[path(other)] = (root / path(other)).read_bytes()
    elif fault == 'extra_artifact': files[path(values[-1])] = (root / path(values[-1])).read_bytes()
    elif fault == 'extra_mapping': files['mappings/inactive.json'] = (root / 'mappings/inactive.json').read_bytes()
    elif fault == 'boundary_missing': updates['boundary_references'] = []
    elif fault == 'boundary_extra':
        value = bundle.manifest['boundary_references'][0]; value['relation_id'] = 'REL-' + '9' * 26
        updates['boundary_references'] = [value]
    else: updates['bundle_model_root_sha256' if fault == 'root' else 'profile_sha256'] = 'a' * 64
    # Exclusion conflicts are independently invalid; remove those claims to
    # exercise the native exact payload union, not just the transport codec.
    updates['excluded_contents'] = [r for r in bundle.manifest['excluded_contents'] if r['path'] not in files]
    with no_write_attempts(), pytest.raises(BundleError) as error: verify_bundle(rebind(bundle, files, **updates))
    assert error.value.exit_code == 3


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_no_review_or_project_scope_rejects_unnecessary_proof(tmp_path, kind):
    root = tmp_path / 'origin'; values = project(root, kind)
    for bundle in (prepare_partial_bundle(root, scope(kind)), prepare_project_bundle(root)):
        assert not any(p.startswith('bundle-context/') for p in bundle.files)
        if bundle.manifest['bundle_kind'] == 'partial': verify_without_origin(bundle)
        with pytest.raises(BundleError) as error:
            verify_bundle(rebind(bundle, {**bundle.files, context_path(values[-2]): canonical_json_bytes(values[-2])}))
        assert error.value.exit_code == 3


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_external_hash_and_cli_preserve_read_only_partial_semantics(tmp_path, kind):
    root = tmp_path / 'origin'; values, _ = reviewed(root, kind)
    bundle = prepare_partial_bundle(root, scope(kind)); files = bundle.files
    target = values[-2]; files[context_path(target)] = json.dumps(target, indent=4).encode() + b'\n'
    changed = rebind(bundle, files)
    assert verify_bundle(changed)['model_root_verified']
    with pytest.raises(BundleError) as error: verify_bundle(changed, expected_sha256=bundle.sha256)
    assert error.value.code == 'SRV060'
    filename = tmp_path / 'input.zip'; filename.write_bytes(bundle.source_bytes)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = dispatch_result(['bundle', 'verify', str(filename), '--expected-sha256', bundle.sha256], cwd=tmp_path)
    assert result.exit_code == 0 and inventory(tmp_path) == before
    assert result.as_dict()['project'] is None
    assert result.as_dict()['result']['manifest']['read_only'] is True


@pytest.mark.filterwarnings('ignore:Duplicate name:UserWarning')
@pytest.mark.parametrize('fault', ['duplicate', 'symlink', 'directory', 'traversal', 'unlisted', 'bitflip'])
def test_zip_safety_and_inventory_precede_model_success(tmp_path, fault):
    root = tmp_path / 'origin'; values, _ = reviewed(root)
    bundle = prepare_partial_bundle(root, scope()); cp = context_path(values[-2])
    stream = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(bundle.source_bytes)) as original, zipfile.ZipFile(stream, 'w') as output:
        for info in original.infolist():
            raw = original.read(info.filename)
            if info.filename == cp and fault == 'symlink': info.external_attr = (0o120777 << 16)
            if info.filename == cp and fault == 'bitflip': raw = raw[:-1] + b'X'
            output.writestr(info, raw)
        if fault in ('duplicate', 'directory', 'traversal', 'unlisted'):
            name = {'duplicate': cp, 'directory': 'bundle-context/', 'traversal': '../escape',
                    'unlisted': 'bundle-context/extra.json'}[fault]
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)); info.create_system = 3
            info.external_attr = (0o040755 if fault == 'directory' else 0o100644) << 16
            output.writestr(info, b'{}')
    with no_write_attempts(), pytest.raises(BundleError) as error: verify_bundle(stream.getvalue())
    assert error.value.exit_code == (7 if fault in ('duplicate', 'symlink', 'directory', 'traversal') else 3)


@pytest.mark.parametrize('kind', ['baseline', 'attachment', 'packages', 'empty_release', 'release_seeds'])
def test_native_resource_and_seed_variants_are_independently_verified(tmp_path, kind):
    root = tmp_path / 'origin'
    if kind == 'baseline':
        from test_project_bundle import baseline_project
        op = baseline_project(root)
        save(root, record_value('document', relations=[edge('contains', ref('SEC'), 8)]))
        save(root, record_value('section', relations=[edge('contains', ref('BLOCK'), 9)]))
        save(root, record_value('content_block', block_kind='artifact_ref', payload={'render_mode': 'full'},
                               relations=[edge('references', op['record']['id'], 10)]))
    elif kind == 'attachment':
        values = project(root)
        raw = b'\x00 required evidence \xff'
        evidence = record_value('evidence', attachments=[{'path': 'attachments/selected.bin',
            'size': len(raw), 'media_type': 'application/octet-stream', 'sha256': sha256(raw).hexdigest()}])
        put(root, 'attachments/selected.bin', raw); save(root, evidence)
        save(root, record_value('content_block', block_kind='artifact_ref', payload={'render_mode': 'full'},
                               relations=[edge('references', evidence['id'], 3)]))
    elif kind == 'packages':
        assert dispatch_result(['init', str(root)]).exit_code == 0
        save(root, record_value('document'))
    elif kind == 'release_seeds':
        values = project(root, 'release')
        milestone = domain_value('milestone', relations=[edge('part_of', values[0]['id'], 6)])
        task = domain_value('task', relations=[edge('part_of', milestone['id'], 7)])
        capability = domain_value('capability', relations=[edge('scheduled_for', milestone['id'], 8)])
        for value in (milestone, task, capability): save(root, value)
    else:
        inspection_project(root, artifacts=[domain_value('release')])
    bundle = prepare_partial_bundle(root, scope('release' if kind in ('empty_release', 'release_seeds') else 'document'))
    verify_without_origin(bundle)
    if kind in ('baseline', 'attachment', 'packages'):
        files = bundle.files
        prefix = {'baseline': 'archive/objects/', 'attachment': 'attachments/',
                  'packages': 'profiles/language-data/packages/'}[kind]
        candidates = [p for p in files if p.startswith(prefix)]; assert candidates
        del files[candidates[0]]
        with pytest.raises(BundleError) as error: verify_bundle(rebind(bundle, files))
        assert error.value.exit_code == 3


@pytest.mark.parametrize('fault', ['missing', 'cycle', 'invalid_selection', 'excluded_anchor', 'excluded_dependency'])
def test_configuration_errors_cannot_pass_with_forged_hashes(tmp_path, fault):
    from support.srx import binary, expression_document, field, literal
    root = tmp_path / 'origin'; values, chain, _ = configured(root)
    bundle = prepare_partial_bundle(root, scope(configuration_id=chain[-1]['id'])); files = bundle.files
    if fault == 'missing':
        del files[path(chain[-1])]
    elif fault in ('cycle', 'invalid_selection'):
        data = deepcopy(chain[0])
        if fault == 'cycle': data['parent'] = chain[-1]['id']
        else: data['selection'] = {'platform': 'not-allowed'}
        files[path(data)] = canonical_json_bytes(data)
    else:
        target = values[0] if fault == 'excluded_anchor' else values[-3]
        data = deepcopy(target)
        data['applicability'] = expression_document(binary('eq', field('/effective_values/platform', 'configuration'), literal('windows')))
        files[path(data)] = canonical_json_bytes(data)
    with pytest.raises(BundleError) as error: verify_bundle(rebind(bundle, files))
    assert error.value.exit_code == 3


def test_partial_inventory_cannot_certify_full_origin_or_different_scope():
    from specroad.graph.scope_inputs import ScopeSeedInputs
    from specroad.graph.scope_seeds import resolve_scope_seeds
    from specroad.graph.scope_closure import resolve_scope_closure, verify_partial_scope_closure
    from specroad.graph.closure_inputs import ClosureBindings, artifact_node
    from specroad.model.configuration import ProjectConfiguration
    from specroad.model.errors import ModelError
    from support.model import configuration_value
    from support.scopes import descriptor
    from specroad.graph.scope_descriptors import ScopeDescriptor
    record = record_value('document')
    inputs = ScopeSeedInputs(ProjectConfiguration(configuration_value()), sources(record), partial_descriptor=scope())
    bindings = ClosureBindings(inputs, uses={artifact_node(record['id']): ()}, current_reviews={})
    seeds = resolve_scope_seeds(scope(), inputs)
    assert verify_partial_scope_closure(seeds, bindings, []).artifact_ids == (record['id'],)
    with pytest.raises(ModelError): resolve_scope_closure(seeds, bindings)
    other = resolve_scope_seeds(ScopeDescriptor(descriptor('project')), inputs)
    with pytest.raises(ModelError): verify_partial_scope_closure(other, bindings, [])
    with pytest.raises(ModelError):
        ScopeSeedInputs(ProjectConfiguration(configuration_value()), sources(record),
                        partial_descriptor=ScopeDescriptor(descriptor('project')))


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_proof_target_own_attachment_is_not_a_resource_or_history_provider(tmp_path, kind):
    root = tmp_path / 'origin'; values = project(root, kind)
    raw = b'outside proof attachment'
    target = record_value('evidence', attachments=[{'path': 'attachments/proof-only.bin', 'size': len(raw),
        'sha256': sha256(raw).hexdigest(), 'media_type': 'application/octet-stream'}])
    source = domain_value('capability', relations=[edge('conflicts_with', target['id'], 14)])
    values[-3]['relations'].append(edge('depends_on', source['id'], 15))
    record = review(source, target)
    for value in (target, source, values[-3], record): save(root, value)
    put(root, 'attachments/proof-only.bin', raw)
    bundle = prepare_partial_bundle(root, scope(kind))
    assert context_path(target) in bundle.files and path(target) not in bundle.files
    assert 'attachments/proof-only.bin' not in bundle.files
    verify_without_origin(bundle)
    (root / 'attachments/proof-only.bin').unlink()
    with pytest.raises(BundleError): prepare_partial_bundle(root, scope(kind))
