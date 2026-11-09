"""Owned temporary materialization and cleanup, independent of project services."""
from pathlib import Path, PurePosixPath
import os
import stat
import shutil
import tempfile
from .values import require


class CheckWorkspace:
    """Fresh private directory, never a project-selected program or output path."""
    def __init__(self, project_root, keep):
        require(type(keep) is bool, 'proposal_debug_boolean_required', exit_code=2)
        self.path = None
        self.identity = None
        self.keep = keep
        self.state = dict(retained=False, path=None, cleanup='not_created')
        self.project_root = Path(project_root).resolve()

    def create(self):
        # gettempdir() probes candidate directories by writing a file. Check
        # each stdlib candidate BEFORE any such write, including the cwd fallback.
        candidates = ((tempfile.tempdir,) if tempfile.tempdir is not None
                      else tempfile._candidate_tempdir_list())
        last_error = None
        for candidate in candidates:
            parent = Path(os.fsdecode(candidate)).resolve()
            require(parent != self.project_root and self.project_root not in parent.parents,
                    'proposal_workspace_inside_project', exit_code=7)
            try:
                self.path = Path(tempfile.mkdtemp(prefix='specroad-proposal-check-', dir=parent))
                break
            except OSError as error:
                last_error = error
        else:
            raise last_error or OSError('No usable private Proposal workspace parent')
        info = self.path.lstat()
        self.identity = (info.st_dev, info.st_ino)
        return self

    def verify(self):
        info = self.path.lstat()
        require(stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == self.identity,
                'proposal_workspace_identity_changed', exit_code=7)

    def materialize(self, name, files):
        self.verify()
        root = self.path / name
        root.mkdir(mode=0o700)
        for path, raw in sorted(files.items()):
            parts = PurePosixPath(path)
            require(type(path) is str and parts.as_posix() == path and not parts.is_absolute()
                    and not any(p in ('', '.', '..') for p in path.split('/')) and '\\' not in path,
                    'proposal_workspace_path_invalid', exit_code=7)
            target = root / path
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(raw)
            target.chmod(0o600)
        return root

    def close(self):
        if self.path is None:
            return
        self.state.update(path=str(self.path), cleanup='failed')
        self.verify()
        if self.keep:
            self.state.update(retained=True, path=str(self.path), cleanup='retained')
        else:
            self.state.update(path=str(self.path), cleanup='failed')
            shutil.rmtree(self.path)
            self.state.update(path=None, cleanup='removed')
