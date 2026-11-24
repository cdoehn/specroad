"""Reusable Apply-only commit sequence. No model calls, retries, reset or CI."""
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile


from .bundle_contract import canonical, validate_bundle, public_plan, remaining_commits, DELETION_CAPABILITY_PATH, DELETION_CAPABILITY
from .bundle_delete import delete_bound_file


def run_bundle(data, backend):
    """A failed stage ends the sequence; previous commits and current files survive."""
    validate_bundle(data)
    plan = public_plan(data)
    plan_hash = sha256(canonical(plan)).hexdigest()
    committed = []
    head = data['binding']['base_commit']
    stage = None

    def publish(phase, error=None):
        progress = {'format_version': 1, 'kind': 'specroad-apply-progress-v1',
                    'plan_sha256': plan_hash, 'source_result_sha256': data['source_result_sha256'],
                    'phase': phase, 'committed': list(committed),
                    'active_commit_id': None if stage is None else stage['commit_id'],
                    'remaining_commit_ids': [s['commit_id'] for s in data['stages'][len(committed):]],
                    'actual_head': backend.head(), 'error': error}
        backend.publish(progress)
        return progress

    backend.publish_plan(plan)
    try:
        backend.initial(data)
        publish('started')
        for stage in data['stages']:
            backend.before(stage, head)
            publish('materializing')
            backend.install(stage)
            backend.pending(stage, head)
            publish('testing')
            evidence = backend.test(stage, head)
            backend.pending(stage, head)
            publish('committing')
            completed = backend.commit(stage, head, evidence)
            committed.append({'commit_id': stage['commit_id'], 'parent': head,
                              'commit': completed, 'gate': evidence})
            head = completed
            publish('committed')
            backend.clean(head)
        stage = None
        return publish('completed')
    except Exception as error:
        publish('failed', str(error))
        raise


class NativeApply:
    """Host operations used only by the PatchHarbor entrypoint, never Development."""

    def __init__(self, data):
        self.data = data
        self.root = Path.cwd().resolve()
        self.report_dir = None
        self.event = 0

    def git(self, *args):
        return subprocess.run(['git', '--no-optional-locks', *args], cwd=self.root,
                              stdin=subprocess.DEVNULL, capture_output=True, check=True).stdout

    def head(self):
        return self.git('rev-parse', 'HEAD').decode().strip()

    def location(self):
        if (self.root != Path(self.data['apply_repository']) or self.root.name in ('specroad-codex', 'specroad-dev', 'specroad-dev2')
                or Path(self.git('rev-parse', '--show-toplevel').decode().strip()) != self.root
                or self.git('branch', '--show-current').decode().strip() != self.data['branch']):
            raise ValueError('The bound Apply repository and branch are required')

    def initial(self, data):
        from patchharbor.repository import inspect_local_registration, inspect_repository_root
        from patchharbor.repository_state import capture_consistent_repository_snapshot, repository_context_from_snapshot
        self.location()
        repository = inspect_repository_root(self.root)
        repo_id, _ = inspect_local_registration(repository)
        snapshot = capture_consistent_repository_snapshot(repository, read_only=True)
        context = repository_context_from_snapshot(repository, repo_id, snapshot)
        if ({k: str(getattr(context, k)) for k in data['binding']} != data['binding']
                or context.dirty is not data['initial_dirty']):
            raise ValueError('Apply does not match the exact authoritative Result state')
        if any(stage.get('deletions') for stage in data['stages']):
            self.require_deletion_support()
        if not (self.root / '.venv/bin/python').is_file():
            raise ValueError('The existing project test interpreter is required')
        self.report_dir = self.workspace()

    def require_deletion_support(self):
        expected = canonical(DELETION_CAPABILITY) + b'\n'
        self.bytes_match({DELETION_CAPABILITY_PATH: sha256(expected).hexdigest()})
        if self.git('show', self.data['binding']['base_commit'] + ':' + DELETION_CAPABILITY_PATH) != expected:
            raise ValueError('Deletion support is not committed in the bound source')

    def workspace(self):
        parent = self.root / 'build'
        if parent.exists() or parent.is_symlink():
            if not stat.S_ISDIR(parent.lstat().st_mode):
                raise ValueError('A real build directory is required')
        else:
            parent.mkdir(mode=0o700)
        probe = 'build/specroad-apply-commit-probe'
        if (self.git('check-ignore', '--', probe).decode().strip() != probe
                or self.git('ls-files', '--cached', '--', 'build')
                or parent.stat().st_dev != self.root.stat().st_dev):
            raise ValueError('Apply reports require an ignored local build directory')
        return Path(tempfile.mkdtemp(prefix='apply-' + self.data['bundle_number'] + '-', dir=parent))

    def publish_plan(self, plan):
        print('SPECROAD_APPLY_PLAN ' + canonical(plan).decode(), flush=True)

    def publish(self, progress):
        raw = canonical(progress) + b'\n'
        if self.report_dir is not None:
            with (self.report_dir / ('progress-%04d.json' % self.event)).open('xb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            descriptor = os.open(self.report_dir, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            self.event += 1
        print('SPECROAD_APPLY_PROGRESS ' + raw.decode().rstrip(), flush=True)

    def names(self, *args):
        return {n.decode() for n in self.git(*args).split(b'\0') if n}

    def changed(self):
        return (self.names('diff', '--cached', '--no-renames', '--name-only', '-z')
                | self.names('diff', '--no-renames', '--name-only', '-z')
                | self.names('ls-files', '--others', '--exclude-standard', '-z'))

    def bytes_match(self, expected):
        for name, digest in expected.items():
            path = self.root / name
            for parent in path.parents:
                if not stat.S_ISDIR(parent.lstat().st_mode):
                    raise ValueError('Linked stage parent: ' + name)
            info = path.lstat()
            mode = info.st_mode
            if (not stat.S_ISREG(mode) or mode & 0o7111 or info.st_nlink != 1
                    or sha256(path.read_bytes()).hexdigest() != digest):
                raise ValueError('Unexpected stage bytes/type/mode: ' + name)

    def before(self, stage, head):
        self.location()
        scope = set(stage['after']) | set(stage.get('deletions', {}))
        if self.head() != head or not self.changed() <= scope:
            raise ValueError('Foreign changes or HEAD movement before stage')
        self.bytes_match(stage['before'])
        for name in scope - set(stage['before']):
            if os.path.lexists(self.root / name):
                raise ValueError('New stage path already exists: ' + name)
        for name in stage.get('deletions', {}):
            delete_bound_file(self.root, name, stage['deletions'][name],
                              absent=name not in stage['before'], remove=False)

    def install(self, stage):
        if stage['payloads']:
            from patchharbor.models import BundlePayload
            from patchharbor.payload_files import write_bundle_payloads
            payloads = [BundlePayload(relative_path=name, content=base64.b64decode(raw, validate=True), unix_mode=0o644)
                        for name, raw in stage['payloads'].items()]
            write_bundle_payloads(payloads, cwd=self.root)
        for name, digest in stage.get('deletions', {}).items():
            delete_bound_file(self.root, name, digest, absent=name not in stage['before'])
        self.bytes_match(stage['after'])
        self.absent(stage)

    def absent(self, stage):
        for name, digest in stage.get('deletions', {}).items():
            delete_bound_file(self.root, name, digest, absent=True, remove=False)

    def commit_scope(self, stage, head):
        """A bound uncommitted preimage is absent from the final tree, not a Git D."""
        removed = set(stage.get('deletions', {}))
        tracked = (self.names('ls-tree', '-r', '--name-only', '-z', head, '--', *sorted(removed))
                   if removed else set())
        return set(stage['after']) | (removed & tracked)

    def pending(self, stage, head):
        self.location()
        committed_scope = self.commit_scope(stage, head)
        removed = set(stage.get('deletions', {}))
        indexed = (self.names('ls-files', '-z', '--', *sorted(removed))
                   if removed else set())
        temporary_additions = (removed & indexed) - committed_scope
        if (not committed_scope or self.head() != head
                or self.changed() != (committed_scope | temporary_additions)):
            raise ValueError('Stage scope differs from the intended commit')
        self.bytes_match(stage['after'])
        self.absent(stage)
        for cached in ((), ('--cached',)):
            records = self.git('diff', *cached, '--raw', '--no-abbrev', '--no-renames', '-z').split(b'\0')
            if records[-1] != b'' or (len(records) - 1) % 2:
                raise ValueError('Malformed staged change inventory')
            for index in range(0, len(records) - 1, 2):
                old, new, _, _, kind = records[index].split()
                name = records[index + 1].decode()
                if kind == b'D':
                    valid = name in stage.get('deletions', {}) and old == b':100644' and new == b'000000'
                elif cached and kind == b'A' and name in temporary_additions:
                    # Removing a staged addition cancels it. Its index bytes must
                    # still be the exact bound preimage, never arbitrary data.
                    valid = (old == b':000000' and new == b'100644'
                             and sha256(self.git('show', ':' + name)).hexdigest() == stage['deletions'][name])
                else:
                    valid = (name in stage['after'] and kind in (b'A', b'M')
                             and old == (b':000000' if kind == b'A' else b':100644') and new == b'100644')
                if not valid:
                    raise ValueError('Unplanned deletion, type, mode or rename change')

    def test(self, stage, head):
        directory = self.report_dir / stage['commit_id']
        directory.mkdir(mode=0o700)
        plan_path = directory / 'test-plan.json'
        plan_path.write_bytes(canonical(stage['test_plan']))
        scratch = directory / 'tmp'; scratch.mkdir(mode=0o700)
        environment = dict(os.environ)
        for key in ('TMPDIR', 'TMP', 'TEMP', 'PYTEST_DEBUG_TEMPROOT'):
            environment[key] = str(scratch)
        # This is an evidence check, never a benchmark. A final stage requires
        # it even if somebody removed the development policy file. Toy runner
        # projects without this project-specific obligation remain unaffected.
        policy = self.root / 'verification/resource_measurement_policy.json'
        if policy.exists() or policy.is_symlink() or stage['commit_id'].startswith('20.n.'):
            subprocess.run([str(self.root / '.venv/bin/python'), '-I', '-B',
                            'tools/check_analyzer_resources.py', '--commit-id', stage['commit_id']],
                           cwd=self.root, env=environment, stdin=subprocess.DEVNULL, check=True)
        code = subprocess.run([str(self.root / '.venv/bin/python'), '-I', '-B',
                               'tools/run_apply_tests.py', '--test-plan', str(plan_path),
                               '--commit-id', stage['commit_id'], '--outdir', str(directory / 'gate')],
                              cwd=self.root, env=environment, stdin=subprocess.DEVNULL, check=False).returncode
        if code:
            raise ValueError('Apply tests failed before commit ' + stage['commit_id'])
        # Use a fresh interpreter so later phases cannot reuse an earlier
        # imported runner/validator after those source files have changed.
        command = [str(self.root / '.venv/bin/python'), '-I', '-B',
                   'tools/verify_apply_commit.py', '--gate', str(directory / 'gate'),
                   '--source', stage['source_sha256'], '--head', head, '--test-plan', str(plan_path)]
        result = subprocess.run(command, cwd=self.root, stdin=subprocess.DEVNULL,
                                capture_output=True, check=True)
        return json.loads(result.stdout)

    def commit(self, stage, head, evidence):
        paths = sorted(set(stage['after']) | set(stage.get('deletions', {})))
        committed_scope = self.commit_scope(stage, head)
        # A failed commit may have already removed a path from the index.
        # Its cached deletion is still checked below, without an unmatched add.
        index_paths = self.names('ls-files', '-z', '--', *paths)
        to_add = sorted(set(stage['after']) | (set(stage.get('deletions', {})) & index_paths))
        if to_add:
            self.git('add', '-A', '--', *to_add)
        self.pending(stage, head)
        if (self.names('diff', '--cached', '--no-renames', '--name-only', '-z') != committed_scope
                or self.names('diff', '--no-renames', '--name-only', '-z')
                or self.names('ls-files', '--others', '--exclude-standard', '-z')):
            raise ValueError('Index has unexpected commit contents')
        self.git('diff', '--cached', '--check')
        indexed = set()
        for record in self.git('ls-files', '--stage', '-z', '--', *paths).split(b'\0'):
            if record:
                metadata, name = record.split(b'\t', 1)
                indexed.add(name.decode())
                mode, _, index_stage = metadata.split()
                if mode != b'100644' or index_stage != b'0':
                    raise ValueError('Index mode or merge stage differs from regular payloads')
        if indexed != set(stage['after']):
            raise ValueError('Index contains a deleted file or omits a tested file')
        for name, digest in stage['after'].items():
            if sha256(self.git('show', ':' + name)).hexdigest() != digest:
                raise ValueError('Index bytes differ from the tested stage')
        final = stage['commit_id'] == self.data['stages'][-1]['commit_id']
        body = ('SpecRoad-Bundle: ' + self.data['bundle_number']
                + '\nSpecRoad-Bundle-Final: ' + str(final).lower() + '\nSpecRoad-Commit-ID: '
                + stage['commit_id'] + '\nApply-Selection-SHA256: ' + evidence['selection_sha256'])
        output = self.git('commit', '-m', stage['message'], '-m', body)
        print(output.decode(errors='replace'), end='', flush=True)
        completed = self.head()
        if (self.git('rev-parse', 'HEAD^').decode().strip() != head
                or self.git('log', '-1', '--format=%s').decode().strip() != stage['message']
                or self.names('diff', '--no-renames', '--name-only', '-z', head, completed) != committed_scope):
            raise ValueError('Actual commit differs from the tested stage; retain and inspect')
        for name, digest in stage['after'].items():
            if sha256(self.git('show', completed + ':' + name)).hexdigest() != digest:
                raise ValueError('Committed bytes differ from the tested stage')
        if self.names('ls-tree', '-r', '--name-only', '-z', completed, '--', *paths) != set(stage['after']):
            raise ValueError('Committed tree contains a deleted file')
        self.absent(stage)
        return completed

    def clean(self, head):
        self.location()
        if self.head() != head or self.git('status', '--porcelain=v1', '--untracked-files=all', '-z'):
            raise ValueError('The completed commit is not clean')
