"""Pin a stopped service to code from a successful, natively verified Apply Result."""
from contextlib import ExitStack
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import zipfile
from .errors import ControlError
from .local import outside, private_dir, lock, json_read, json_write, read_private, write_private

PREFIX = 'base/tools/dev/codex/control/'


def reject():
    raise ControlError('release_unproven', 'A complete successful clean SpecRoad Apply Result with Control code is required.')


def release_files(raw, facts, repo_id):
    if (facts.get('kind') != 'result' or facts.get('operation') != 'apply' or facts.get('dry_run') is not False
            or facts.get('success') is not True or facts.get('dirty') is not False or facts.get('entrypoint_started') is not True
            or facts.get('completed_commit') != facts.get('binding', {}).get('base_commit')
            or facts.get('binding', {}).get('repo_id') != repo_id
            or sha256(raw).hexdigest() != facts.get('sha256')):
        reject()
    if re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', str(facts.get('completed_commit'))) is None:
        reject()
    files = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if len(set(archive.namelist())) != len(archive.namelist()):
            reject()
        for info in archive.infolist():
            if not info.filename.startswith(PREFIX):
                continue
            name = info.filename[len(PREFIX):]
            p = PurePosixPath(name)
            if p.is_absolute() or str(p) != name or any(part in ('.', '..') for part in p.parts):
                reject()
            if name == 'control' or (name.startswith('specroad_control/') and name.endswith('.py')):
                if (info.file_size > 65536 or (info.external_attr >> 16) & 0o170000 not in (0, 0o100000)
                        or not re.fullmatch(r'control|specroad_control/[A-Za-z0-9_]+\.py', name)):
                    reject()
                files[name] = archive.read(info)
    if not {'control', 'specroad_control/__init__.py', 'specroad_control/cli.py',
            'specroad_control/releases.py', 'specroad_control/migration.py'} <= set(files):
        reject()
    return files


def verify_release(paths, receipt):
    if (not isinstance(receipt, dict) or type(receipt.get('format_version')) is not int
            or receipt['format_version'] != 1
            or not isinstance(receipt.get('commit'), str)
            or re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', receipt['commit']) is None
            or not isinstance(receipt.get('result_sha256'), str)
            or re.fullmatch(r'[0-9a-f]{64}', receipt['result_sha256']) is None
            or not isinstance(receipt.get('files'), dict) or not receipt['files']):
        reject()
    from .release_reader import release_bytes
    from .local import decode_object
    root = paths.home / 'releases' / receipt['commit']
    try:
        files = release_bytes(root, set(receipt['files']) | {'release.json'})
        for name, digest in receipt['files'].items():
            if (not isinstance(digest, str) or re.fullmatch(r'[0-9a-f]{64}', digest) is None
                    or sha256(files[name]).hexdigest() != digest):
                reject()
        if decode_object(files['release.json']) != receipt:
            reject()
    except (OSError, ValueError, UnicodeError):
        reject()
    return root


def active_entrypoint(paths):
    from .migration import require_complete
    require_complete(paths)
    deployment = json_read(paths.home / 'deployment.json')
    if deployment is not None and deployment.get('phase') not in ('completed', 'rolled_back'):
        raise ControlError('deployment_incomplete', 'Finish the explicit offline deployment before starting Control.')
    receipt = json_read(paths.home / 'active-release.json')
    return verify_release(paths, receipt) / 'control'


def tested_apply(facts):
    """Reuse the existing passive gate/commit evidence contract, never Result code."""
    from .apply_reconcile_proof import member, completion
    from .local import decode_object
    try:
        lines = member(facts, 'logs/execution.log').decode().splitlines()
        plans = [decode_object(line[len('SPECROAD_APPLY_PLAN '):])
                 for line in lines if line.startswith('SPECROAD_APPLY_PLAN ')]
        if (len(plans) != 1 or plans[0].get('binding') != facts.get('expected')
                or not plans[0].get('stages')):
            reject()
        completion(facts, plans[0])
    except (KeyError, TypeError, ValueError, UnicodeError):
        reject()


def deploy(paths, result):
    from . import service
    from .config import load
    from .core import Core
    from .migration import stopped, require_complete
    require_complete(paths)
    config = load(paths)
    config_bytes = read_private(paths.config)
    path = Path(result)
    if not path.is_absolute() or not path.is_file():
        reject()
    # Core parses this as data. Nothing is imported or executed from the Result.
    facts = Core(config).result(path)
    if path.stat().st_size > 512 * 1024 * 1024:
        reject()
    files = release_files(path.read_bytes(), facts, config.repo_id)
    tested_apply(facts)
    receipt = {'format_version': 1, 'commit': facts['binding']['base_commit'],
               'result_sha256': facts['sha256'], 'files': {n: sha256(b).hexdigest() for n,b in files.items()}}
    private_dir(paths.home)
    with ExitStack() as stack:
        for name in ('operation.lock', 'worker.lock'):
            stack.enter_context(lock(paths.state/name))
        if read_private(paths.config) != config_bytes:
            reject()
        stopped(paths, allow_uninstalled=True)
        root = paths.home / 'releases' / receipt['commit']
        private_dir(root)
        for name, raw in files.items():
            target = root/name
            if target.exists():
                if read_private(target) != raw:
                    reject()
            else:
                private_dir(target.parent)
                write_private(target, raw, exclusive=True)
        previous_receipt = json_read(root/'release.json')
        if previous_receipt not in (None, receipt):
            reject()
        json_write(root/'release.json', receipt)
        verify_release(paths, receipt)
        pending = json_read(paths.home/'deployment.json')
        current = json_read(paths.home/'active-release.json')
        old_unit = read_private(paths.unit) if paths.unit.exists() else None
        expected_unit = service.unit_text(paths, entrypoint=root/'control').encode()
        if pending is not None and pending.get('phase') not in ('completed', 'rolled_back', 'switching'):
            reject()
        if pending and pending.get('phase') == 'switching':
            if (pending.get('format_version') != 1 or pending.get('next') != receipt
                    or current not in (pending.get('previous'), receipt)):
                reject()
            original = pending.get('previous_unit')
            if original is not None and not isinstance(original, str):
                reject()
            original = None if original is None else original.encode()
            if old_unit not in (original, expected_unit):
                reject()
            previous, old_unit, journal = pending['previous'], original, pending
        else:
            previous = current
            journal = {'format_version': 1, 'phase': 'switching', 'previous': previous,
                       'next': receipt, 'previous_unit': None if old_unit is None else old_unit.decode()}
            json_write(paths.home/'deployment.json', journal)
        json_write(paths.home/'active-release.json', receipt)
        try:
            private_dir(paths.logs)
            from .local import user_dir
            user_dir(paths.unit.parent)
            write_private(paths.unit, expected_unit)
            service.checked(['daemon-reload'])
        except BaseException:
            if old_unit is None:
                if paths.unit.exists():
                    paths.unit.unlink()
            else:
                write_private(paths.unit, old_unit)
            if previous is None:
                (paths.home/'active-release.json').unlink()
            else:
                json_write(paths.home/'active-release.json', previous)
            # Reload the restored unit. Failure leaves an explicit unfinished journal.
            service.checked(['daemon-reload'])
            json_write(paths.home/'deployment.json', dict(journal, phase='rolled_back'))
            raise
        json_write(paths.home/'deployment.json', dict(journal, phase='completed'))
    return {'deployed': True, 'commit': receipt['commit'], 'started': False, 'history_rewritten': False}
