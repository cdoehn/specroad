"""Versioned canonical-byte vectors and invalid-data behavior, not UI tests."""

from decimal import Decimal, Inexact, Rounded, localcontext
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
import unittest

from specroad.model.canonical import (canonical_json_bytes, canonical_json_sha256,
                                      canonical_object_bytes, canonical_object_sha256)
from specroad.model.errors import ModelError
from specroad.storage.json_syntax import parse_json_object
from specroad.storage.artifact_common import CommonArtifact
from support.artifacts import common_artifact, artifact_bytes
from support.portable import build_distribution

DATA = Path(__file__).parent / 'data' / 'jcs-rfc8785-v1.json'


class CanonicalRightTests(unittest.TestCase):
    def test_rfc8785_binary64_vectors(self):
        vectors = json.loads(DATA.read_text(encoding='utf-8'))
        for vector in vectors['numbers']:
            bits, expected = vector['binary64_hex'], vector['canonical']
            value = struct.unpack('>d', bytes.fromhex(bits))[0]
            with self.subTest(binary64=bits):
                if expected is None:
                    with self.assertRaises(ModelError) as caught:
                        canonical_json_sha256(value)
                    self.assertEqual(caught.exception.reason, 'nonfinite_number')
                else:
                    self.assertEqual(canonical_json_bytes(value), expected.encode('ascii'))
                    self.assertEqual(canonical_json_sha256(value), hashlib.sha256(expected.encode()).hexdigest())

    def test_every_valid_rfc_number_roundtrips_through_strict_reader(self):
        for vector in json.loads(DATA.read_text())['numbers']:
            expected = vector['canonical']
            if expected is not None:
                with self.subTest(binary64=vector['binary64_hex']):
                    raw = ('{"n":' + expected + '}').encode()
                    self.assertEqual(canonical_object_bytes(raw), raw)

    def test_rfc_full_object_utf8_vector(self):
        expected = bytes.fromhex('''7b 22 6c 69 74 65 72 61 6c 73 22 3a 5b 6e 75 6c 6c 2c 74 72
            75 65 2c 66 61 6c 73 65 5d 2c 22 6e 75 6d 62 65 72 73 22 3a
            5b 33 33 33 33 33 33 33 33 33 2e 33 33 33 33 33 33 33 2c 31
            65 2b 33 30 2c 34 2e 35 2c 30 2e 30 30 32 2c 31 65 2d 32 37
            5d 2c 22 73 74 72 69 6e 67 22 3a 22 e2 82 ac 24 5c 75 30 30
            30 66 5c 6e 41 27 42 5c 22 5c 5c 5c 5c 5c 22 2f 22 7d''')
        # RFC's example describes already-parsed binary64, not a lossless input
        # token. SpecRoad deliberately rejects the original overprecise token.
        value = {'string': "€$\x0f\nA'B\"\\\\\"/", 'literals': [None, True, False],
                 'numbers': [333333333.3333333, 1e30, 4.5, 0.002, 1e-27]}
        self.assertEqual(canonical_json_bytes(value), expected)
        with self.assertRaises(ModelError):
            canonical_object_bytes(b'{"n":333333333.33333329}')

    def test_shortest_rounding_tie_is_even(self):
        value = struct.unpack('>d', bytes.fromhex('43143ff3c1cb0959'))[0]
        self.assertEqual(canonical_json_bytes(value), b'1424953923781206.2')
        self.assertEqual(canonical_json_bytes(-value), b'-1424953923781206.2')

    def test_subnormal_and_normal_boundaries(self):
        for bits in ('000fffffffffffff', '0010000000000000', '0010000000000001'):
            value = struct.unpack('>d', bytes.fromhex(bits))[0]
            with self.subTest(binary64=bits):
                encoded = canonical_json_bytes(value)
                self.assertEqual(struct.pack('>d', float(encoded)).hex(), bits)
                self.assertEqual(canonical_json_bytes(-value), b'-' + encoded)

    def test_threshold_neighbors_have_correct_decimal_placement(self):
        pairs = [(1e-6, b'0.000001'), (math.nextafter(1e-6, 0), b'9.999999999999997e-7'),
                 (math.nextafter(1e-6, math.inf), b'0.0000010000000000000002'),
                 (1e21, b'1e+21'), (math.nextafter(1e21, 0), b'999999999999999900000'),
                 (math.nextafter(1e21, math.inf), b'1.0000000000000001e+21')]
        for value, expected in pairs:
            with self.subTest(expected=expected):
                self.assertEqual(canonical_json_bytes(value), expected)

    def test_all_ascii_control_bytes_use_jcs_escapes(self):
        short = {8: b'\\b', 9: b'\\t', 10: b'\\n', 12: b'\\f', 13: b'\\r'}
        for codepoint in range(32):
            with self.subTest(codepoint=codepoint):
                expected = short.get(codepoint, ('\\u%04x' % codepoint).encode())
                self.assertEqual(canonical_json_bytes(chr(codepoint)), b'"' + expected + b'"')

    def test_other_unicode_scalars_remain_unescaped(self):
        value = '\x7f\u0080\u00ad\ufeff\u2028\u2029\uffff\U0010ffff'
        self.assertEqual(canonical_json_bytes(value), b'"' + value.encode() + b'"')

    def test_sorting_uses_unescaped_key_values(self):
        self.assertEqual(list(json.loads(canonical_json_bytes({'\\n': 1, '\n': 2, 'A': 3}))),
                         ['\n', 'A', '\\n'])

    def test_utf16_prefix_and_supplementary_order(self):
        keys = ['\uffff', '\ue000', '\U00010000', '\U0010ffff', '\ud7ff', '', 'a', 'aa']
        expected = ['', 'a', 'aa', '\ud7ff', '\U00010000', '\U0010ffff', '\ue000', '\uffff']
        self.assertEqual(list(json.loads(canonical_json_bytes(dict.fromkeys(keys, 0)))), expected)

    def test_nfc_nfd_keys_remain_separate(self):
        value = {'é': 1, 'e\u0301': 2}
        self.assertEqual(json.loads(canonical_json_bytes(value)), value)
        self.assertNotEqual(canonical_json_sha256({'é': 1}), canonical_json_sha256({'e\u0301': 1}))

    def test_valid_escaped_surrogate_pair_matches_literal_scalar(self):
        self.assertEqual(canonical_object_sha256(b'{"x":"\\ud83d\\ude00"}'),
                         canonical_object_sha256('{"x":"😀"}'.encode()))

    def test_invalid_surrogate_value_reports_pointer(self):
        with self.assertRaises(ModelError) as caught:
            canonical_json_sha256({'a/b~': ['\ud800']})
        self.assertEqual(caught.exception.pointer, '/a~1b~0/0')
        self.assertEqual(caught.exception.reason, 'invalid_unicode')

    def test_both_hash_and_byte_apis_reject_the_same_invalid_value(self):
        for value in [float('nan'), b'no', {'a': object()}, {1: 2}, {'x': 10 ** 400}]:
            reasons = []
            for call in (canonical_json_bytes, canonical_json_sha256):
                with self.assertRaises(ModelError) as caught:
                    call(value)
                reasons.append((caught.exception.reason, caught.exception.pointer))
            self.assertEqual(reasons[0], reasons[1])

    def test_failed_call_does_not_poison_subsequent_hashes(self):
        expected = canonical_json_sha256({'ok': 1})
        for _ in range(3):
            with self.assertRaises(ModelError):
                canonical_json_sha256([1, object()])
            self.assertEqual(canonical_json_sha256({'ok': 1}), expected)

    def test_deep_value_does_not_depend_on_python_recursion_limit(self):
        value = 0
        for _ in range(1500):
            value = [value]
        expected = b'[' * 1500 + b'0' + b']' * 1500
        self.assertEqual(canonical_json_bytes(value), expected)
        self.assertEqual(canonical_json_sha256(value), hashlib.sha256(expected).hexdigest())

    def test_deep_cycle_is_rejected_without_recursion_error(self):
        root = []; current = root
        for _ in range(1200):
            child = []; current.append(child); current = child
        current.append(root)
        with self.assertRaises(ModelError) as caught:
            canonical_json_sha256(root)
        self.assertEqual(caught.exception.reason, 'cyclic_json')

    def test_shared_nested_objects_can_occur_at_multiple_depths(self):
        shared = {'x': [1, 2]}
        value = [shared, {'a': [shared]}, shared]
        self.assertEqual(json.loads(canonical_json_bytes(value)), value)

    def test_passive_mapping_subclasses_are_not_executed(self):
        class Trap(dict):
            def __iter__(self):
                raise AssertionError('must not iterate')
            def items(self):
                raise AssertionError('must not call')
        with self.assertRaises(ModelError) as caught:
            canonical_json_bytes(Trap(a=1))
        self.assertEqual(caught.exception.reason, 'unsupported_json_type')

    def test_custom_numeric_conversion_is_not_executed(self):
        class Trap(int):
            def __float__(self):
                raise AssertionError('must not convert')
        with self.assertRaises(ModelError) as caught:
            canonical_json_sha256(Trap(1))
        self.assertEqual(caught.exception.reason, 'unsupported_json_type')

    def test_generators_are_not_consumed_as_json_arrays(self):
        called = []
        def values():
            called.append(True)
            yield 1
        with self.assertRaises(ModelError):
            canonical_json_bytes(values())
        self.assertEqual(called, [])

    def test_decimal_precision_and_traps_do_not_change_hash(self):
        value = {'a': 1.2345678901234567, 'b': 10 ** 23}
        expected = canonical_json_sha256(value)
        with localcontext() as context:
            context.prec = 2; context.traps[Inexact] = True; context.traps[Rounded] = True
            flags = dict(context.flags)
            self.assertEqual(canonical_json_sha256(value), expected)
            self.assertEqual(context.prec, 2)
            self.assertEqual(dict(context.flags), flags)

    def test_small_seeded_binary64_roundtrips(self):
        rng = random.Random(8785)
        for _ in range(512):
            bits = rng.getrandbits(64)
            value = struct.unpack('>d', bits.to_bytes(8, 'big'))[0]
            if not math.isfinite(value):
                continue
            encoded = canonical_json_bytes(value)
            self.assertEqual(float(encoded), value)
            self.assertEqual(canonical_json_bytes(parse_json_object(b'{"x":' + encoded + b'}')['x']), encoded)

    def test_object_hash_requires_original_bytes_and_object_root(self):
        for raw in (None, '{}', bytearray(b'{}'), b'[]', b'1', b'null'):
            with self.subTest(kind=type(raw).__name__), self.assertRaises(ModelError):
                canonical_object_sha256(raw)

    def test_canonical_hashing_does_not_increment_artifact_revision(self):
        raw = artifact_bytes(common_artifact(revision=7, title='e\u0301'))
        artifact = CommonArtifact(raw)
        before = artifact.audit
        canonical_json_sha256(parse_json_object(artifact.source_bytes)); canonical_object_sha256(artifact.source_bytes)
        self.assertEqual(artifact.audit, before)
        self.assertEqual(artifact.source_bytes, raw)
        self.assertEqual(parse_json_object(artifact.source_bytes)['revision'], 7)

    def test_full_artifact_field_changes_change_hash(self):
        value = common_artifact()
        before = canonical_json_sha256(value)
        for field, change in [('revision', 2), ('updated_at', '2026-09-16T10:00:00Z'),
                              ('extensions', {'test.example': {'x': 1}})]:
            modified = dict(value); modified[field] = change
            with self.subTest(field=field):
                self.assertNotEqual(canonical_json_sha256(modified), before)

    def test_string_encoded_large_numbers_stay_strings(self):
        value = {'huge': '1e400', 'exact': '1000000000000000128'}
        self.assertEqual(json.loads(canonical_json_bytes(value)), value)
        self.assertEqual(canonical_json_bytes({'n': '0.1'}), b'{"n":"0.1"}')

    def test_numeric_spellings_are_normalized_but_text_is_not(self):
        self.assertEqual(canonical_object_bytes(b'{"x":-0.000e-2,"s":"-0.000e-2"}'),
                         b'{"s":"-0.000e-2","x":0}')

    def test_hash_state_is_private_between_threads(self):
        from concurrent.futures import ThreadPoolExecutor
        values = [{'n': i, 'data': 'e\u0301'} for i in range(24)]
        expected = [canonical_json_sha256(value) for value in values]
        with ThreadPoolExecutor(max_workers=3) as workers:
            self.assertEqual(list(workers.map(canonical_json_sha256, values)), expected)

    def test_portable_distributions_keep_jcs_contract_without_third_party_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); build_distribution(root / 'out')
            (root / 'out').rename(root / 'moved')
            for location in (root / 'moved/module', root / 'moved/specroad.pyz'):
                code = ('import sys;sys.path.insert(0,sys.argv[1]);'
                        'from specroad.model.canonical import canonical_json_bytes,canonical_object_sha256;'
                        'assert canonical_json_bytes({"n":1e21,"a":"é"}) == '
                        '\'{"a":"é","n":1e+21}\'.encode();'
                        'assert canonical_object_sha256(b"{}") == '
                        '"44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"')
                result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code, str(location)],
                                        cwd=root, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(result.returncode, 0, result.stderr)
