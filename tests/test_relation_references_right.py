"""Independent exhaustive Core relation matrix and input-set regression cases."""

from copy import deepcopy
from pathlib import Path
import tempfile
import subprocess
import sys
import json
import unittest
from unittest.mock import patch

from specroad.graph.relations import SourceRelations
from specroad.graph.references import validate_relation_references, ResolvedRelation
from specroad.graph.relation_matrix import relation_pair_allowed, relation_rules
from specroad.model.errors import ModelError
from specroad.model.identity_values import artifact_identity
from support.artifacts import artifact_bytes
from support.relations import aid, artifact, edge, external
from support.portable import build_distribution

# Independent test contract: do not read the production table or prose docs.
TYPES = "goal need capability requirement scenario decision risk assumption component interface source verification test evidence release milestone task term proposal baseline issue document section content_block view code_ref relation_review configuration".split()
KINDS = "addresses refines derived_from depends_on conflicts_with constrains allocated_to implemented_by verified_by produces mitigates scheduled_for part_of supersedes duplicates contains references".split()


def cartesian(sources, targets):
    return {(source, target) for source in sources.split() for target in targets.split()}


def expected_pairs():
    all_types = " ".join(TYPES)
    depends = "capability requirement component interface task release milestone code_ref configuration"
    return {
        "addresses": cartesian("need capability requirement", "goal"),
        "refines": cartesian("need", "goal need") | cartesian("capability", "need capability") |
                   cartesian("requirement", "need capability requirement") | cartesian("scenario", "need capability requirement scenario"),
        "derived_from": cartesian("goal need capability requirement scenario decision risk assumption component interface verification test release milestone task term document section content_block view code_ref configuration", "source need decision assumption"),
        "depends_on": cartesian(depends, depends),
        "conflicts_with": cartesian(all_types, all_types),
        "constrains": cartesian("requirement decision", "capability requirement component interface"),
        "allocated_to": cartesian("requirement", "component interface"),
        "implemented_by": cartesian("capability requirement decision", "task component code_ref"),
        "verified_by": cartesian("requirement capability task", "verification test"),
        "produces": cartesian("verification test", "evidence"),
        "mitigates": cartesian("requirement decision task", "risk"),
        "scheduled_for": cartesian("capability requirement task", "release milestone"),
        "part_of": cartesian("milestone", "release") | cartesian("component interface", "component capability") |
                   cartesian("task", "release milestone capability"),
        "supersedes": {(kind,kind) for kind in TYPES},
        "duplicates": {(kind,kind) for kind in TYPES},
        "contains": cartesian("document", "section") | cartesian("section", "section content_block"),
        "references": cartesian("content_block view verification test source", all_types),
    }


def record(value): return SourceRelations(artifact_bytes(value))


def resolve(kind, source, target):
    a=artifact(source,number=1,relations=[edge(kind,aid(target,2))]);b=artifact(target,number=2)
    return validate_relation_references([record(a),record(b)])


class RelationReferenceRightTests(unittest.TestCase):
    def test_all_13328_type_combinations_match_independent_contract(self):
        expected = expected_pairs()
        for kind in KINDS:
            with self.subTest(kind=kind):
                accepted=set()
                for source in TYPES:
                    for target in TYPES:
                        result=relation_pair_allowed(kind,source,target)
                        self.assertIs(type(result),bool)
                        if result:accepted.add((source,target))
                self.assertEqual(accepted,expected[kind])

    def test_each_allowed_pair_resolves_through_actual_records(self):
        for kind,pairs in expected_pairs().items():
            with self.subTest(kind=kind):
                for source,target in sorted(pairs):
                    result=resolve(kind,source,target)
                    item=result.relations[0]
                    self.assertEqual((item.source.artifact_type,item.target.artifact_type),(source,target))
                    self.assertEqual(item.relation.type,kind)

    def test_self_link_forbidden_for_all_types_and_all_stored_relations(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                for source_type in TYPES:
                    value=artifact(source_type,relations=[edge(kind,aid(source_type))])
                    with self.assertRaises(ModelError) as caught: validate_relation_references([record(value)])
                    self.assertEqual(caught.exception.reason,"self_relation_forbidden")

    def test_missing_targets_rejected_for_every_stored_type(self):
        for kind in KINDS:
            with self.subTest(kind=kind),self.assertRaises(ModelError) as caught:
                validate_relation_references([record(artifact(relations=[edge(kind)]))])
            self.assertEqual(caught.exception.reason,"missing_relation_target")

    def test_unlisted_pairs_fail_in_resolved_value_constructor(self):
        for kind,source_type,target_type in (("addresses","goal","need"),("refines","goal","requirement"),
                                            ("depends_on","source","task"),("references","evidence","goal")):
            a=record(artifact(source_type,relations=[edge(kind,aid(target_type,2))]));b=record(artifact(target_type,number=2))
            with self.subTest(kind=kind),self.assertRaises(ModelError):ResolvedRelation(a.relations[0],a.identity,b.identity)

    def test_error_pointer_identifies_second_edge_without_exposing_contents(self):
        source=record(artifact(relations=[edge(number=1),edge(number=2,target=aid(number=5))]))
        source=SourceRelations(source.source_bytes,path="spec/requirements/source.json")
        with self.assertRaises(ModelError) as caught: validate_relation_references([source,record(artifact(number=2))])
        error=caught.exception
        self.assertEqual(error.pointer,"/relations/1/target")
        self.assertEqual(error.path,source.path)
        self.assertNotIn(aid(number=5),str(error))

    def test_duplicate_external_identity_between_distinct_relations_rejected(self):
        a=record(artifact(relations=[edge(number=1,external_identities=[external()]),
                                      edge(number=2,external_identities=[external(external_revision="2")])]))
        with self.assertRaises(ModelError) as caught:validate_relation_references([a,record(artifact(number=2))])
        self.assertEqual(caught.exception.reason,"duplicate_external_relation_identity")
        self.assertEqual(caught.exception.pointer,"/relations/1/external_identities/0")

    def test_duplicate_external_identity_across_sources_rejected(self):
        a=record(artifact(number=1,relations=[edge(number=1,target=aid(number=3),external_identities=[external()])]))
        b=record(artifact(number=2,relations=[edge(number=2,target=aid(number=3),external_identities=[external()])]))
        with self.assertRaises(ModelError) as caught:validate_relation_references([a,b,record(artifact(number=3))])
        self.assertEqual(caught.exception.reason,"duplicate_external_relation_identity")

    def test_external_identity_class_is_separate_from_artifact_identity_class(self):
        a=artifact(relations=[edge(external_identities=[external()])],external_identities=[external()])
        self.assertEqual(len(validate_relation_references([record(a),record(artifact(number=2))]).relations),1)

    def test_external_identity_key_is_not_just_external_id(self):
        cases=[external(),external(source_system="other"),external(source_document="other.reqif"),external(external_id="_REQ-10")]
        a=artifact(relations=[edge(number=index+1,external_identities=[value]) for index,value in enumerate(cases)])
        result=validate_relation_references([record(a),record(artifact(number=2))])
        self.assertEqual(len(result.relations),4)

    def test_input_set_failure_never_changes_source_records(self):
        a=record(artifact(relations=[edge(number=1),edge(number=2,target=aid(number=8))]));b=record(artifact(number=2))
        before=[a.source_bytes,b.source_bytes]
        with self.assertRaises(ModelError):validate_relation_references([a,b])
        self.assertEqual([a.source_bytes,b.source_bytes],before)

    def test_independent_checks_do_not_retain_old_target_or_identity_cache(self):
        a=record(artifact(relations=[edge()]));b=record(artifact(number=2))
        validate_relation_references([a,b])
        with self.assertRaises(ModelError):validate_relation_references([a])
        result=validate_relation_references([a,b]);self.assertEqual(len(result.relations),1)

    def test_permutation_keeps_metadata_attached_to_original_relation(self):
        edges=[edge(number=2,rationale="second"),edge(number=1,rationale="first")]
        a=validate_relation_references([record(artifact(relations=edges)),record(artifact(number=2))])
        b=validate_relation_references([record(artifact(number=2)),record(artifact(relations=list(reversed(edges))))])
        self.assertEqual([(r.relation.key,r.relation.data) for r in a.relations],[(r.relation.key,r.relation.data) for r in b.relations])

    def test_multiple_refinements_do_not_imply_a_single_parent_field(self):
        a=record(artifact(relations=[edge(number=1,target=aid(number=2)),edge(number=2,target=aid(number=3))]))
        result=validate_relation_references([a,record(artifact(number=2)),record(artifact(number=3))])
        self.assertEqual({r.target.id for r in result.relations},{aid(number=2),aid(number=3)})

    def test_two_distinct_relations_between_same_endpoints_remain_distinct(self):
        a=record(artifact(relations=[edge("refines",number=1),edge("depends_on",number=2)]))
        result=validate_relation_references([a,record(artifact(number=2))])
        self.assertEqual({r.relation.type for r in result.relations},{"refines","depends_on"})
        self.assertEqual(len({r.relation.identity.id for r in result.relations}),2)

    def test_language_of_text_does_not_change_matrix_or_direction(self):
        sources=[]
        for lang in ("de","ja","ar"):
            source=artifact(relations=[edge()],language=lang,title="not analyzed")
            result=validate_relation_references([record(source),record(artifact(number=2,language=lang))])
            sources.append(result.relations[0].relation.key)
        self.assertTrue(all(key==sources[0] for key in sources))

    def test_legacy_and_random_identity_can_coexist_without_remapping(self):
        old=artifact(id="SR-REQ-0001",id_scheme="legacy-sequential-v1")
        new=artifact(number=2,relations=[edge(target="SR-REQ-0001")])
        result=validate_relation_references([record(new),record(old)])
        self.assertEqual(result.relations[0].target.id,"SR-REQ-0001")
        self.assertEqual(result.relations[0].source.id,aid(number=2))

    def test_numeric_and_nonstring_matrix_inputs_raise_controlled_errors(self):
        for value in (None,False,1,[],{},"REQUIREMENT"):
            for position in range(3):
                args=["depends_on","requirement","requirement"];args[position]=value
                with self.subTest(value=repr(value),position=position),self.assertRaises(ModelError):relation_pair_allowed(*args)

    def test_records_generator_is_consumed_once_and_owned(self):
        inputs=[record(artifact(relations=[edge()])),record(artifact(number=2))];observed=[]
        def records():
            for item in inputs:observed.append(item.identity.id);yield item
        result=validate_relation_references(records());inputs.clear()
        self.assertEqual(len(observed),2);self.assertEqual(len(result.sources),2)

    def test_relation_targets_are_not_resolved_through_external_identities(self):
        fake=record(artifact(number=3,external_identities=[external(external_id=aid(number=2))]))
        with self.assertRaises(ModelError):validate_relation_references([record(artifact(relations=[edge()])),fake])

    def test_registered_rows_cannot_silently_match_twice(self):
        for kind in KINDS:
            rows=relation_rules(kind)
            for source,target in expected_pairs()[kind]:
                self.assertEqual(sum(row.accepts(source,target) for row in rows),1)

    def test_portable_graph_validation_uses_no_optional_packages(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);dist=root/"dist";build_distribution(dist);shifted=root/"moved";dist.rename(shifted)
            module=next(p for p in shifted.rglob("__init__.py") if p.parent.name=="specroad").parent.parent
            code="import sys,json;sys.path.insert(0,sys.argv[1]);from specroad.graph.relations import SourceRelations;from specroad.graph.references import validate_relation_references;values=json.loads(sys.argv[2]);result=validate_relation_references([SourceRelations(json.dumps(v).encode()) for v in values]);print(json.dumps([(r.relation.type,r.source.id,r.target.id) for r in result.relations]))"
            values=[artifact(relations=[edge()]),artifact(number=2)]
            for target in (module,next(shifted.rglob("*.pyz"))):
                run=subprocess.run([sys.executable,"-I","-S","-B","-c",code,str(target),json.dumps(values)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                self.assertEqual(run.returncode,0,run.stderr)
                self.assertEqual(json.loads(run.stdout),[["refines",aid(),aid(number=2)]])
