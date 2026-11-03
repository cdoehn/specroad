"""Read-only working-tree guard, including staged state and nonignored new files.

This is a guard against changing Dev work, not a proof that arbitrary shell tools
had no external side effects. Retry eligibility additionally uses a strict tool
allowlist and a confirmed terminal Codex turn.
"""
import hashlib
import os
from pathlib import Path
import stat
import subprocess
from .errors import ControlError

MAX_FILES = 100000
MAX_BYTES = 512 * 1024 * 1024
MAX_FILE = 128 * 1024 * 1024


def fingerprint(repository):
    env = dict(os.environ)
    env['GIT_OPTIONAL_LOCKS'] = '0'
    for key in list(env):
        if key in ('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_COMMON_DIR','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES') or key.startswith('GIT_CONFIG_'):
            env.pop(key,None)
    env['GIT_CONFIG_NOSYSTEM'] = '1'
    digest = hashlib.sha256()
    root = repository.resolve()
    budget = 0

    def add(data):
        nonlocal budget
        budget += len(data)
        if budget > MAX_BYTES:
            raise ControlError('retry_workspace_unproven', 'Workspace guard exceeds its bounded read budget.')
        digest.update(str(len(data)).encode()+b':'+data)

    def git(*args):
        try:
            result = subprocess.run(['git','-c','core.fsmonitor=false','-C',str(root),*args],
                                    env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL,timeout=15,check=False)
        except (OSError,subprocess.TimeoutExpired):
            raise ControlError('retry_workspace_unproven', 'Cannot read the Dev Git state.') from None
        if result.returncode or len(result.stdout) > 16 * 1024 * 1024:
            raise ControlError('retry_workspace_unproven', 'Cannot read the Dev Git state within its budget.')
        return result.stdout

    if Path(os.fsdecode(git('rev-parse','--show-toplevel')).strip()).resolve() != root:
        raise ControlError('retry_workspace_unproven', 'Dev must be its actual Git working-tree root.')
    initial_head = git('rev-parse','HEAD')
    add(initial_head)
    # Includes staged intent without refreshing/writing the index.
    initial_index = git('diff','--cached','--binary','--no-ext-diff','--no-textconv')
    add(initial_index)
    initial_names = git('ls-files','--cached','--others','--exclude-standard','-z')
    names = sorted(set(initial_names.split(b'\0')) - {b''})
    if len(names) > MAX_FILES:
        raise ControlError('retry_workspace_unproven','Workspace file count exceeds the read budget.')
    try:
        for name in names:
            relative = Path(os.fsdecode(name))
            if relative.is_absolute() or '..' in relative.parts or '.git' in relative.parts:
                raise ControlError('retry_workspace_unproven','Unexpected Git path in workspace guard.')
            path = root / relative
            if any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents):
                raise ControlError('retry_workspace_unproven','Symlink parent in Dev is ambiguous.')
            add(name)
            try:
                before = path.lstat()
            except FileNotFoundError:
                add(b'missing');continue
            add(str(stat.S_IMODE(before.st_mode)).encode())
            if stat.S_ISLNK(before.st_mode):
                add(b'link');add(os.fsencode(os.readlink(path)))
            elif stat.S_ISREG(before.st_mode) and before.st_size <= MAX_FILE:
                add(b'file')
                fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                try:
                    opened = os.fstat(fd)
                    if (opened.st_dev,opened.st_ino) != (before.st_dev,before.st_ino):
                        raise ControlError('retry_workspace_changed','Dev changed during the guard read.')
                    # Fixed block boundaries keep the digest independent of short reads.
                    with os.fdopen(fd,'rb',closefd=False) as stream:
                        while True:
                            block = stream.read(1024*1024)
                            if not block:break
                            add(block)
                finally:
                    os.close(fd)
            else:
                raise ControlError('retry_workspace_unproven','Unsupported or oversized Dev file.')
            after = path.lstat()
            if (before.st_dev,before.st_ino,before.st_mode,before.st_size,before.st_mtime_ns,before.st_ctime_ns) != (after.st_dev,after.st_ino,after.st_mode,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                raise ControlError('retry_workspace_changed','Dev changed during the guard read.')
    except OSError:
        raise ControlError('retry_workspace_unproven','A Dev file could not be safely read.') from None
    if (git('rev-parse','HEAD') != initial_head
            or git('diff','--cached','--binary','--no-ext-diff','--no-textconv') != initial_index
            or git('ls-files','--cached','--others','--exclude-standard','-z') != initial_names):
        raise ControlError('retry_workspace_changed','Dev Git state changed during the guard read.')
    return digest.hexdigest()
