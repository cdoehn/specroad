"""An owned Codex-style symlink is accepted without weakening socket checks."""
import os
from pathlib import Path
import socket
from codex_control_tests.external_temp import temporary_directory
import threading
from unittest.mock import patch
from specroad_control.codex import Codex
from specroad_control.errors import ControlError
from specroad_control import codex_socket
from codex_control_tests.automation_support import AutomationCase
from codex_control_tests.daemon_socket import FakeServer

class CodexSocketLinkTests(AutomationCase):
    def linked_daemon(self):
        self.codex_daemon.close()
        suffix = 'codex-daemon-' + str(os.getuid()) + '/' + 'a' * 64
        temporary = temporary_directory(prefix='sx-', socket_suffix=suffix)
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        directory = root/('codex-daemon-'+str(os.getuid()))
        directory.mkdir(mode=0o700)
        target = directory/('a'*64)
        server = FakeServer(target,self.codex_home,self.dev)
        target.chmod(0o600)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        def close():
            server.shutdown(); server.server_close(); thread.join(timeout=2)
        self.addCleanup(close)
        mock=patch.object(codex_socket,'DAEMON_TEMP_ROOT',root)
        mock.start()
        self.addCleanup(mock.stop)
        link = self.codex_home/'app-server-control/app-server-control.sock'
        link.symlink_to(target)
        self.addCleanup(lambda: link.unlink(missing_ok=True))
        return link,target,directory

    def test_codex_link_must_not_target_an_arbitrary_private_socket(self):
        link,target,parent=self.linked_daemon()
        link.unlink()
        link.symlink_to(self.codex_home/'other.sock')
        with self.assertRaises(ControlError) as caught: Codex(self.config).check()
        self.assertEqual(caught.exception.code,'codex_socket_untrusted')

    def test_link_directory_must_remain_private(self):
        link,target,parent=self.linked_daemon()
        link.parent.chmod(0o775)
        with self.assertRaises(ControlError) as caught: Codex(self.config).check()
        self.assertEqual(caught.exception.code,'codex_socket_untrusted')

    def test_socket_mode_must_remain_private(self):
        link,target,parent=self.linked_daemon()
        target.chmod(0o660)
        with self.assertRaises(ControlError) as caught: Codex(self.config).check()
        self.assertEqual(caught.exception.code,'codex_socket_untrusted')

    def test_socket_destination_cannot_be_a_symlink_chain(self):
        link,target,parent=self.linked_daemon()
        target.rename(parent/('c'*64))
        target.symlink_to(parent/('c'*64))
        with self.assertRaises(ControlError) as caught: Codex(self.config).check()
        self.assertEqual(caught.exception.code,'codex_socket_untrusted')

    def test_wrong_connected_peer_uid_is_rejected(self):
        link,target,parent=self.linked_daemon()
        with patch.object(codex_socket,'connected_peer_uid',return_value=os.getuid()+1):
            with self.assertRaises(ControlError) as caught: Codex(self.config).check()
        self.assertEqual(caught.exception.code,'codex_socket_untrusted')

    def test_link_change_after_connection_is_rejected(self):
        link,target,parent=self.linked_daemon()
        original=codex_socket.trusted_daemon_socket
        counter={'calls':0}
        def changed(p):
            counter['calls']+=1
            if counter['calls']==2:
                link.unlink(); link.symlink_to(parent/('b'*64))
            return original(p)
        with patch.object(codex_socket,'trusted_daemon_socket',side_effect=changed):
            with self.assertRaises(ControlError) as caught: Codex(self.config).check()
        self.assertIn(caught.exception.code,('codex_socket_untrusted','codex_daemon_unavailable'))
        self.assertGreaterEqual(counter['calls'],2)

    def test_private_codex_symlink_resolves_existing_thread_no_model_call(self):
        link,target,parent=self.linked_daemon()
        self.assertTrue(link.is_symlink())
        self.assertTrue(Codex(self.config).check()['thread_resolved'])
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_symlink_into_untrusted_directory_fails_closed(self):
        link,target,parent=self.linked_daemon()
        parent.chmod(0o777)
        with self.assertRaises(ControlError) as caught: Codex(self.config).check()
        self.assertEqual(caught.exception.code,'codex_socket_untrusted')

    def test_symlink_to_regular_file_is_rejected(self):
        link,target,parent=self.linked_daemon()
        link.unlink()
        candidate=parent/('b'*64); candidate.write_text('not a socket')
        link.symlink_to(candidate)
        with self.assertRaises(ControlError) as caught: Codex(self.config).check()
        self.assertEqual(caught.exception.code,'codex_socket_untrusted')
