"""Explicit profile minima and the exact Appendix J review-context boundary."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.graph.relation_obligations import RelationObligations, MinimumRelationRule
from specroad.graph.review_contexts import EndpointReviewContext, RelationReviewContext, relation_content_sha256
from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from support.artifacts import artifact_bytes
from support.relations import artifact, aid, edge, rid, external
from support.portable import build_distribution, files_under
from support import run_python
from test_relation_obligations import sources, satisfied_fixture


def rule(**overrides):
    args = dict(rule_id='profile:minimum', artifact_types=('requirement',),
                relation_types=('depends_on',), minimum=1)
    args.update(overrides)
    return MinimumRelationRule(**args)


class ProfileObligationTests(unittest.TestCase):
    def test_orphan_minima_apply_by_type_and_maturity(self):
        records = sources(artifact(), artifact(number=2, maturity='proposed'), artifact('component'))
        result = RelationObligations(records, profile_rules=[rule(maturities=('proposed',))])
        self.assertEqual([x.artifact_id for x in result.checks], [aid(number=2)])
        self.assertEqual(result.diagnostics[0]['reason'], 'missing_required_relation')

    def test_every_core_maturity_can_be_used_as_profile_filter(self):
        for maturity in ('draft','proposed','in_review','approved','rejected','superseded','retired'):
            with self.subTest(maturity=maturity):
                result=RelationObligations(sources(artifact('component',maturity=maturity)),
                    profile_rules=[rule(artifact_types=('component',),maturities=(maturity,))])
                self.assertEqual(len(result.checks),1)
                self.assertFalse(result.checks[0].satisfied)

    def test_severity_is_preserved_without_granting_approval(self):
        for severity in ('info', 'warning', 'error'):
            with self.subTest(severity=severity):
                result = RelationObligations(sources(artifact()), profile_rules=[rule(severity=severity)])
                self.assertEqual(result.diagnostics[0]['severity'], severity)
                self.assertEqual(result.has_errors, severity=='error')
                self.assertFalse(result.requirements_satisfied)
                self.assertFalse(result.approval_granted)

    def test_profiles_cannot_remove_or_weaken_core_minima(self):
        result = RelationObligations(sources(artifact(maturity='approved')),
                                     profile_rules=[rule(minimum=0, severity='info')])
        self.assertEqual(len(result.diagnostics), 2)
        self.assertTrue(result.has_errors)
        self.assertTrue(all(x['rule_id'].startswith('core:') for x in result.diagnostics))

    def test_profile_id_cannot_impersonate_core(self):
        for value in ('core:requirement-origin', 'core:requirement-verification', 'core:new'):
            with self.subTest(value=value), self.assertRaises(ModelError): rule(rule_id=value)

    def test_endpoint_types_filter_opposite_end(self):
        records = sources(artifact(relations=[edge('depends_on', aid('component'))]), artifact('component'))
        good = RelationObligations(records, profile_rules=[rule(endpoint_types=('component',))])
        bad = RelationObligations(records, profile_rules=[rule(endpoint_types=('requirement',))])
        self.assertTrue(good.requirements_satisfied)
        self.assertFalse(bad.requirements_satisfied)

    def test_incoming_task_implementation_uses_stored_edge(self):
        records = sources(artifact(relations=[edge('implemented_by', aid('task'))]), artifact('task', maturity='approved'))
        profile = rule(artifact_types=('task',), relation_types=('implemented_by',),
                       endpoint_types=('requirement',), direction='incoming')
        result = RelationObligations(records, profile_rules=[profile])
        self.assertTrue(result.requirements_satisfied)
        self.assertEqual(result.checks[0].relation_ids, (rid(),))
        self.assertEqual(result.checks[0].endpoint_ids, (aid(),))

    def test_incoming_supersedes_does_not_require_storing_inverse_type(self):
        records = sources(artifact(), artifact(number=2, relations=[edge('supersedes', aid())]))
        result = RelationObligations(records, profile_rules=[rule(relation_types=('supersedes',), direction='incoming')])
        actual = {x.artifact_id:x.actual for x in result.checks}
        self.assertEqual(actual[aid()],1); self.assertEqual(actual[aid(number=2)],0)
        with self.assertRaises(ModelError): rule(relation_types=('superseded_by',))

    def test_symmetric_both_direction_counts_identity_once(self):
        records = sources(artifact(relations=[edge('duplicates')]), artifact(number=2))
        result = RelationObligations(records, profile_rules=[rule(relation_types=('duplicates',), direction='both')])
        self.assertEqual([x.actual for x in result.checks], [1,1])
        self.assertEqual([x.relation_ids for x in result.checks], [(rid(),),(rid(),)])

    def test_noncanonical_symmetry_is_not_repaired(self):
        records = sources(artifact(), artifact(number=2,relations=[edge('duplicates',aid())]))
        with self.assertRaises(ModelError): RelationObligations(records, profile_rules=[rule()])

    def test_distinct_relations_to_same_target_remain_distinct(self):
        records = sources(artifact(relations=[edge('depends_on',number=1),edge('depends_on',number=2)]), artifact(number=2))
        result = RelationObligations(records, profile_rules=[rule(minimum=2)])
        first = next(x for x in result.checks if x.artifact_id==aid())
        self.assertEqual(first.actual,2)
        self.assertEqual(len(first.endpoint_ids),1)
        self.assertTrue(first.satisfied)

    def test_duplicate_relation_id_is_never_counted_twice(self):
        with self.assertRaises(ModelError):
            RelationObligations(sources(artifact(relations=[edge('depends_on'), edge('depends_on')]),artifact(number=2)),
                                profile_rules=[rule(minimum=2)])

    def test_unknown_filter_values_rejected(self):
        for kwargs in ({'artifact_types':('missing',)}, {'endpoint_types':('missing',)},
                       {'maturities':('ready',)}, {'relation_types':('unknown',)},
                       {'direction':'sideways'}, {'severity':'fatal'}):
            with self.subTest(field=next(iter(kwargs))), self.assertRaises(ModelError): rule(**kwargs)

    def test_invalid_minimum_not_coerced(self):
        for value in (True, False, -1, 1.0, '1', None):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ModelError): rule(minimum=value)

    def test_empty_or_duplicate_filters_rejected(self):
        for kwargs in ({'artifact_types':()}, {'relation_types':()},
                       {'artifact_types':('requirement','requirement')},
                       {'relation_types':('depends_on','depends_on')},
                       {'endpoint_types':('task','task')}, {'maturities':('draft','draft')}):
            with self.subTest(field=next(iter(kwargs))), self.assertRaises(ModelError): rule(**kwargs)

    def test_profile_rule_ids_are_unique(self):
        with self.assertRaises(ModelError):
            RelationObligations(sources(artifact()), profile_rules=[rule(),rule(minimum=2)])

    def test_unresolved_dicts_or_callbacks_are_not_executed(self):
        def forbidden(): raise AssertionError('must not execute')
        for item in ({'minimum':1}, forbidden, object(), None):
            with self.subTest(kind=type(item).__name__), self.assertRaises(ModelError):
                RelationObligations(sources(artifact()), profile_rules=[item])

    def test_invalid_sequences_have_controlled_errors(self):
        for value in ('bad', b'bad', {}, None, 1):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(ModelError): RelationObligations(value)
                with self.assertRaises(ModelError): RelationObligations(sources(artifact()),profile_rules=value)

    def test_input_and_policy_binding_are_separate_and_order_independent(self):
        records = sources(artifact(),artifact(number=2))
        a,b = rule(rule_id='profile:a'),rule(rule_id='profile:b',minimum=2)
        one = RelationObligations(records,profile_rules=[a,b])
        two = RelationObligations(reversed(records),profile_rules=[b,a])
        self.assertEqual(one,two)
        changed = RelationObligations(records,profile_rules=[a])
        self.assertEqual(one.input_sha256,changed.input_sha256)
        self.assertNotEqual(one.policy_sha256,changed.policy_sha256)

    def test_mutable_rule_inputs_and_data_views_do_not_leak(self):
        types=['requirement']; profile=rule(artifact_types=types)
        types.append('task'); view=profile.data;view['artifact_types'].clear()
        self.assertEqual(profile.artifact_types,('requirement',))
        with self.assertRaises(FrozenInstanceError): profile.minimum=0

    def test_result_diagnostics_are_independent_copies(self):
        result=RelationObligations(sources(artifact()),profile_rules=[rule()])
        diagnostic=result.diagnostics[0];diagnostic['minimum']=0;diagnostic['relation_ids'].append('fake')
        self.assertEqual(result.diagnostics[0]['minimum'],1)
        self.assertEqual(result.diagnostics[0]['relation_ids'],[])

    def test_many_incoming_edges_are_not_cut_at_display_limit(self):
        count=151
        records=sources(artifact('task'),*[artifact(number=n,relations=[edge('implemented_by',aid('task'),n)])
                                          for n in range(1,count+1)])
        profile=rule(artifact_types=('task',),relation_types=('implemented_by',),direction='incoming',minimum=count)
        result=RelationObligations(records,profile_rules=[profile])
        self.assertTrue(result.requirements_satisfied)
        self.assertEqual(len(result.checks[0].relation_ids),count)
        self.assertEqual(result.checks[0].actual,count)

    def test_all_diagnostics_are_returned_without_first_failure_truncation(self):
        result=RelationObligations(sources(*[artifact(number=n,maturity='approved') for n in range(1,81)]))
        self.assertEqual(len(result.diagnostics),160)

    def test_empty_explicit_profile_does_not_mean_profile_composition_was_validated(self):
        result=RelationObligations(satisfied_fixture(),profile_rules=[])
        self.assertTrue(result.requirements_satisfied)
        self.assertFalse(result.profile_composition_checked)
        self.assertEqual(result.profile_rule_ids,())


class ReviewContextRightTests(unittest.TestCase):
    def test_all_excluded_top_level_fields(self):
        changes = {'revision':2, 'created_at':'2025-01-01T00:00:00Z',
            'created_by':{'actor_type':'human','actor_id':'changed'},
            'updated_at':'2027-01-01T00:00:00Z', 'updated_by':{'actor_type':'tool','actor_id':'changed'},
            'maturity':'approved', 'implementation_status':'implemented', 'verification_plan_status':'planned',
            'risk_status':'closed','validation_status':'validated','issue_status':'closed',
            'proposal_status':'draft','evidence_state':'recorded','baseline_state':'sealed',
            'review_state':'recorded','relations':[edge()], 'tags':['changed']}
        baseline=EndpointReviewContext(sources(artifact())[0])
        for field,value in changes.items():
            with self.subTest(field=field):
                context=EndpointReviewContext(sources(artifact(**{field:value}))[0])
                self.assertEqual(context.context_sha256,baseline.context_sha256)
                self.assertNotEqual(context.artifact_sha256,baseline.artifact_sha256)

    def test_business_and_unknown_future_fields_remain_bound(self):
        changes={'title':'changed','statement':'changed','rationale':'changed','owner':'changed',
                 'priority':'could','criticality':'high','language':'en','normative_force':'may',
                 'applicability':{'literal':True},'provenance':[], 'external_identities':[],
                 'extensions':{'example.org:data':42}, 'future_business_field':None,
                 'display_id':'new display'}
        baseline=EndpointReviewContext(sources(artifact())[0])
        for field,value in changes.items():
            with self.subTest(field=field):
                context=EndpointReviewContext(sources(artifact(**{field:value}))[0])
                self.assertNotEqual(context.context_sha256,baseline.context_sha256)

    def test_exclusion_is_not_recursive(self):
        keys=['revision','created_at','created_by','updated_at','updated_by','maturity',
              'implementation_status','verification_plan_status','risk_status','validation_status',
              'issue_status','proposal_status','evidence_state','baseline_state','review_state','relations','tags']
        for key in keys:
            with self.subTest(field=key):
                a,b=sources(artifact(extensions={'example.org:x':{key:'one'}}),
                            artifact(extensions={'example.org:x':{key:'two'}}))
                self.assertNotEqual(EndpointReviewContext(a).context_sha256,EndpointReviewContext(b).context_sha256)

    def test_absent_and_null_business_fields_differ(self):
        a,b=sources(artifact(),artifact(future=None))
        self.assertNotEqual(EndpointReviewContext(a).context_sha256,EndpointReviewContext(b).context_sha256)

    def test_array_order_and_unicode_are_not_normalized(self):
        for before,after in [([1,2],[2,1]),('é','e\u0301')]:
            with self.subTest(kind=type(before).__name__):
                a,b=sources(artifact(extensions={'x.y':before}),artifact(extensions={'x.y':after}))
                self.assertNotEqual(EndpointReviewContext(a).context_sha256,EndpointReviewContext(b).context_sha256)

    def test_relation_rationale_identity_target_type_extensions_are_bound(self):
        baseline=sources(artifact(relations=[edge()]))[0].relations[0]
        for changes in ({'rationale':'new'}, {'relation_id':rid(2)}, {'target':aid(number=3)},
                        {'type':'depends_on'}, {'extensions':{'a.b':{'created_at':'kept'}}},
                        {'external_identities':[external()]}):
            with self.subTest(field=next(iter(changes))):
                changed=sources(artifact(relations=[edge(**changes)]))[0].relations[0]
                self.assertNotEqual(relation_content_sha256(baseline),relation_content_sha256(changed))

    def test_contains_position_is_review_relevant(self):
        a,b=sources(artifact('document',relations=[edge('contains',aid('section'),position=0)]),
                    artifact('document',relations=[edge('contains',aid('section'),position=1)]))
        self.assertNotEqual(relation_content_sha256(a.relations[0]),relation_content_sha256(b.relations[0]))
        self.assertEqual(EndpointReviewContext(a).context_sha256,EndpointReviewContext(b).context_sha256)

    def test_relation_hash_matches_independent_simple_jcs_vector(self):
        record=sources(artifact(relations=[edge(rationale='plain',created_at='2026-01-01T00:00:00Z')]))[0]
        expected=edge(rationale='plain')
        raw=json.dumps(expected,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
        self.assertEqual(relation_content_sha256(record.relations[0]),sha256(raw).hexdigest())

    def test_mismatched_source_record_is_rejected(self):
        a,b,c=sources(artifact(relations=[edge()]),artifact(number=2),artifact(number=3))
        with self.assertRaises(ModelError): RelationReviewContext(a.relations[0],c,b)

    def test_same_id_but_replaced_relation_bytes_are_rejected(self):
        a,b=sources(artifact(relations=[edge()]),artifact(number=2))
        changed=sources(artifact(relations=[edge(extensions={'a.b':'new'})]))[0]
        with self.assertRaises(ModelError): RelationReviewContext(a.relations[0],changed,b)

    def test_noncanonical_symmetric_context_is_rejected(self):
        a,b=sources(artifact(),artifact(number=2,relations=[edge('duplicates',aid())]))
        with self.assertRaises(ModelError): RelationReviewContext(b.relations[0],b,a)

    def test_controlled_schema_errors_not_hashes_for_bad_input(self):
        for raw in (b'{"id":1}', b'{"id":1,"id":2}', b'{} trailing', b'\xff'):
            with self.subTest(raw=raw.hex()), self.assertRaises(ModelError):
                EndpointReviewContext(SourceRelations(raw))

    def test_context_objects_are_immutable(self):
        a,b=sources(artifact(relations=[edge()]),artifact(number=2))
        result=RelationReviewContext(a.relations[0],a,b)
        with self.assertRaises(FrozenInstanceError):result.relation_sha256='0'*64
        with self.assertRaises(FrozenInstanceError):result.source.revision=99

    def test_original_bytes_stay_identical_after_both_operations(self):
        records=satisfied_fixture();original=[r.source_bytes for r in records]
        RelationObligations(records,profile_rules=[rule(minimum=0)])
        RelationReviewContext(records[0].relations[0],records[0],records[1])
        self.assertEqual(original,[r.source_bytes for r in records])

    def test_no_clock_entropy_locale_or_process_lookup(self):
        a,b=sources(artifact(relations=[edge()]),artifact(number=2))
        with patch('time.time',side_effect=AssertionError('clock')), \
             patch('secrets.token_bytes',side_effect=AssertionError('entropy')), \
             patch('locale.setlocale',side_effect=AssertionError('locale')):
            binding=RelationReviewContext(a.relations[0],a,b)
            self.assertEqual(binding.source.revision,1)
            self.assertFalse(binding.review_selected)

    def test_distributions_retain_pure_contracts_after_moving(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);build=root/'built';build_distribution(build)
            moved=root/'moved';build.rename(moved)
            a,b=sources(artifact(relations=[edge()]),artifact(number=2))
            expected=RelationReviewContext(a.relations[0],a,b).source.context_sha256
            body=("from specroad.graph.relations import SourceRelations\n"
                  "from specroad.graph.review_contexts import RelationReviewContext\n"
                  "from specroad.graph.relation_obligations import RelationObligations,MinimumRelationRule\n"
                  f"a=SourceRelations({a.source_bytes!r}); b=SourceRelations({b.source_bytes!r})\n"
                  f"assert RelationReviewContext(a.relations[0],a,b).source.context_sha256=={expected!r}\n"
                  "assert not RelationObligations((a,b)).approval_granted\n")
            before=files_under(moved)
            module=next(path for path in moved.rglob('specroad') if path.is_dir())
            zipapp=next(moved.glob('*.pyz'))
            for location in (module.parent,zipapp):
                result=run_python(['-I','-S','-B','-c','import sys;sys.path.insert(0,'+repr(str(location))+');\n'+body],root)
                self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(files_under(moved),before)
