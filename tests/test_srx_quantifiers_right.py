"""Nested lexical scopes, complete ordered iteration and portable execution."""
from concurrent.futures import ThreadPoolExecutor
import copy
import itertools
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.srx import (EvaluationContext, SrxError, SrxProgram, evaluate,
                          parse_program)
from specroad.srx import fields
from support.srx import binary, expression_document, field, literal, quantifier, roots, run
from support.portable import build_distribution
from support.processes import run_python


def item(pointer=""):
    return field(pointer, "item")


def unary(op, arg):
    return {"op": op, "arg": arg}


class SrxQuantifierRightTests(unittest.TestCase):
    def test_nested_array_reads_enclosing_item(self):
        inner = quantifier("any", item("/children"), item())
        self.assertIs(run(quantifier("all", literal([{"children": [False, True]},
                                                    {"children": [True]}]), inner)), True)

    def test_inner_item_shadows_outer_item(self):
        inner = quantifier("all", item("/children"), binary("eq", item("/name"), literal("inner")))
        outer = [{"name": "outer", "children": [{"name": "inner"}]}]
        self.assertIs(run(quantifier("all", literal(outer), inner)), True)

    def test_outer_item_is_restored_after_inner_quantifier(self):
        inner = quantifier("all", item("/xs"), item())
        predicate = binary("and", inner, item("/ok"))
        values = [{"xs": [True], "ok": True}, {"xs": [True], "ok": False}]
        self.assertIs(run(quantifier("all", literal(values), predicate)), False)

    def test_outer_item_is_restored_after_empty_inner_quantifier(self):
        predicate = binary("and", quantifier("none", item("/xs"), item()), item("/ok"))
        self.assertIs(run(quantifier("all", literal([{"xs": [], "ok": True}]), predicate)), True)

    def test_outer_item_survives_short_circuit_in_inner_predicate(self):
        inner = quantifier("all", item("/xs"), binary("or", literal(True), item("/0/01")))
        predicate = binary("and", inner, item("/ok"))
        self.assertIs(run(quantifier("all", literal([{"xs": [[]], "ok": True}]), predicate)), True)

    def test_multiple_nested_siblings_have_separate_bindings(self):
        predicate = binary("and", quantifier("any", item("/yes"), item()),
                           quantifier("none", item("/no"), item()))
        data = [{"yes": [False, True], "no": [False]}, {"yes": [True], "no": []}]
        self.assertIs(run(quantifier("all", literal(data), predicate)), True)

    def test_three_lexical_levels_restore_each_parent(self):
        leaf = quantifier("all", item("/children"), item("/ok"))
        middle = quantifier("all", item("/children"), binary("and", leaf, item("/ok")))
        outer = quantifier("all", literal([{"children": [{"children": [{"ok": True}], "ok": True}], "ok": True}]),
                           binary("and", middle, item("/ok")))
        self.assertIs(run(outer), True)

    def test_nested_scalar_item_has_no_outer_field_fallback(self):
        predicate = quantifier("none", item("/xs"), unary("exists", item("/outer_only")))
        self.assertIs(run(quantifier("all", literal([{"xs": [1], "outer_only": True}]), predicate)), True)

    def test_nested_null_item_is_a_real_binding(self):
        predicate = quantifier("all", item(), binary("eq", item(), literal(None)))
        self.assertIs(run(quantifier("all", literal([[None]]), predicate)), True)

    def test_root_fields_named_item_do_not_leak_into_lexical_scope(self):
        data = roots({"item": "root"})
        predicate = binary("and", binary("eq", item(), literal("element")),
                           binary("eq", field("/item"), literal("root")))
        self.assertIs(run(quantifier("all", literal(["element"]), predicate), context=data), True)

    def test_dynamic_outer_context_reference_is_rejected(self):
        for name in ("outer.item", "parent", "item.parent", "environment", {"op": "literal", "value": "item"}):
            node = quantifier("all", literal([1]), field("", name))
            with self.assertRaises(SrxError): run(node)

    def test_dynamic_pointer_is_rejected_inside_nested_predicate(self):
        bad = {"op": "field", "context": "item", "pointer": literal("/x")}
        with self.assertRaises(SrxError):
            run(quantifier("all", literal([[True]]), quantifier("all", item(), bad)))

    def test_relative_outer_escape_is_rejected(self):
        for pointer in ("/../outer", "/./x"):
            with self.assertRaises(SrxError):
                run(quantifier("all", literal([{}]), item(pointer)))

    def test_nested_quantifier_does_not_legalize_unbound_array_item(self):
        inner = quantifier("all", literal([True]), item())
        with self.assertRaises(SrxError):
            run(quantifier("all", binary("or", inner, item()), literal(True)))

    def test_array_expression_is_evaluated_once(self):
        calls = []; original = fields.resolve_tokens
        def observe(root, tokens, **kwargs):
            calls.append((tokens, root)); return original(root, tokens, **kwargs)
        node = quantifier("all", field("/xs"), item())
        with patch.object(fields, "resolve_tokens", side_effect=observe):
            self.assertIs(run(node, {"xs": [True, True, True]}), True)
        self.assertEqual([tokens for tokens, _ in calls], [("xs",), (), (), ()])

    def test_all_elements_visited_in_original_order_including_duplicates(self):
        original = fields.resolve_tokens
        for op in ("any", "all", "none"):
            seen = []
            def observe(root, tokens, **kwargs):
                if tokens == ("ok",): seen.append(root["id"])
                return original(root, tokens, **kwargs)
            values = [{"id": i, "ok": bool(i)} for i in (2, 0, 2, 1)]
            with patch.object(fields, "resolve_tokens", side_effect=observe):
                run(quantifier(op, literal(values), item("/ok")))
            self.assertEqual(seen, [2, 0, 2, 1])

    def test_first_bad_element_stops_before_later_element(self):
        seen = []; original = fields.resolve_tokens
        def observe(root, tokens, **kwargs):
            seen.append(root); return original(root, tokens, **kwargs)
        with patch.object(fields, "resolve_tokens", side_effect=observe), self.assertRaises(SrxError):
            run(quantifier("any", literal([False, None, True]), item()))
        self.assertEqual(seen, [False, None])

    def test_decisive_value_does_not_hide_later_type_error(self):
        for op, initial in (("any", True), ("all", False), ("none", True)):
            with self.assertRaises(SrxError):
                run(quantifier(op, literal([initial, None]), item()))

    def test_outer_boolean_short_circuit_skips_runtime_quantifier(self):
        bad = quantifier("all", literal([None]), item())
        self.assertIs(run(binary("and", literal(False), bad)), False)
        self.assertIs(run(binary("or", literal(True), bad)), True)

    def test_quantifier_predicate_boolean_short_circuit_remains(self):
        bad = unary("count", item())
        self.assertIs(run(quantifier("all", literal([None]), binary("or", literal(True), bad))), True)
        self.assertIs(run(quantifier("none", literal([None]), binary("and", literal(False), bad))), True)

    def test_type_failure_in_array_precedes_predicate_evaluation(self):
        bad_predicate = item("/01")
        with self.assertRaises(SrxError) as error:
            run(quantifier("all", literal(3), bad_predicate))
        self.assertEqual(error.exception.pointer, "/expression/array")

    def test_nested_error_has_exact_expression_path(self):
        node = quantifier("all", literal([[None]]), quantifier("all", item(), item()))
        program = SrxProgram(expression_document(node), rule_id="quantifier-rule")
        with self.assertRaises(SrxError) as error:
            evaluate(program, EvaluationContext(roots(), rule_id="context-rule"))
        diagnostic = error.exception.diagnostic()
        self.assertEqual(diagnostic["code"], "SRV110")
        self.assertEqual(diagnostic["rule_id"], "quantifier-rule")
        self.assertEqual(diagnostic["expression_pointer"], "/expression/where/where")
        self.assertEqual(diagnostic["expected_type"], "boolean")
        self.assertEqual(diagnostic["actual_type"], "null")

    def test_failed_evaluation_leaves_context_reusable(self):
        bad = SrxProgram(expression_document(quantifier("all", field("/xs"), item())), rule_id="bad")
        good = SrxProgram(expression_document(quantifier("all", field("/xs"), unary("exists", item()))), rule_id="good")
        context = EvaluationContext(roots({"xs": [None]}), rule_id="owned")
        before = context.data
        with self.assertRaises(SrxError): evaluate(bad, context)
        self.assertEqual(context.data, before)
        self.assertIs(evaluate(good, context), True)

    def test_repeated_nested_error_is_deterministic(self):
        node = quantifier("any", literal([[False, None]]), quantifier("all", item(), item()))
        diagnostics = []
        for _ in range(3):
            with self.assertRaises(SrxError) as error: run(node)
            diagnostics.append(error.exception.diagnostic())
        self.assertEqual(diagnostics[0], diagnostics[1])
        self.assertEqual(diagnostics[1], diagnostics[2])

    def test_exhaustive_nested_boolean_models(self):
        rows = [list(items) for size in range(3) for items in itertools.product((False, True), repeat=size)]
        oracle = {"any": any, "all": all, "none": lambda xs: not any(xs)}
        for outer, inner in itertools.product(oracle, repeat=2):
            for left, right in itertools.product(rows, repeat=2):
                matrix = [left, right]
                expected = oracle[outer]([oracle[inner](row) for row in matrix])
                node = quantifier(outer, literal(matrix), quantifier(inner, item(), item()))
                self.assertIs(run(node), expected)

    def test_deep_nesting_does_not_use_python_call_stack(self):
        node = item()
        for _ in range(1200): node = quantifier("all", literal([True]), node)
        self.assertIs(run(node), True)

    def test_broad_array_is_not_truncated(self):
        values = [False] * 2048 + [True]
        self.assertIs(run(quantifier("any", literal(values), item())), True)
        self.assertIs(run(quantifier("none", literal(values), item())), False)

    def test_deeply_wrapped_predicate_preserves_item_scope(self):
        node = item()
        for _ in range(1200): node = unary("not", node)
        self.assertIs(run(quantifier("all", literal([True]), node)), True)

    def test_separate_threads_do_not_share_element_context(self):
        node = quantifier("all", field("/xs"), quantifier("all", item(), item()))
        program = SrxProgram(expression_document(node), rule_id="threads")
        contexts = [EvaluationContext(roots({"xs": [[value]]}), rule_id="threads") for value in (True, False)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda i: evaluate(program, contexts[i % 2]), range(32)))
        self.assertEqual(results, [i % 2 == 0 for i in range(32)])

    def test_external_mutation_of_views_does_not_change_nested_result(self):
        program = SrxProgram(expression_document(quantifier("all", field("/xs"),
                                      quantifier("all", item(), item()))), rule_id="owned")
        context = EvaluationContext(roots({"xs": [[True]]}), rule_id="owned")
        context.data["artifact"]["xs"][0][0] = False
        program.expression["where"]["where"] = literal(False)
        self.assertIs(evaluate(program, context), True)

    def test_foreign_boolean_conversion_never_executes(self):
        calls = []
        class Foreign:
            def __bool__(self): calls.append("bool"); return True
            def __iter__(self): calls.append("iter"); return iter([True])
        with self.assertRaises(SrxError): run(quantifier("all", literal([Foreign()]), item()))
        self.assertEqual(calls, [])

    def test_list_subclass_never_supplies_a_quantifier_array(self):
        calls = []
        class ForeignList(list):
            def __iter__(self): calls.append("iter"); return iter([True])
        with self.assertRaises(SrxError): run(quantifier("all", literal(ForeignList([True])), item()))
        self.assertEqual(calls, [])

    def test_no_host_environment_or_file_lookup(self):
        program = SrxProgram(expression_document(quantifier("all", literal([True]), item())), rule_id="offline")
        context = EvaluationContext(roots(), rule_id="offline")
        with patch("builtins.open", side_effect=AssertionError("unexpected I/O")), \
             patch.object(os, "getenv", side_effect=AssertionError("host lookup")):
            self.assertIs(evaluate(program, context), True)

    def test_missing_in_predicate_comparisons_keeps_existing_policy(self):
        predicate = binary("ne", item("/absent"), literal(None))
        self.assertIs(run(quantifier("all", literal([{}, {}]), predicate)), True)

    def test_mutable_literal_values_are_neither_executed_nor_modified(self):
        content = {"op": "run", "command": "do-not-execute", "items": [1]}
        before = copy.deepcopy(content)
        node = quantifier("all", literal([[content]]), quantifier("all", item(),
                          binary("eq", item(), literal(content))))
        self.assertIs(run(node), True)
        self.assertEqual(content, before)

    def test_raw_bytes_reject_duplicate_quantifier_keys(self):
        raw = b'{"language":"srx","version":"1.0","expression":{"op":"any","array":{},"array":{},"where":{}}}'
        with self.assertRaises(SrxError): parse_program(raw, rule_id="duplicate")

    def test_portable_module_and_zipapp_support_nested_quantifiers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "build"
            build_distribution(output)
            moved = root / "moved"
            output.rename(moved)
            code = '''
from specroad.srx import SrxProgram, EvaluationContext, evaluate
l=lambda x:{"op":"literal","value":x}
f={"op":"field","context":"item","pointer":""}
q=lambda a,w:{"op":"all","array":a,"where":w}
p=SrxProgram({"language":"srx","version":"1.0","expression":q(l([[True],[True]]),q(f,f))},rule_id="portable")
c=EvaluationContext({"artifact":{},"configuration":None,"project":{},"relations":[]},rule_id="portable")
assert evaluate(p,c) is True
'''
            for source in (moved / "module", moved / "specroad.pyz"):
                prefix = "import sys;sys.path.insert(0," + repr(str(source)) + ");\n"
                result = run_python(["-I", "-S", "-B", "-c", prefix + code], root)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
