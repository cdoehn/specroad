"""Isolated deletion plans and Git repositories; no operator Apply or host pool."""
import base64
from hashlib import sha256
import stat
import subprocess

from verification_support.bundle_apply import NativeApply
from test_apply_commit_plan import bundle, make_plan


def deletion_bundle(raw=b'original\n', name='gone.py'):
    data = bundle()
    data.update(format_version=2, handoff_kind='patch_ready')
    stage = data['stages'][0]
    stage.update(role='implementation', before={name: sha256(raw).hexdigest()}, after={}, payloads={},
                 deletions={name: sha256(raw).hexdigest()},
                 delete_preimages={name: base64.b64encode(raw).decode()},
                 test_plan=make_plan(files=['tests/test_surviving.py']))
    data['stages'] = [stage]
    return data


class GitApply(NativeApply):
    """Exercise the actual file/index/commit boundaries in a disposable repository.

    Test execution is injected; these are driver regressions, not gate receipts.
    Native registration and the real gate retain their existing integration tests.
    """
    def __init__(self, root, data):
        super().__init__(data)
        self.root = root
        self.events = []
        self.gates = []
        self.fail_gate = False

    def location(self):
        assert self.root.name == 'isolated-delete-repository'

    def initial(self, data):
        self.location()
        assert self.head() == data['binding']['base_commit']

    def git(self, *args):
        return subprocess.run(['git', '-c', 'user.name=Deletion Fixture',
            '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false',
            '-c', 'core.hooksPath=' + str(self.root/'empty-hooks'), *args],
            cwd=self.root, stdin=subprocess.DEVNULL, capture_output=True, check=True).stdout

    def publish(self, progress):
        self.events.append(progress)

    def publish_plan(self, plan):
        self.plan = plan

    def test(self, stage, head):
        self.gates.append((head, dict(stage['deletions'])))
        self.absent(stage)
        if self.fail_gate:
            raise ValueError('fixture gate failed')
        return {'selection_sha256': 'e'*64}


def regular_file(path, raw):
    """Create the valid 0644 precondition independently of the worker's umask."""
    path.write_bytes(raw)
    path.chmod(0o644)
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o644
    assert info.st_nlink == 1
    return path


def git_apply(tmp_path, raw=b'original\n'):
    root = tmp_path/'isolated-delete-repository'
    root.mkdir()
    regular_file(root/'gone.py', raw)
    regular_file(root/'survives.py', b'keep\n')
    backend = GitApply(root, deletion_bundle(raw))
    backend.git('init')
    backend.git('add', '--', 'gone.py', 'survives.py')
    backend.git('commit', '-m', 'fixture base')
    backend.data['binding']['base_commit'] = backend.head()
    backend.data['apply_repository'] = str(root)
    return backend


def empty_source(root):
    for name in ('src/specroad', 'tests', 'tools', 'verification'):
        (root/name).mkdir(parents=True, exist_ok=True)
    (root/'pyproject.toml').write_text('[project]\nname="fixture"\nversion="0"\n')
