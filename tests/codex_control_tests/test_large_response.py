"""Actual socket framing and RPC limits, without real Codex or model calls."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
import io
import json
import socket
import struct
import unittest
from specroad_control.codex_proxy import Proxy
from specroad_control.codex_ws import UnixWebSocket, MAX_LINE, MAX_RESPONSE
from specroad_control.errors import ControlError
from codex_control_tests.automation_support import AutomationCase
from codex_control_tests.daemon_socket import send_frame


class WireSizeTests(unittest.TestCase):
    def setUp(self):
        self.client, self.server = socket.socketpair()
        self.ws = object.__new__(UnixWebSocket)
        self.ws.sock, self.ws.buffer = self.client, bytearray()
        self.addCleanup(self.server.close)
        self.addCleanup(self.ws.close)

    def read_sent(self, send, **kwargs):
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(send)
            result = self.ws.read(**kwargs)
            future.result(5)
        return result

    def test_three_mib_json_message_is_accepted(self):
        doc = {'result': {'data': 'x' * (3 * 1024 * 1024)}}
        raw = json.dumps(doc).encode()
        self.assertGreater(len(raw), MAX_LINE)
        self.assertEqual(self.read_sent(lambda: send_frame(self.server, raw)), doc)

    def test_large_fragmented_unicode_message_preserves_bytes(self):
        doc = {'result': {'data': '\u00e4' * (600 * 1024)}}
        raw = json.dumps(doc, ensure_ascii=False).encode()
        def send():
            # Split inside an encoded character, not on a JSON boundary.
            send_frame(self.server, raw[:101], fin=False)
            send_frame(self.server, b'ping', opcode=9)
            send_frame(self.server, raw[101:], opcode=0)
        self.assertEqual(self.read_sent(send), doc)

    def test_over_limit_header_rejected_without_waiting_for_its_body(self):
        self.server.sendall(bytes([0x81, 127]) + struct.pack('!Q', MAX_RESPONSE + 1))
        with self.assertRaises(ControlError) as caught:
            self.ws.read(timeout=.5)
        self.assertEqual(caught.exception.code, 'codex_response_too_large')
        self.assertEqual(caught.exception.details['announced_bytes'], MAX_RESPONSE + 1)
        self.assertEqual(caught.exception.details['limit_bytes'], MAX_RESPONSE)
        self.assertIsNone(self.ws.sock)

    def test_outgoing_limit_does_not_increase(self):
        with self.assertRaises(ControlError) as caught:
            self.ws.send({'input': 'x' * (MAX_LINE + 1)})
        self.assertEqual(caught.exception.code, 'codex_protocol_error')
        self.server.settimeout(.05)
        with self.assertRaises(socket.timeout):
            self.server.recv(1)

    def test_small_malformed_json_is_still_rejected(self):
        send_frame(self.server, b'{"id":1,"id":2}')
        with self.assertRaises(ControlError) as caught:
            self.ws.read()
        self.assertEqual(caught.exception.code, 'codex_protocol_error')


class LargeHistorySocketTests(AutomationCase):
    def insert_history(self):
        target = {'id': 'target', 'status': 'failed', 'itemsView': 'full', 'items': [
            {'id': 'reasoning', 'type': 'reasoning', 'text': 'x' * (3 * 1024 * 1024)}],
            'error': {'codexErrorInfo': 'serverOverloaded'}}
        self.codex_daemon.server.history['target'] = target
        return target

    def test_large_paginated_turn_can_be_read_without_model_call(self):
        target = self.insert_history()
        with Proxy(self.config) as proxy:
            live = proxy.inspect_turn('target')
        self.assertEqual(live['turn'], target)
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_large_legacy_history_remains_readable(self):
        target = self.insert_history()
        self.settings(legacy_history=True)
        with Proxy(self.config) as proxy:
            live = proxy.inspect_turn('target')
        self.assertEqual(live['turn'], target)
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_response_limit_has_structured_journal_classification(self):
        self.settings(frame_oversized=True)
        output = io.StringIO()
        with redirect_stderr(output):
            with self.assertRaises(ControlError) as caught:
                Proxy(self.config)
        self.assertEqual(caught.exception.code, 'codex_response_too_large')
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(records[-1]['error'], 'codex_response_too_large')
        self.assertEqual(records[-1]['rpc_method'], 'initialize')
        self.assertEqual(records[-1]['announced_bytes'], 2**30)
        self.assertNotIn(self.thread, output.getvalue())
