"""JCS is a byte-level integrity contract, never a human-output snapshot."""

import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from specroad.model.canonical import (canonical_json_bytes, canonical_json_sha256,
                                      canonical_object_bytes, canonical_object_sha256)
from specroad.model.errors import ModelError
from specroad.storage.json_syntax import parse_json_object
from support.processes import run_core


class CanonicalWorkTests(unittest.TestCase):
    def test_literals_remain_distinct_from_numbers(self):
        self.assertEqual(canonical_json_bytes([None, True, False, 1, 0]), b'[null,true,false,1,0]')

    def test_ascii_keys_are_sorted_at_every_object_level(self):
        self.assertEqual(canonical_json_bytes({'z': {'b': 2, 'a': 1}, 'a': [3, 2, 1]}),
                         b'{"a":[3,2,1],"z":{"a":1,"b":2}}')

    def test_key_insertion_order_cannot_change_hash(self):
        left = {'z': [3, {'b': 2, 'a': 1}], 'a': 0}
        right = {'a': 0, 'z': [3, {'a': 1, 'b': 2}]}
        self.assertEqual(canonical_json_sha256(left), canonical_json_sha256(right))

    def test_array_order_is_semantic(self):
        self.assertNotEqual(canonical_json_sha256([1, 2]), canonical_json_sha256([2, 1]))

    def test_sha256_binds_exact_canonical_bytes(self):
        # Independent SHA-256 vector for the JCS empty object.
        self.assertEqual(canonical_json_sha256({}),
                         '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a')
        value = {'data': [1, False, '汉字']}
        self.assertEqual(canonical_json_sha256(value), hashlib.sha256(canonical_json_bytes(value)).hexdigest())

    def test_decimals_and_exponent_thresholds(self):
        for value, expected in [(1.0, b'1'), (0.1, b'0.1'), (1e-6, b'0.000001'),
                                (1e-7, b'1e-7'), (1e20, b'100000000000000000000'),
                                (1e21, b'1e+21'), (-1.25e-5, b'-0.0000125')]:
            with self.subTest(expected=expected):
                self.assertEqual(canonical_json_bytes(value), expected)

    def test_negative_zero_is_canonical_zero(self):
        self.assertEqual(canonical_json_bytes([-0.0, 0.0, 0]), b'[0,0,0]')
        self.assertEqual(canonical_json_sha256(-0.0), canonical_json_sha256(0))

    def test_unicode_scalars_are_not_normalized(self):
        self.assertNotEqual(canonical_json_sha256('é'), canonical_json_sha256('e\u0301'))
        text = 'العربية 汉字 e\u0301 😀'
        self.assertEqual(json.loads(canonical_json_bytes(text)), text)

    def test_original_text_newlines_are_not_normalized(self):
        self.assertNotEqual(canonical_json_sha256('a\r\nb'), canonical_json_sha256('a\nb'))

    def test_control_quotes_and_backslashes_are_escaped(self):
        self.assertEqual(canonical_json_bytes('\x00\x0f\b\t\n\f\r"\\/'),
                         b'"\\u0000\\u000f\\b\\t\\n\\f\\r\\"\\\\/"')

    def test_utf16_order_is_not_python_codepoint_order(self):
        value = {'\ufb33': 7, '😀': 6, '€': 5, 'ö': 4, '\u0080': 3, '1': 2, '\r': 1}
        self.assertEqual(list(json.loads(canonical_json_bytes(value))),
                         ['\r', '1', '\u0080', 'ö', '€', '😀', '\ufb33'])

    def test_raw_whitespace_and_escapes_have_equal_hashes(self):
        first = b'{"x":"a","n":1}'
        second = b' { "n": 1.00, "x": "\\u0061" }\r\n'
        self.assertEqual(canonical_object_bytes(second), first.replace(b'"x":"a","n":1', b'"n":1,"x":"a"'))
        self.assertEqual(canonical_object_sha256(first), canonical_object_sha256(second))
        self.assertNotEqual(hashlib.sha256(first).digest(), hashlib.sha256(second).digest())

    def test_inputs_are_not_modified(self):
        shared = {'z': [3, 2, 1], 'a': 'e\u0301'}
        value = [shared, shared]
        before = copy.deepcopy(value)
        canonical_json_bytes(value); canonical_json_sha256(value)
        self.assertEqual(value, before)
        self.assertIs(value[0], value[1])
        self.assertEqual(list(shared), ['z', 'a'])

    def test_shared_child_is_not_a_cycle(self):
        child = {'b': 2, 'a': 1}
        self.assertEqual(canonical_json_bytes([child, child]), b'[{"a":1,"b":2},{"a":1,"b":2}]')

    def test_list_cycle_is_rejected_without_mutation(self):
        value = []; value.append(value)
        with self.assertRaises(ModelError) as caught:
            canonical_json_sha256(value)
        self.assertEqual((caught.exception.reason, caught.exception.pointer), ('cyclic_json', '/0'))
        self.assertIs(value[0], value)

    def test_dictionary_cycle_is_rejected(self):
        value = {}; value['self'] = value
        with self.assertRaises(ModelError):
            canonical_json_bytes(value)

    def test_non_string_keys_are_not_coerced(self):
        for key in (1, None, False, (1, 2)):
            with self.subTest(kind=type(key).__name__), self.assertRaises(ModelError) as caught:
                canonical_json_bytes({key: 'value'})
            self.assertEqual(caught.exception.reason, 'string_key_required')

    def test_nonfinite_numbers_never_produce_a_hash(self):
        for number in (float('nan'), float('inf'), -float('inf')):
            with self.subTest(sign=repr(number)), self.assertRaises(ModelError) as caught:
                canonical_json_sha256({'value': number})
            self.assertEqual((caught.exception.reason, caught.exception.pointer), ('nonfinite_number', '/value'))

    def test_lossy_python_integers_are_rejected(self):
        for number in (9007199254740993, 1000000000000000128, 10 ** 400):
            with self.subTest(digits=len(str(number))), self.assertRaises(ModelError):
                canonical_json_bytes({'n': number})

    def test_large_decimal_roundtrip_integers_are_allowed(self):
        self.assertEqual(canonical_json_bytes(10 ** 23), b'1e+23')
        self.assertEqual(canonical_json_bytes(9007199254740994), b'9007199254740994')

    def test_raw_lossy_tokens_are_not_silently_rounded(self):
        for token in ('1.0000000000000001', '9007199254740993', '1e-400'):
            with self.subTest(token=token), self.assertRaises(ModelError) as caught:
                canonical_object_sha256(('{"a/b~":[' + token + ']}').encode(), path='owned.json')
            self.assertEqual(caught.exception.pointer, '/a~1b~0/0')
            self.assertEqual(caught.exception.path, 'owned.json')

    def test_raw_duplicate_keys_and_invalid_encoding_are_rejected(self):
        for raw in (b'{"a":1,"\\u0061":2}', b'{"x":"\xff"}', b'{} {}', b'\xef\xbb\xbf{}'):
            with self.subTest(raw=raw), self.assertRaises(ModelError):
                canonical_object_bytes(raw)

    def test_unpaired_surrogates_are_not_silently_replaced(self):
        for value in ('\ud800', {'key': '\udfff'}, {'\ud800': 'value'}):
            with self.assertRaises(ModelError) as caught:
                canonical_json_bytes(value)
            self.assertEqual(caught.exception.reason, 'invalid_unicode')

    def test_non_json_python_values_are_not_coerced(self):
        for value in ((1, 2), {1, 2}, b'text', Decimal('1.1'), object()):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ModelError) as caught:
                canonical_json_bytes(value)
            self.assertEqual(caught.exception.reason, 'unsupported_json_type')

    def test_full_hash_does_not_drop_audit_or_self_hash_fields(self):
        value = {'id': 'A', 'revision': 1, 'content_sha256': '0' * 64, 'runtime': {}}
        original = canonical_json_sha256(value)
        for field, change in [('revision', 2), ('content_sha256', '1' * 64), ('runtime', {'pid': 2})]:
            altered = dict(value); altered[field] = change
            with self.subTest(field=field):
                self.assertNotEqual(original, canonical_json_sha256(altered))

    def test_no_implicit_file_read_or_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.json'
            raw = b' { "z": 1.00, "a": "e\\u0301" } '
            path.write_bytes(raw)
            canonical_object_sha256(raw, path=str(path))
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ['source.json'])

    def test_core_works_without_site_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            process = run_core("from specroad.model.canonical import canonical_json_bytes; "
                               "assert canonical_json_bytes({'b':1.0,'a':'é'}) == "
                               "'{\"a\":\"é\",\"b\":1}'.encode('utf-8')", directory)
            self.assertEqual(process.returncode, 0, process.stderr)
