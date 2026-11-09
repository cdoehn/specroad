"""SSH native authentication and private multiplexing; no credential handling."""
from hashlib import sha256
import json
import shlex
import subprocess

from .config import state_directory


class Transport:
    def __init__(self, host, *, runner=None, state=None):
        self.host = host
        self.runner = subprocess.run if runner is None else runner
        self.state = state or state_directory()

    @property
    def socket(self):
        return str(self.state / ('ssh-' + sha256(self.host.ssh.encode()).hexdigest()[:16]))

    def options(self, *, interactive=False):
        return ['-o', 'ControlMaster=auto', '-o', 'ControlPersist=' + str(self.host.persist),
                '-o', 'ControlPath=' + self.socket, '-o', 'ForwardAgent=no',
                '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=20',
                '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3',
                '-o', 'BatchMode=' + ('no' if interactive else 'yes')]

    def run(self, args, *, input=None, interactive=False, timeout=120, check=True):
        command = list(args)
        if self.host.ssh is not None:
            command = ['ssh', *self.options(interactive=interactive),
                       *(['-tt'] if interactive else ['-T']), self.host.ssh, shlex.join(command)]
        result = self.runner(command, input=input, text=True, timeout=timeout,
                             capture_output=not interactive, check=False)
        if check and result.returncode:
            raise ValueError(f'{self.host.name}: command failed ({result.returncode}); check SSH/environment')
        return result

    def copy(self, source, target):
        args = ['rsync', '-rltp', '--']
        if self.host.ssh is not None:
            args[1:1] = ['-e', shlex.join(['ssh', *self.options()])]
            target = self.host.ssh + ':' + str(target)
        result = self.runner([*args, str(source), str(target)], timeout=600, check=False, capture_output=True)
        if result.returncode:
            raise ValueError(self.host.name + ': snapshot transfer failed')

    def python(self, script, *, executable=None, timeout=120):
        # Manifests can exceed execve's per-argument limit. Stream the program
        # over stdin; never embed a complete snapshot in a shell argument.
        result = self.run([executable or 'python3', '-I', '-B', '-'], input=script, timeout=timeout)
        try:
            return json.loads(result.stdout)
        except (ValueError, TypeError) as error:
            raise ValueError(self.host.name + ': invalid remote response') from error

    def control(self, action):
        if self.host.ssh is None:
            return {'host': self.host.name, 'local': True}
        if action == 'connect':
            # Native SSH/agent/askpass prompt; the master persists only when idle.
            self.run(['true'], interactive=True)
        operation = 'exit' if action == 'disconnect' else 'check'
        result = self.runner(['ssh', *self.options(), '-O', operation, self.host.ssh],
                             timeout=30, capture_output=True, text=True, check=False)
        return {'host': self.host.name, 'connected': result.returncode == 0 and operation == 'check',
                'exit_code': result.returncode, 'idle_seconds': self.host.persist}
