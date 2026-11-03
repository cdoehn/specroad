"""Wire and retained-event budgets are safety contracts, not UI tests."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from unittest.mock import patch
import io
import json
import socket
import struct
import unittest
from specroad_control.codex_proxy import Proxy
from specroad_control.codex_ws import UnixWebSocket
from specroad_control.errors import ControlError
from codex_control_tests.automation_support import AutomationCase
from codex_control_tests.daemon_socket import send_frame


class WireBudgetTests(unittest.TestCase):
    def setUp(self):
        self.client,self.server=socket.socketpair()
        self.ws=object.__new__(UnixWebSocket)
        self.ws.sock,self.ws.buffer=self.client,bytearray()
        self.addCleanup(self.server.close);self.addCleanup(self.ws.close)

    def test_ping_does_not_count_toward_text_byte_budget(self):
        raw=b'{"a":"1234567890"}'
        send_frame(self.server,raw[:-1],fin=False)
        send_frame(self.server,b'p'*125,opcode=9)
        send_frame(self.server,raw[-1:],opcode=0)
        with patch('specroad_control.codex_ws.MAX_RESPONSE',len(raw)):
            self.assertEqual(self.ws.read(),{'a':'1234567890'})

    def test_fragmented_total_larger_than_cap_is_refused_before_final_body(self):
        send_frame(self.server,b'x'*80,fin=False)
        self.server.sendall(bytes([0x80,50]))
        with patch('specroad_control.codex_ws.MAX_RESPONSE',100), self.assertRaises(ControlError) as caught:
            self.ws.read(.5)
        self.assertEqual(caught.exception.code,'codex_response_too_large')
        self.assertEqual(caught.exception.details['announced_bytes'],130)
        self.assertIsNone(self.ws.sock)

    def test_reserved_high_bit_of_length_is_protocol_error_without_body(self):
        self.server.sendall(bytes([0x81,127])+struct.pack('!Q',2**63))
        with self.assertRaises(ControlError) as caught:self.ws.read(.5)
        self.assertEqual(caught.exception.code,'codex_protocol_error')

    def test_unknown_control_frame_is_rejected_without_waiting_body(self):
        self.server.sendall(bytes([0x8f,125]))
        with self.assertRaises(ControlError) as caught:self.ws.read(.5)
        self.assertEqual(caught.exception.code,'codex_protocol_error')

    def test_orphan_continuation_is_rejected_without_body(self):
        self.server.sendall(bytes([0x80,125]))
        with self.assertRaises(ControlError) as caught:self.ws.read(.5)
        self.assertEqual(caught.exception.code,'codex_protocol_error')

    def test_active_read_keeps_unlimited_wait_despite_larger_frame_limit(self):
        from threading import Event
        release=Event()
        def send():
            release.wait(3);send_frame(self.server,b'{"method":"turn/completed"}')
        with ThreadPoolExecutor(1) as pool:
            future=pool.submit(send)
            # timeout=None is passed through to socket.settimeout(None).
            with patch.object(self.ws,'_receive',wraps=self.ws._receive) as receive:
                release.set()
                self.assertEqual(self.ws.read(None)['method'],'turn/completed')
                self.assertTrue(all(call.args[1] is None for call in receive.call_args_list))
            future.result(3)


class PendingBudgetTests(AutomationCase):
    def test_retained_notifications_have_an_aggregate_byte_limit(self):
        with Proxy(self.config) as proxy:
            output=io.StringIO()
            event={'method':'item/delta','params':{'text':'secret-content'*20}}
            with patch('specroad_control.codex_proxy.MAX_PENDING_BYTES',100), \
                    patch.object(proxy,'read',return_value=event), redirect_stderr(output):
                with self.assertRaises(ControlError) as caught:proxy.call('thread/read',{})
            self.assertEqual(caught.exception.code,'codex_response_too_large')
            self.assertIsNone(proxy.connection)
            self.assertNotIn('secret-content',output.getvalue())
            self.assertEqual(json.loads(output.getvalue())['limit_bytes'],100)

    def test_tiny_notification_flood_still_has_count_limit(self):
        with Proxy(self.config) as proxy:
            event={'method':'ping'}
            with patch.object(proxy,'read',return_value=event), self.assertRaises(ControlError) as caught:proxy.call('thread/read',{})
            self.assertEqual(caught.exception.code,'codex_event_backlog')
            self.assertEqual(len(proxy.pending),256)
            self.assertIsNone(proxy.connection)
