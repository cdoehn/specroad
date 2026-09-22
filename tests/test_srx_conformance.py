"""Versioned behavior vectors for every SRX 1.0 operator and Appendix U."""
import copy
import json
import unittest
from unittest.mock import patch

from specroad.srx import SUPPORTED_OPERATORS, SrxError
from support.srx_vectors import load_corpus, validate_corpus, assert_case, assert_json_equal, observe_case
from support.srx import literal, binary, expression_document, roots


class SrxConformanceWorkTests(unittest.TestCase):
    def cases(self):
        return load_corpus()['cases']

    def test_operator_positive_vectors(self):
        for case in self.cases():
            if case['category']=='positive':
                with self.subTest(case=case['id']):assert_case(case)

    def test_operator_negative_vectors(self):
        for case in self.cases():
            if case['category']=='negative':
                with self.subTest(case=case['id']):assert_case(case)

    def test_operator_boundary_vectors(self):
        for case in self.cases():
            if case['category']=='boundary':
                with self.subTest(case=case['id']):assert_case(case)

    def test_operator_error_vectors_and_pointers(self):
        for case in self.cases():
            if case['category']=='error':
                with self.subTest(case=case['id']):assert_case(case)

    def test_appendix_u_decisions(self):
        cases=[c for c in self.cases() if c['category']=='annex_u']
        self.assertEqual(len(cases),9)
        for case in cases:
            with self.subTest(case=case['id']):assert_case(case)

    def test_every_supported_operator_has_all_four_case_classes(self):
        cases=self.cases()
        self.assertEqual({c['operator'] for c in cases},set(SUPPORTED_OPERATORS))
        for op in SUPPORTED_OPERATORS:
            self.assertTrue({'positive','negative','boundary','error'} <=
                            {c['category'] for c in cases if c['operator']==op})

    def test_fixture_copies_are_independent(self):
        a=load_corpus();b=load_corpus();a['cases'][0]['program'].clear()
        self.assertNotEqual(a,b)
        self.assertEqual(b,load_corpus())

    def test_case_execution_keeps_inputs(self):
        for c in self.cases():
            before=copy.deepcopy(c);assert_case(c);self.assertEqual(c,before)

    def test_null_and_missing_are_distinct_oracles(self):
        c=self.cases()[0];c['program']=expression_document(literal(None));c['expect']={'kind':'missing'}
        with self.assertRaises(AssertionError):assert_case(c)

    def test_boolean_and_number_cannot_forge_passing_value(self):
        for a,b in [(True,1),(False,0),({'v':[True]}, {'v':[1]})]:
            with self.assertRaises(AssertionError):assert_json_equal(a,b)

    def test_bad_expected_result_is_not_regenerated_from_implementation(self):
        c=self.cases()[0];c['expect']={'kind':'value','value':'wrong'}
        with self.assertRaises(AssertionError):assert_case(c)

    def test_wrong_error_pointer_is_detected(self):
        c=next(c for c in self.cases() if c['expect']['kind']=='error');c['expect']['input_pointer']='/wrong'
        with self.assertRaises(AssertionError):assert_case(c)

    def test_unexpected_internal_exception_is_not_conformance_success(self):
        with patch('support.srx_vectors.evaluate',side_effect=RuntimeError('internal')):
            with self.assertRaises(RuntimeError):observe_case(self.cases()[0])

    def test_empty_corpus_is_rejected(self):
        corpus=load_corpus();corpus['cases']=[]
        with self.assertRaises(ValueError):validate_corpus(corpus)

    def test_duplicate_identity_is_rejected(self):
        corpus=load_corpus();corpus['cases'].append(corpus['cases'][0])
        with self.assertRaises(ValueError):validate_corpus(corpus)

    def test_malformed_expectation_is_rejected(self):
        for expected in ({'kind':'unknown'}, {'kind':'value'}, {'kind':'missing','value':None}, {}):
            corpus=load_corpus();corpus['cases'][0]['expect']=expected
            with self.assertRaises(ValueError):validate_corpus(corpus)

    def test_corpus_version_is_not_silently_upgraded(self):
        for key,value in [('format_version',2),('corpus_revision',2),('language_version','2.0')]:
            corpus=load_corpus();corpus[key]=value
            with self.assertRaises(ValueError):validate_corpus(corpus)

    def test_diagnostic_is_independent_and_repair_is_passive(self):
        error=SrxError('division_by_zero',rule_id='r');error.code='SRV197'
        d=error.diagnostic();d['reason']='changed'
        self.assertEqual(error.diagnostic()['reason'],'division_by_zero')
        self.assertEqual(error.diagnostic()['repair_action'],'supply_nonzero_divisor')

    def test_numeric_repairs_remain_disjoint(self):
        for reason,action in [('precision_exceeded','review_project_precision'),
                              ('non_terminating','use_exact_numeric_contract'),
                              ('non_finite','supply_finite_number')]:
            error=SrxError(reason,rule_id='r');error.code='SRV197'
            self.assertEqual(error.diagnostic()['repair_action'],action)
