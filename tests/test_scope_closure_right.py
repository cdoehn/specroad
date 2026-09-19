"""Mixed-edge fixed points, fresh observations, provider failures and portability."""
from dataclasses import replace
from pathlib import Path
import itertools
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from specroad.graph.closure_inputs import ClosureBindings, artifact_node as A, resource_node as R
from specroad.graph.scope_closure import resolve_scope_closure, require_scope_closure_current
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_inputs import ScopeResource
from specroad.graph.scope_seeds import ScopeSeeds, QuerySeedPage, resolve_scope_seeds
from specroad.model.errors import ModelError
from support.boundary import selection
from support.closure import observe, source
from support.relations import artifact, aid, edge, rid
from support.scopes import inputs, descriptor, query
from support.portable import build_distribution


class ScopeClosureRightTests(unittest.TestCase):
    def test_all_three_node_mixed_dags_match_independent_membership_and_boundary_oracle(self):
        pairs = [(0, 1), (0, 2), (1, 2)]
        # Each possible edge is absent, strong, duplicates or conflicts_with.
        for labels in itertools.product((None, 'depends_on', 'duplicates', 'conflicts_with'), repeat=3):
            graph = [(a, b, label, i+1) for i, ((a, b), label) in enumerate(zip(pairs, labels)) if label]
            inventory = inputs(*(artifact(number=a+1, relations=[edge(label, aid(number=b+1), number=i)
                for left, b, label, i in graph if left == a]) for a in range(3)))
            for seed in range(3):
                for policy in ('closed', 'partial'):
                    reached = {seed}
                    while True:
                        expanded = reached | {b for a, b, label, _ in graph
                            if a in reached and (policy == 'closed' or label == 'depends_on')}
                        if expanded == reached: break
                        reached = expanded
                    expected_boundary = {(aid(number=a+1), rid(i), aid(number=b+1))
                        for a, b, label, i in graph if policy == 'partial' and a in reached
                        and b not in reached and label != 'depends_on'}
                    result = resolve_scope_closure(selection(inventory, [aid(number=seed+1)], policy=policy), observe(inventory))
                    self.assertEqual(set(result.artifact_ids), {aid(number=a+1) for a in reached})
                    self.assertEqual({item.key for item in result.boundary_references}, expected_boundary)
                    self.assertEqual(len(result.processing_order), len(reached))

    def test_deep_weak_chain_is_iterative(self):
        size = 1100
        inventory = inputs(*(artifact(number=n, relations=[edge('duplicates', aid(number=n+1), number=n)] if n < size else [])
                             for n in range(1, size+1)))
        result = resolve_scope_closure(selection(inventory, [aid()], policy='closed'), observe(inventory))
        self.assertEqual(len(result.artifact_ids), size)
        self.assertEqual(len(result.processing_order), size)

    def test_wide_partial_boundaries_are_not_truncated_at_display_limit(self):
        size = 141
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=n), number=n) for n in range(2, size+2)]),
                           *(artifact(number=n) for n in range(2, size+2)))
        result = resolve_scope_closure(selection(inventory, [aid()]), observe(inventory))
        self.assertEqual(len(result.boundary_references), size)

    def test_closed_weak_then_strong_missing_usage_is_an_error(self):
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2))
        binding = ClosureBindings(inventory, uses={A(aid()): ()}, current_reviews={rid(): ()})
        with self.assertRaises(ModelError) as error:
            resolve_scope_closure(selection(inventory, [aid()], policy='closed'), binding)
        self.assertEqual(error.exception.reason, 'closure_usage_observation_missing')

    def test_partial_does_not_require_usage_for_omitted_target(self):
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2))
        binding = ClosureBindings(inventory, uses={A(aid()): ()}, current_reviews={rid(): ()})
        self.assertEqual(len(resolve_scope_closure(selection(inventory, [aid()]), binding).boundary_references), 1)

    def test_missing_review_observation_is_not_a_boundary_fallback(self):
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2))
        binding = ClosureBindings(inventory, uses={A(aid()): ()}, current_reviews={})
        with self.assertRaises(ModelError): resolve_scope_closure(selection(inventory, [aid()]), binding)

    def test_stale_seeds_are_rejected_before_policy_evaluation(self):
        inventory = inputs(artifact()); seeds = selection(inventory, [aid()])
        changed = inputs(artifact(revision=2))
        with self.assertRaises(ModelError): resolve_scope_closure(seeds, observe(changed))

    def test_forged_seed_subset_is_rejected(self):
        inventory = inputs(artifact(), artifact(number=2)); seeds = selection(inventory, kind='project')
        with self.assertRaises(ModelError): resolve_scope_closure(replace(seeds, artifact_ids=(aid(),)), observe(inventory))

    def test_configuration_without_resolver_does_not_succeed_unfiltered(self):
        inventory = inputs(artifact(), artifact('configuration'))
        desc = ScopeDescriptor(descriptor('explicit', {'artifact_ids': [aid()], 'resource_ids': []}, configuration_id=aid('configuration')))
        seeds = ScopeSeeds(desc, inventory.fingerprint, (aid(),), (), 'a'*64)
        with self.assertRaises(ModelError): resolve_scope_closure(seeds, observe(inventory))

    def test_specification_closed_weak_control_target_remains_blocked(self):
        inventory = inputs(artifact(relations=[edge('conflicts_with', aid('proposal'))]), artifact('proposal'))
        with self.assertRaises(ModelError) as error:
            resolve_scope_closure(selection(inventory, kind='specification', policy='closed'), observe(inventory))
        self.assertEqual(error.exception.reason, 'scope_control_dependency')

    def test_specification_partial_keeps_weak_control_target_outside(self):
        inventory = inputs(artifact(relations=[edge('conflicts_with', aid('proposal'))]), artifact('proposal'))
        result = resolve_scope_closure(selection(inventory, kind='specification'), observe(inventory))
        self.assertNotIn(aid('proposal'), result.artifact_ids)
        self.assertEqual(result.boundary_references[0].data['target_id'], aid('proposal'))

    def test_same_observation_is_accepted_against_same_supplied_inputs(self):
        inventory = inputs(artifact()); seeds = selection(inventory, [aid()]); binding = observe(inventory)
        result = resolve_scope_closure(seeds, binding)
        require_scope_closure_current(result, seeds, binding)

    def test_missing_member_in_old_observation_is_rejected(self):
        inventory = inputs(artifact()); seeds = selection(inventory, [aid()]); binding = observe(inventory)
        result = resolve_scope_closure(seeds, binding)
        with self.assertRaises(ModelError): require_scope_closure_current(replace(result, artifact_ids=()), seeds, binding)

    def test_forged_missing_boundary_is_rejected(self):
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2))
        seeds = selection(inventory, [aid()]); binding = observe(inventory); result = resolve_scope_closure(seeds, binding)
        with self.assertRaises(ModelError): require_scope_closure_current(replace(result, boundary_references=()), seeds, binding)

    def test_changed_origin_target_invalidates_existing_observation(self):
        before = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2))
        old = resolve_scope_closure(selection(before, [aid()]), observe(before))
        after = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2, revision=2))
        with self.assertRaises(ModelError): require_scope_closure_current(old, selection(after, [aid()]), observe(after))

    def test_changed_boundary_policy_invalidates_observation(self):
        inventory = inputs(artifact()); old = resolve_scope_closure(selection(inventory, [aid()]), observe(inventory))
        with self.assertRaises(ModelError): require_scope_closure_current(old, selection(inventory, [aid()], policy='closed'), observe(inventory))

    def test_query_page_order_is_preserved_while_final_membership_is_sorted(self):
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=3))]), artifact(number=2), artifact(number=3))
        desc = ScopeDescriptor(descriptor('query', {'query': query(limit=2)}, boundary_policy='partial'))
        page = QuerySeedPage(desc, inventory, [aid(number=2), aid()], total=3)
        seeds = resolve_scope_seeds(desc, inventory, query_page=page)
        result = resolve_scope_closure(seeds, observe(inventory), query_page=page)
        self.assertEqual(result.seeds.artifact_ids, (aid(number=2), aid()))
        self.assertEqual(result.artifact_ids, (aid(), aid(number=2)))
        self.assertEqual(len(result.boundary_references), 1)

    def test_missing_query_page_is_not_an_empty_success(self):
        inventory = inputs(artifact()); desc = ScopeDescriptor(descriptor('query', {'query': query()}))
        page = QuerySeedPage(desc, inventory, [aid()], total=1)
        with self.assertRaises(ModelError): resolve_scope_closure(resolve_scope_seeds(desc, inventory, query_page=page), observe(inventory))

    def test_attachment_is_never_replaced_by_weak_boundary(self):
        from support.closure import subject
        evidence = source('evidence', subjects=[subject(aid())], attachments=[
            {'path': 'attachments/no.bin', 'media_type': 'application/octet-stream', 'size': 1, 'sha256': 'a'*64}])
        inventory = inputs(artifact(relations=[edge('conflicts_with', evidence['id'])]), evidence)
        with self.assertRaises(ModelError):
            resolve_scope_closure(selection(inventory, [aid()], policy='closed'), observe(inventory))

    def test_locale_and_timezone_do_not_change_boundaries_or_membership(self):
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2))
        seeds = selection(inventory, [aid()]); binding = observe(inventory); original = resolve_scope_closure(seeds, binding)
        with patch.dict(os.environ, {'LANG': 'tr_TR.UTF-8', 'LC_ALL': 'ar_EG.UTF-8', 'TZ': 'Pacific/Auckland'}):
            self.assertEqual(resolve_scope_closure(seeds, binding), original)

    def test_portable_module_and_zipapp_resolve_and_validate_boundaries(self):
        from support.model import configuration_value
        raw = [artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2)]
        code = '''
import sys,json
sys.path.insert(0,sys.argv[1])
from specroad.model.configuration import ProjectConfiguration
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_inputs import ScopeSeedInputs
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.graph.closure_inputs import ClosureBindings,artifact_node
from specroad.graph.scope_closure import resolve_scope_closure
from specroad.graph.boundary_validation import validate_boundary_references
configuration,raw,descriptor=json.loads(sys.argv[2])
records=[SourceRelations(json.dumps(value).encode()) for value in raw]
inputs=ScopeSeedInputs(ProjectConfiguration(configuration),records)
bindings=ClosureBindings(inputs,uses={artifact_node(r.identity.id):() for r in records},current_reviews={raw[0]['relations'][0]['relation_id']:()})
seeds=resolve_scope_seeds(ScopeDescriptor(descriptor),inputs)
result=resolve_scope_closure(seeds,bindings)
assert result.artifact_ids==(raw[0]['id'],) and len(result.boundary_references)==1
checked=validate_boundary_references([records[0]],[item.data for item in result.boundary_references],descriptor=seeds.descriptor,origin_sources=records)
assert checked.origin_hashes_verified and len(checked.boundary_references)==1
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); built = root/'built'; build_distribution(built); moved = root/'moved'; built.rename(moved)
            data = json.dumps([configuration_value(), raw, descriptor('explicit', {'artifact_ids': [aid()], 'resource_ids': []}, boundary_policy='partial')])
            for distribution in (moved/'module', moved/'specroad.pyz'):
                proc = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code, str(distribution), data],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
                self.assertEqual(proc.returncode, 0, proc.stderr.decode())
