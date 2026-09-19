"""R-23 regressions: indirect/control bindings, partial readers and portability."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from specroad.graph.boundary_validation import validate_boundary_references
from specroad.graph.closure_inputs import ClosureBindings, artifact_node as A, resource_node as R
from specroad.graph.scope_admission import (
    ScopeControlDependencyError, excludes_control_artifacts, require_artifact_admissible)
from specroad.graph.scope_closure import resolve_scope_closure, require_scope_closure_current
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_inputs import ScopeResource
from specroad.graph.scope_query_page import QuerySeedPage
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.model.artifact_types import artifact_types
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.identity_values import artifact_identity
from support.boundary import selection
from support.closure import observe, source, subject
from support.model import configuration_value
from support.relations import artifact, aid, edge, rid
from support.scopes import inputs, descriptor, query
from support.portable import build_distribution


def controlled(inventory, policy='closed', **options):
    return resolve_scope_closure(selection(inventory, kind='specification', policy=policy),
                                 observe(inventory, **options))


class ScopeControlRightTests(unittest.TestCase):
    def failure(self, inventory, policy='closed'):
        with self.assertRaises(ScopeControlDependencyError) as raised:
            controlled(inventory, policy)
        self.assertEqual(raised.exception.exit_code, 3)
        return raised.exception.diagnostic()

    def test_transitive_document_composition_does_not_readmit_controls(self):
        for kind in ('proposal', 'baseline'):
            inventory = inputs(
                artifact('document', relations=[edge('contains', aid('section'))]),
                artifact('section', relations=[edge('contains', aid('content_block'), number=2)]),
                artifact('content_block', relations=[edge('references', aid(kind), number=3)]),
                artifact(kind))
            diagnostic = self.failure(inventory)
            self.assertEqual(diagnostic['source_id'], aid('content_block'))
            self.assertEqual(diagnostic['target_id'], aid(kind))
            self.assertEqual(diagnostic['relation_id'], rid(3))

    def test_long_reference_chain_terminates_with_control_diagnostic(self):
        values = [artifact('view', number=n, relations=[edge('references', aid('view', n+1), number=n)])
                  for n in range(1, 1100)]
        values += [artifact('view', number=1100, relations=[edge('references', aid('proposal'), number=1100)]),
                   artifact('proposal')]
        diagnostic = self.failure(inputs(*values))
        self.assertEqual(diagnostic['source_id'], aid('view', 1100))
        self.assertEqual(diagnostic['relation_id'], rid(1100))

    def test_control_subject_reached_through_evidence_is_mandatory(self):
        ev = source('evidence', subjects=[subject(aid('baseline'))], attachments=[])
        test = artifact('test', relations=[edge('produces', ev['id'])])
        diagnostic = self.failure(inputs(test, ev, artifact('baseline')), 'partial')
        self.assertEqual(diagnostic['source_id'], ev['id'])
        self.assertEqual(diagnostic['pointer'], '/subjects/0/artifact_id')
        self.assertIsNone(diagnostic['relation_id'])

    def test_relation_error_uses_identity_order_and_original_field_position(self):
        links = [edge('references', aid('proposal', 2), number=2), edge('references', aid('proposal'), number=1)]
        first = inputs(artifact('view', relations=links), artifact('proposal'), artifact('proposal', 2))
        second = inputs(artifact('proposal', 2), artifact('view', relations=list(reversed(links))), artifact('proposal'))
        one, two = self.failure(first), self.failure(second)
        self.assertEqual(one['relation_id'], two['relation_id'])
        self.assertEqual(one['relation_id'], rid())
        self.assertEqual(one['target_id'], two['target_id'])
        self.assertEqual(one['pointer'], '/relations/1/target')
        self.assertEqual(two['pointer'], '/relations/0/target')

    def test_error_is_independent_of_supplied_source_order(self):
        records = [artifact('view', 2, relations=[edge('references', aid('baseline'), number=2)]),
                   artifact('content_block', relations=[edge('references', aid('proposal'))]),
                   artifact('baseline'), artifact('proposal')]
        self.assertEqual(self.failure(inputs(*records)), self.failure(inputs(*reversed(records))))

    def test_new_control_dependency_invalidates_previous_success_without_fallback(self):
        before = inputs(artifact('view'), artifact('proposal'))
        old = controlled(before)
        after = inputs(artifact('view', relations=[edge('references', aid('proposal'))]), artifact('proposal'))
        with self.assertRaises(ScopeControlDependencyError):
            require_scope_closure_current(old, selection(after, kind='specification', policy='closed'), observe(after))

    def test_control_writes_leave_non_control_member_projection_unchanged(self):
        values = [artifact(), artifact('proposal'), artifact('baseline')]
        first = controlled(inputs(*values))
        changed = deepcopy(values)
        changed[1].update(revision=5, maturity='rejected', title='Control only')
        changed[2].update(revision=4, title='Archived control only')
        second = controlled(inputs(*changed))
        self.assertEqual(canonical_json_sha256([m.data for m in first.members]),
                         canonical_json_sha256([m.data for m in second.members]))
        self.assertNotEqual(first.observation_sha256, second.observation_sha256)

    def test_unused_control_archive_is_not_promoted_by_inventory_presence(self):
        resource = ScopeResource('archive:control', 'archive', 'a'*64)
        inv = inputs(artifact(), artifact('baseline'), resources=[resource],
                     archive_bindings={aid('baseline'): ['archive:control']})
        self.assertEqual(controlled(inv).resource_ids, ())

    def test_project_reference_to_baseline_still_requires_archive_observation(self):
        inv = inputs(artifact('view', relations=[edge('references', aid('baseline'))]), artifact('baseline'))
        with self.assertRaises(ModelError) as raised:
            resolve_scope_seeds(ScopeDescriptor(descriptor('project')), inv)
        self.assertEqual(raised.exception.reason, 'scope_baseline_archive_inventory_required')

    def test_partial_omitted_control_outgoing_dependencies_are_not_traversed(self):
        inv = inputs(artifact(relations=[edge('conflicts_with', aid('proposal'))]),
                     artifact('proposal', relations=[edge('conflicts_with', aid('baseline'), number=2)]),
                     artifact('baseline'))
        result = controlled(inv, 'partial')
        self.assertEqual(result.artifact_ids, (aid(),))
        self.assertEqual(len(result.boundary_references), 1)
        self.assertEqual(result.boundary_references[0].data['target_id'], aid('proposal'))

    def test_partial_boundary_hash_tracks_control_content(self):
        value = artifact(relations=[edge('conflicts_with', aid('baseline'))])
        one = controlled(inputs(value, artifact('baseline')), 'partial')
        two = controlled(inputs(value, artifact('baseline', revision=2)), 'partial')
        self.assertEqual(one.members, two.members)
        self.assertNotEqual(one.boundary_references, two.boundary_references)

    def test_strong_dependency_cannot_hide_behind_existing_partial_weak_edge(self):
        inv = inputs(artifact('view', relations=[edge('conflicts_with', aid('proposal')),
                                               edge('references', aid('proposal'), number=2)]), artifact('proposal'))
        diagnostic = self.failure(inv, 'partial')
        self.assertEqual(diagnostic['relation_id'], rid(2))

    def test_plain_configured_specification_uses_same_admission_policy(self):
        desc = ScopeDescriptor(descriptor(configuration_id=aid('configuration')))
        with self.assertRaises(ScopeControlDependencyError):
            require_artifact_admissible(desc, artifact_identity(artifact('baseline')),
                                       source_id=aid('view'), relation_id=rid())

    def test_every_non_control_artifact_type_is_admissible(self):
        desc = ScopeDescriptor(descriptor())
        for item in artifact_types():
            if item.artifact_type not in ('proposal', 'baseline'):
                require_artifact_admissible(desc, artifact_identity(artifact(item.artifact_type)))

    def test_guard_does_not_accept_raw_unvalidated_identity(self):
        with self.assertRaises(ModelError) as raised:
            require_artifact_admissible(ScopeDescriptor(descriptor()), artifact('proposal'))
        self.assertEqual(raised.exception.reason, 'artifact_identity_required')

    def test_guard_does_not_accept_raw_descriptor(self):
        with self.assertRaises(ModelError):
            excludes_control_artifacts(descriptor())

    def test_control_cannot_be_mislabelled_as_current_review(self):
        inv = inputs(artifact(relations=[edge('conflicts_with', aid('proposal'))]), artifact('proposal'))
        with self.assertRaises(ModelError):
            observe(inv, reviews={rid(): [aid('proposal')]})

    def test_resource_identifier_resembling_control_id_is_not_an_artifact(self):
        resource = ScopeResource(aid('proposal'), 'rule', 'a'*64, '1', active=True)
        inv = inputs(artifact(), resources=[resource])
        result = controlled(inv)
        self.assertEqual(result.artifact_ids, (aid(),))
        self.assertEqual(result.resource_ids, (aid('proposal'),))

    def test_resource_cannot_replace_a_missing_subject_artifact(self):
        resource = ScopeResource(aid('proposal'), 'rule', 'a'*64, '1')
        ev = source('evidence', subjects=[subject(aid('proposal'))], attachments=[])
        with self.assertRaises(ModelError) as raised:
            controlled(inputs(ev, resources=[resource]))
        self.assertEqual(raised.exception.reason, 'closure_bound_artifact_missing')

    def test_active_resource_is_retained_despite_unrelated_controls(self):
        resource = ScopeResource('profile:active', 'profile', 'a'*64, '1', active=True)
        result = controlled(inputs(artifact(), artifact('proposal'), artifact('baseline'), resources=[resource]))
        self.assertEqual(result.resource_ids, ('profile:active',))

    def test_partial_reader_rejects_local_control_even_without_relation(self):
        inv = inputs(artifact('proposal'))
        for policy in ('closed', 'partial'):
            with self.assertRaises(ScopeControlDependencyError) as raised:
                validate_boundary_references(inv.records, (),
                    descriptor=ScopeDescriptor(descriptor(boundary_policy=policy)))
            self.assertEqual(raised.exception.diagnostic()['target_id'], aid('proposal'))
            self.assertEqual(raised.exception.pointer, '/sources/0/id')

    def test_partial_reader_allows_control_as_omitted_origin_target(self):
        inv = inputs(artifact(relations=[edge('conflicts_with', aid('proposal'))]), artifact('proposal'))
        result = controlled(inv, 'partial')
        local = [record for record in inv.records if record.identity.id == aid()]
        check = validate_boundary_references(local, result.boundary_references,
                    descriptor=result.seeds.descriptor, origin_sources=inv.records)
        self.assertTrue(check.origin_hashes_verified)
        self.assertEqual(len(check.boundary_references), 1)

    def test_partial_reader_applies_guard_to_configuration_wrapper(self):
        desc = ScopeDescriptor(descriptor('configuration', {'base_scope_descriptor': descriptor()},
                                           configuration_id=aid('configuration')))
        with self.assertRaises(ScopeControlDependencyError):
            validate_boundary_references(inputs(artifact('baseline')).records, (), descriptor=desc)

    def test_partial_reader_does_not_exclude_project_controls(self):
        inv = inputs(artifact('proposal'))
        result = validate_boundary_references(inv.records, (), descriptor=ScopeDescriptor(descriptor('project')))
        self.assertEqual(result.source_ids, (aid('proposal'),))

    def test_query_scope_may_select_control_without_specification_rule(self):
        inv = inputs(artifact('proposal'))
        desc = ScopeDescriptor(descriptor('query', {'query': query()}))
        page = QuerySeedPage(desc, inv, [aid('proposal')], total=1)
        seeds = resolve_scope_seeds(desc, inv, query_page=page)
        result = resolve_scope_closure(seeds, observe(inv), query_page=page)
        self.assertEqual(result.artifact_ids, (aid('proposal'),))

    def test_error_has_no_unrelated_confidential_text(self):
        inv = inputs(artifact('view', title='CONFIDENTIAL-TITLE',
                              relations=[edge('references', aid('proposal'), rationale='CONFIDENTIAL-REASON')]),
                     artifact('proposal', title='CONFIDENTIAL-PROPOSAL'))
        diagnostic = self.failure(inv)
        self.assertFalse(any('CONFIDENTIAL' in str(value) for value in diagnostic.values()))

    def test_repeated_rejection_is_stable_without_state_change(self):
        inv = inputs(artifact('view', relations=[edge('references', aid('proposal'))]), artifact('proposal'))
        before = inv.fingerprint
        self.assertEqual(self.failure(inv), self.failure(inv))
        self.assertEqual(before, inv.fingerprint)

    def test_locale_and_timezone_do_not_modify_admission(self):
        inv = inputs(artifact('view', relations=[edge('references', aid('proposal'))]), artifact('proposal'))
        before = self.failure(inv)
        with patch.dict(os.environ, {'LANG': 'tr_TR.UTF-8', 'LC_ALL': 'ar_EG.UTF-8', 'TZ': 'Pacific/Auckland'}):
            self.assertEqual(self.failure(inv), before)

    def test_partial_reader_control_source_is_not_allowed_via_self_contained_list(self):
        inv = inputs(artifact('view', relations=[edge('references', aid('proposal'))]), artifact('proposal'))
        with self.assertRaises(ScopeControlDependencyError):
            validate_boundary_references(inv.records, (), descriptor=ScopeDescriptor(descriptor()))

    def test_portable_distributions_preserve_control_diagnostic_and_no_writes(self):
        raw = [artifact('view', relations=[edge('references', aid('proposal'))]), artifact('proposal')]
        code = '''
import sys,json,pathlib
sys.path.insert(0,sys.argv[1])
from specroad.model.configuration import ProjectConfiguration
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_inputs import ScopeSeedInputs
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.graph.closure_inputs import ClosureBindings,artifact_node
from specroad.graph.scope_closure import resolve_scope_closure
from specroad.graph.scope_admission import ScopeControlDependencyError
configuration,raw,descriptor=json.loads(sys.argv[2])
records=[SourceRelations(json.dumps(value).encode()) for value in raw]
inventory=ScopeSeedInputs(ProjectConfiguration(configuration),records)
bindings=ClosureBindings(inventory,uses={artifact_node(r.identity.id):() for r in records},
    current_reviews={raw[0]['relations'][0]['relation_id']:()})
try:
    resolve_scope_closure(resolve_scope_seeds(ScopeDescriptor(descriptor),inventory),bindings)
except ScopeControlDependencyError as error:
    assert error.code=='SRV140' and error.exit_code==3
    assert error.source_id==raw[0]['id'] and error.target_id==raw[1]['id']
    assert error.relation_id==raw[0]['relations'][0]['relation_id']
    raise SystemExit(error.exit_code)
raise SystemExit(99)
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); built = root/'built'; build_distribution(built); moved = root/'moved'; built.rename(moved)
            data = json.dumps([configuration_value(), raw, descriptor()])
            empty = root/'cwd'; empty.mkdir()
            for distribution in (moved/'module', moved/'specroad.pyz'):
                proc = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code, str(distribution), data],
                    cwd=empty, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
                self.assertEqual(proc.returncode, 3, proc.stderr.decode())
                self.assertEqual(list(empty.iterdir()), [])
