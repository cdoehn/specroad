import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from specroad_control.config import initialize
from specroad_control.daemon import request
from specroad_control.errors import ControlError
from specroad_control.local import Paths, REPO
from codex_control_tests.external_temp import temporary_directory

class LocalCase(unittest.TestCase):
    if not hasattr(unittest.TestCase, 'enterContext'):
        def enterContext(self, cm):
            # Python 3.10 equivalent of unittest.TestCase.enterContext (3.11+).
            result = type(cm).__enter__(cm)
            self.addCleanup(type(cm).__exit__, cm, None, None, None)
            return result

    def setUp(self):
        self.temporary = temporary_directory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / "cfg"),
               "XDG_STATE_HOME": str(self.home / "state"), "XDG_RUNTIME_DIR": str(self.home / "run"),
               "SPECROAD_CONTROL_HOME": str(self.home / "control-data"), "PYTHONDONTWRITEBYTECODE": "1"}
        self.environment = patch.dict(os.environ, env)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.paths = Paths.discover()
        from codex_control_tests.integration_support import install_fixture_release
        install_fixture_release(self.paths)

    def spawn(self):
        initialize(self.paths)
        log = tempfile.TemporaryFile()
        self.addCleanup(log.close)
        child = subprocess.Popen([sys.executable, "-B", str(self.paths.home / 'releases' / ('a' * 40) / 'control'), "run"],
                                 env=dict(os.environ), stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        self.last_worker_process, self.last_worker_log = child, log
        def cleanup():
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
        self.addCleanup(cleanup)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if child.poll() is not None:
                log.seek(0)
                self.fail(log.read().decode())
            try:
                reply = request(self.paths, "status")
                return child, reply
            except ControlError as exc:
                if exc.code != "not_running":
                    raise
            time.sleep(0.02)
        self.fail("Worker startup timed out")
