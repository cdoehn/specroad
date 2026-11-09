"""Local runner history with one host/environment capture per process."""
import platform

from .runtime_history import RuntimeHistory
from .runtime_environment import environment, digest


class LocalRuntimeHistory(RuntimeHistory):
    """Tag newly started local attempts without relabelling old measurements."""

    def __init__(self, root, *, path=None):
        self.local_host = platform.node()
        if (not isinstance(self.local_host, str) or not 1 <= len(self.local_host) <= 255
                or self.local_host != self.local_host.strip()
                or any(ord(c) < 33 or ord(c) == 127 for c in self.local_host)):
            raise ValueError('Local runtime history requires an observed hostname')
        self.local_environment = digest(environment())
        super().__init__(root, path=path)

    def start(self, run, node, identity, worker):
        super().start(run, node, identity, worker,
                      host=self.local_host, environment=self.local_environment)

    def verify_run(self, run, pairs, outcomes):
        super().verify_run(run, pairs, outcomes)
        rows = self.db.execute('SELECT h.host,h.environment FROM attempts a LEFT JOIN attempt_hosts h ON h.attempt=a.id WHERE a.run=?', (run,)).fetchall()
        if any(row != (self.local_host, self.local_environment) for row in rows):
            raise ValueError('Local runtime history has missing or changed host metadata')
