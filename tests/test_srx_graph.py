"""Bounded SRX graph evaluation, full supplied adjacency and no live data access."""
import copy
import json
import unittest
from dataclasses import FrozenInstanceError
from specroad.srx import (LoadedGraph, EvaluationContext, SrxProgram, SrxError,
                          evaluate, parse_program, parse_context)
from specroad.graph.indices import RelationIndex
from specroad.graph.references import RelationReferences
from support.srx import roots, literal, binary, field, expression_document, quantifier, run
from support.srx_graph import (artifact, edge, aid, records, graph, call, count, incoming, has, reach, chain)


class SrxGraphTests(unittest.TestCase):
    def test_count_outgoing(self):
        self.assertEqual(call(count(), chain()), 1)

    def test_count_incoming(self):
        self.assertEqual(call(count(direction="incoming"), chain(), 1), 1)

    def test_count_both_directions(self):
        self.assertEqual(call(count(direction="both"), chain(), 1), 2)

    def test_incoming_count_uses_all_loaded_sources(self):
        values = chain(); values.append(artifact(number=4, relations=[edge("depends_on", aid(number=2), number=4)]))
        self.assertEqual(call(incoming(), values, 1, extra_roots={"relations": []}), 2)

    def test_type_filter_and_no_matching_relations(self):
        self.assertEqual(call(count(["refines"]), chain()), 0)
        self.assertEqual(call(count(["depends_on"]), chain()), 1)

    def test_empty_explicit_type_list_means_no_edges(self):
        self.assertEqual(call(count([]), chain()), 0)
        self.assertIs(call(has([]), chain()), False)
        self.assertIs(call(reach(aid(number=2), types=[]), chain()), False)

    def test_wildcard_includes_all_stored_kinds(self):
        values = chain(); values[0]["relations"].append(edge("refines", aid(number=3), number=3))
        self.assertEqual(call(count(), values), 2)

    def test_has_matching_edge(self):
        self.assertIs(call(has(["depends_on"]), chain()), True)

    def test_has_exact_target_id(self):
        self.assertIs(call(has(target_id=aid(number=2)), chain()), True)
        self.assertIs(call(has(target_id=aid(number=3)), chain()), False)

    def test_has_target_type(self):
        self.assertIs(call(has(target_type="requirement"), chain()), True)
        self.assertIs(call(has(target_type="component"), chain()), False)

    def test_has_both_target_filters(self):
        self.assertIs(call(has(target_type="requirement", target_id=aid(number=2)), chain()), True)
        self.assertIs(call(has(target_type="component", target_id=aid(number=2)), chain()), False)

    def test_incoming_target_filter_means_other_endpoint(self):
        self.assertIs(call(has(direction="incoming", target_id=aid(number=1)), chain(), 1), True)

    def test_reachable_depth_zero_checks_start(self):
        self.assertIs(call(reach(aid(number=1), depth=0), chain()), True)
        self.assertIs(call(reach(aid(number=2), depth=0), chain()), False)

    def test_explicit_depth_limits_traversal(self):
        self.assertIs(call(reach(aid(number=3), depth=1), chain()), False)
        self.assertIs(call(reach(aid(number=3), depth=2), chain()), True)

    def test_reachable_incoming_and_both(self):
        self.assertIs(call(reach(aid(number=1), depth=2, direction="incoming"), chain(), 2), True)
        self.assertIs(call(reach(aid(number=1), depth=2, direction="both"), chain(), 2), True)

    def test_reachable_filters_each_hop(self):
        values = chain(); values[1]["relations"][0]["type"] = "refines"
        self.assertIs(call(reach(aid(number=3), depth=2, types=["depends_on"]), values), False)
        self.assertIs(call(reach(aid(number=3), depth=2, types=["depends_on", "refines"]), values), True)

    def test_unreachable_loaded_artifact_is_not_visited(self):
        values = chain(); values.append(artifact(number=4))
        self.assertIs(call(reach(aid(number=4), depth=100), values), False)

    def test_reach_predicate_reads_candidate_artifact(self):
        values = chain(); values[1]["extensions"] = {"org.example": {"ready": True}}
        pred = binary("eq", field("/extensions/org.example/ready"), literal(True))
        self.assertIs(call(reach(where=pred, depth=1), values), True)

    def test_reach_preserves_project_configuration(self):
        data = {"project": {"wanted": aid(number=3)},
                "configuration": {"configuration_id": "cfg", "effective_values": {"wanted": aid(number=3)}}}
        pred = {"op": "and", "args": [binary("eq", field("/id"), field("/wanted", "project")),
            binary("eq", field("/id"), field("/effective_values/wanted", "configuration"))]}
        self.assertIs(call(reach(where=pred, depth=2), chain(), extra_roots=data), True)

    def test_reach_candidate_relations_are_computed_views(self):
        pred = binary("eq", {"op": "count", "arg": field("", "relations")}, literal(2))
        self.assertIs(call(reach(where=pred, depth=1), chain()), True)

    def test_reach_inside_quantifier_keeps_lexical_item(self):
        predicate = binary("eq", field("/id"), field("", "item"))
        node = quantifier("all", literal([aid(number=2), aid(number=3)]), reach(where=predicate, depth=2))
        self.assertIs(call(node, chain()), True)

    def test_reach_does_not_create_global_item(self):
        with self.assertRaises(SrxError):
            SrxProgram(expression_document(reach(where=field("", "item"))), rule_id="unbound")

    def test_predicate_requires_boolean_not_truthiness(self):
        for value in (None, 0, 1, "yes", [], {}):
            with self.subTest(kind=type(value).__name__), self.assertRaises(SrxError) as error:
                call(reach(where=literal(value)), chain())
            self.assertEqual(error.exception.pointer, "/expression/where")

    def test_missing_predicate_is_error(self):
        with self.assertRaises(SrxError) as error:
            call(reach(where=field("/missing")), chain())
        self.assertEqual(error.exception.actual, "missing")

    def test_graph_is_required_not_inferred_from_relations_root(self):
        for node in (count(), incoming(), has(), reach(where=literal(True), depth=0)):
            with self.assertRaises(SrxError) as error: run(node, chain()[0])
            self.assertEqual(error.exception.reason, "loaded_graph_required")

    def test_missing_current_artifact_is_error(self):
        context = EvaluationContext(roots(artifact(number=9)), graph=graph(chain()), rule_id="missing")
        with self.assertRaises(SrxError):
            evaluate(SrxProgram(expression_document(count()), rule_id="missing"), context)

    def test_changed_current_artifact_is_error(self):
        values = chain(); data = roots(copy.deepcopy(values[0])); data["artifact"]["title"] = "changed"
        context = EvaluationContext(data, graph=graph(values), rule_id="stale")
        with self.assertRaises(SrxError) as error:
            evaluate(SrxProgram(expression_document(count()), rule_id="stale"), context)
        self.assertEqual(error.exception.reason, "graph_artifact_mismatch")

    def test_loaded_graph_never_accepts_partial_adjacency_as_source(self):
        for sources in ({"outgoing": []}, [],):
            if not sources:
                self.assertEqual(LoadedGraph(sources, rule_id="empty").artifact_ids, ())
            else:
                with self.assertRaises(SrxError): LoadedGraph(sources, rule_id="invalid")
        with self.assertRaises(SrxError): LoadedGraph([{}], rule_id="invalid")

    def test_caller_index_cannot_be_used_as_loaded_model(self):
        index = RelationIndex(RelationReferences(records(chain())))
        with self.assertRaises(SrxError):
            EvaluationContext(roots(chain()[0]), graph=index, rule_id="index")

    def test_missing_relation_target_is_rejected_during_loading(self):
        with self.assertRaises(SrxError) as error: graph(chain()[:1])
        self.assertEqual(error.exception.actual, "missing_relation_target")

    def test_unknown_options_rejected(self):
        for base in (count(), incoming(), has(), reach(where=literal(False))):
            node = dict(base); node["limit"] = 10
            with self.assertRaises(SrxError): call(node, chain())

    def test_missing_required_selectors_rejected(self):
        for name in ("direction", "types", "max_depth", "where"):
            node = reach(where=literal(False)); del node[name]
            with self.assertRaises(SrxError): call(node, chain())

    def test_direction_is_static_and_known(self):
        for value in (None, True, 1, "in", "all", [], literal("incoming")):
            with self.assertRaises(SrxError): call(count(direction=value), chain())

    def test_explicit_type_list_not_scalar_or_wildcard_mixture(self):
        for value in (None, True, "depends_on", ["*"], ["unknown"], [1], [["depends_on"]]):
            with self.assertRaises(SrxError): call(count(types=value), chain())

    def test_depth_is_nonnegative_integer_not_boolean(self):
        for value in (None, True, False, -1, 1.0, "1", literal(2)):
            with self.assertRaises(SrxError): call(reach(depth=value), chain())

    def test_unknown_target_type_and_empty_id_rejected(self):
        for filters in ({"target_type": "unknown"}, {"target_type": None}, {"target_id": ""}, {"target_id": None}):
            with self.assertRaises(SrxError): call(has(**filters), chain())

    def test_original_graph_and_context_are_unchanged(self):
        values = chain(); before = copy.deepcopy(values); loaded = graph(values)
        data = roots(values[0]); context = EvaluationContext(data, graph=loaded, rule_id="owned")
        program = SrxProgram(expression_document(reach(aid(number=3), depth=2)), rule_id="owned")
        self.assertIs(evaluate(program, context), True)
        self.assertEqual(values, before)
        values[0]["title"] = "new"; loaded.artifact(aid(number=2), rule_id="owned")["relations"].clear()
        self.assertIs(evaluate(program, context), True)

    def test_graph_object_is_immutable(self):
        loaded = graph(chain())
        with self.assertRaises(FrozenInstanceError): loaded.validation_scope = "project_complete"

    def test_raw_program_and_context_do_not_load_model(self):
        values = chain(); program = parse_program(json.dumps(expression_document(incoming())).encode(), rule_id="raw")
        context = parse_context(json.dumps(roots(values[1])).encode(), graph=graph(values), rule_id="raw")
        self.assertEqual(evaluate(program, context), 1)

    def test_non_graph_rules_still_need_no_graph(self):
        self.assertIs(run(binary("eq", literal(2), literal(2))), True)

    def test_short_circuited_graph_operator_does_not_fetch_model(self):
        self.assertIs(run(binary("or", literal(True), has())), True)
        with self.assertRaises(SrxError): run(binary("or", literal(True), reach(depth=-1)))
