"""SR-FIX-IMPORT-SECURITY-v1: owned inputs and an isolated CPython guard.

The guard denies audited network/process operations, including during Core
imports. Byte parsers additionally run without filesystem opens or writes.
Only the explicitly authorized native transaction may write its owned project.
This is a runtime boundary probe, not an OS sandbox or a release certificate.
"""
from pathlib import Path

from support.portable import build_distribution
from support.processes import SOURCE, run_python


GUARD = r'''
import encodings.cp437  # ZIP filename codec; finish runtime loading before byte-only checks.
import json
import os
import socket
import subprocess
from hashlib import sha256
from pathlib import Path

attempts = []
phase = 'bootstrap'
process_events = {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.spawn',
                  'os.exec', 'os.fork', 'os.forkpty', 'pty.spawn'}
write_events = {'os.mkdir', 'os.remove', 'os.rename', 'os.rmdir', 'os.link',
                'os.symlink', 'os.chmod', 'os.chown', 'os.truncate', 'os.utime'}

class ForbiddenEffect(RuntimeError):
    pass

def guard(event, args):
    forbidden = event.startswith('socket.') or event in process_events
    if phase != 'publish':
        forbidden = forbidden or event in write_events
        if event == 'open':
            path, mode, flags = args
            forbidden = forbidden or (
                isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags, int) and flags & (
                    os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
    if phase == 'parse' and event in {'open', 'os.listdir', 'os.scandir'}:
        forbidden = True
    if forbidden:
        attempts.append(event)
        raise ForbiddenEffect(event)

sys.addaudithook(guard)
'''


def run_isolated(body, cwd, *, mode='core'):
    """Only trusted test code is executed; supplier bytes are literal data.

    -I/-S/-B excludes site packages, project imports and bytecode writes.
    The existing subprocess helper clears PATH and closes stdin. Distribution
    construction happens in the parent, outside the guarded child/project.
    """
    cwd = Path(cwd)
    source = SOURCE
    if mode == 'pyz':
        _, source = build_distribution(cwd.parent / 'distribution')
    else:
        assert mode == 'core'
    prefix = 'import sys;sys.path.insert(0,' + repr(str(source)) + ')\n'
    return run_python(['-I', '-S', '-B', '-c', prefix + GUARD + body], cwd, capture=True)


IMPORTS = '''
from specroad.exchange import (apply_import_plan, select_csv_profile, decode_ndjson,
    decode_reqif, decode_reqif_structure, decode_reqifz, ReqIFLimits)
from specroad.changes import TargetModel, TargetPolicy, PublicationAuthority
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument, ModelGate
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.errors import ModelError
from specroad.mappings import CSVProfile, ExchangeMapping
from specroad.verification import JUnitDocument
'''
