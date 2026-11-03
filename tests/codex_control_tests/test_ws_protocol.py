"""Socket-level tests use an independent fake Unix WebSocket daemon."""
import json
import os
from pathlib import Path
from specroad_control.codex import Codex
from specroad_control.errors import ControlError
from codex_control_tests.automation_support import AutomationCase


class WebSocketProtocolTests(AutomationCase):
    def check_error(self, expected, **settings):
        self.settings(**settings)
        with self.assertRaises(ControlError) as caught:
            Codex(self.config).check()
        self.assertEqual(caught.exception.code, expected)
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_existing_owned_socket_success_without_spawning_process(self):
        reply=Codex(self.config).check()
        self.assertTrue(reply['thread_resolved'])
        self.assertFalse(reply['model_called'])
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_no_existing_daemon_requires_manual_start(self):
        self.codex_daemon.close()
        self.check_error('codex_daemon_unavailable')

    def test_non_socket_path_is_rejected(self):
        self.codex_daemon.close()
        self.codex_daemon.path.write_text('regular file')
        self.check_error('codex_socket_untrusted')

    def test_bad_websocket_accept_is_rejected(self):
        self.check_error('codex_handshake_failed',bad_accept=True)

    def test_extensions_are_not_silently_accepted(self):
        self.check_error('codex_handshake_failed',bad_extension=True)

    def test_missing_server_after_handshake_is_connection_lost(self):
        self.check_error('codex_connection_lost',handshake_only=True)

    def test_ping_frames_are_answered_before_metadata_reply(self):
        self.settings(frame_ping=True)
        self.assertTrue(Codex(self.config).check()['thread_resolved'])

    def test_json_messages_may_arrive_in_fragmented_text_frames(self):
        self.settings(fragment=True,frame_ping=True)
        self.assertTrue(Codex(self.config).check()['thread_resolved'])

    def test_binary_frame_is_rejected(self):
        self.check_error('codex_protocol_error',frame_binary=True)

    def test_masked_server_frame_is_rejected(self):
        self.check_error('codex_protocol_error',frame_masked=True)

    def test_oversized_ws_frame_is_rejected(self):
        self.check_error('codex_response_too_large',frame_oversized=True)

    def test_daemon_close_frame_is_not_success(self):
        self.check_error('codex_connection_lost',frame_close=True)
