"""Passive Result-to-release contract; no writes, service calls or code execution."""
from hashlib import sha256
import io
from pathlib import PurePosixPath
import re
import zipfile
from .errors import ControlError

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
