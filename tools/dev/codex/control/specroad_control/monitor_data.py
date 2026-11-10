"""Read-only Control observations; never open a ledger or acquire a lock."""
import os
import subprocess
import time
from .config import parse
from .errors import ControlError
from .ipc import request
from .local import Paths, json_read, read_private
from .state import read_state
from .toml_compat import tomllib


def discover(instance=None, *, all_instances=False):
    if not all_instances:
        return [Paths.discover(instance=instance)], []
    base = Paths.discover(instance='default')
    paths, errors = [base], []
    directory = base.home / 'instances'
    if directory.is_symlink():
        raise ControlError('unsafe_path', 'The instances directory must not be a symbolic link.')
    if not directory.exists():
        return paths, errors
    with os.scandir(directory) as entries:
        names = []
        for entry in entries:
            if len(names) >= 63:
                raise ControlError('too_many_instances', 'Select an instance explicitly; at most 64 are shown together.')
            names.append(entry.name)
    for name in sorted(names):
        try:
            if name == 'default':
                raise ControlError('invalid_instance', 'The default instance uses its existing root.')
            paths.append(Paths.discover(instance=name))
        except (OSError, ControlError) as exc:
            errors.append({'instance': name, 'error': getattr(exc, 'code', 'local_io_error')})
    return paths, errors


def systemd(paths):
    # Inspection only, with a smaller deadline than lifecycle commands.
    fields = 'LoadState,ActiveState,SubState,UnitFileState,MainPID,FragmentPath'
    reply = subprocess.run(['/usr/bin/systemctl', '--user', 'show', paths.unit.name, '--property=' + fields],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=0.75, check=False)
    if reply.returncode not in (0, 4) or len(reply.stdout) > 16384:
        raise ControlError('systemd_unavailable', 'No bounded systemd status is available.')
    props = dict(line.split('=', 1) for line in reply.stdout.splitlines() if '=' in line)
    if 'LoadState' not in props:
        raise ControlError('systemd_unavailable', 'The manager returned no unit information.')
    return props


def collect(paths):
    report = {'instance': paths.instance, 'observed_at': time.time(), 'source': None,
              'stale': True, 'worker_reachable': False, 'state': None, 'errors': {},
              'paths': {name: str(getattr(paths, name)) for name in ('config', 'state', 'socket', 'logs', 'unit')}}
    try:
        reply = request(paths, 'status')
        if not isinstance(reply.get('state'), dict):
            raise ControlError('protocol_error', 'Control returned no state object.')
        report.update(state=reply['state'], stale=False, worker_reachable=True, source='ipc')
    except (ControlError, OSError) as exc:
        report['errors']['ipc'] = getattr(exc, 'code', 'local_io_error')
        try:
            report.update(state=read_state(paths), source='state-file')
        except (ControlError, OSError) as saved:
            report['errors']['state'] = getattr(saved, 'code', 'local_io_error')
    try:
        config = parse(tomllib.loads(read_private(paths.config).decode()), paths)
        report['configured_bindings'] = {'repository': str(config.repository),
            'apply_repository': str(config.apply_directory), 'exchange': str(config.exchange),
            'repo_id': config.repo_id, 'thread_id': config.session_id, 'enabled': config.enabled,
            'transport': config.transport, 'access_mode': config.access_mode}
    except (ControlError, OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        report['errors']['config'] = getattr(exc, 'code', 'invalid_config')
    try:
        if 'configured_bindings' in report and config.enabled:
            from .monitor_history import history
            report['history'] = history(paths, config)
        report['handover'] = json_read(paths.state/'thread-handover-state.json')
    except (ControlError, OSError) as exc:
        report['errors']['history'] = getattr(exc, 'code', 'history_unavailable')
    try:
        receipt = json_read(paths.home/'active-release.json')
        report['installed_release'] = None if receipt is None else {
            'commit': receipt.get('commit'), 'result_sha256': receipt.get('result_sha256'),
            'evidence': 'receipt_only'}
    except (ControlError, OSError) as exc:
        report['errors']['release'] = getattr(exc, 'code', 'local_io_error')
    try:
        report['systemd'] = systemd(paths)
    except (ControlError, OSError, subprocess.TimeoutExpired) as exc:
        report['errors']['systemd'] = getattr(exc, 'code', 'systemd_unavailable')
    report['observed_at'] = time.time()
    return report
