"""Reusable Apply-only commit sequence. No model calls, retries, reset or CI."""
import base64
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(',', ':')).encode()


def validate_bundle(data):
    fields = {'format_version', 'bundle_number', 'source_result_sha256', 'binding',
              'apply_repository', 'branch', 'initial_dirty', 'stages', 'correction_of'}
    if (type(data) is not dict or set(data) != fields
            or type(data['format_version']) is not int or data['format_version'] != 1
            or type(data['initial_dirty']) is not bool or data['branch'] != 'dev'
            or not re.fullmatch(r'[0-9]{3,}', data['bundle_number'])
            or not re.fullmatch(r'[0-9a-f]{64}', data['source_result_sha256'])
            or not Path(data['apply_repository']).is_absolute()
            or type(data['stages']) is not list or not data['stages']):
        raise ValueError('Invalid Apply bundle plan')
    if set(data['binding']) != {'repo_id', 'base_commit', 'state_fingerprint', 'fingerprint_algorithm'}:
        raise ValueError('Incomplete native Result binding')
    ids = []
    for stage in data['stages']:
        if (set(stage) != {'commit_id', 'message', 'before', 'after', 'payloads', 'source_sha256', 'test_plan'}
                or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', stage['commit_id'])
                or not stage['message'] or '\n' in stage['message'] or '\0' in stage['message']
                or not stage['after'] or set(stage['payloads']) != set(stage['after'])
                or not set(stage['before']) <= set(stage['after'])
                or stage['test_plan']['commit_id'] != stage['commit_id']
                or not re.fullmatch(r'[0-9a-f]{64}', stage['source_sha256'])):
            raise ValueError('Invalid commit stage')
        ids.append(stage['commit_id'])
        for name, digest in {**stage['before'], **stage['after']}.items():
            path = PurePosixPath(name)
            if (path.is_absolute() or str(path) != name or '\\' in name
                    or any(p in ('.', '..', '.git', '.patchharbor') for p in path.parts)
                    or not re.fullmatch(r'[A-Za-z0-9_./-]+', name)
                    or not re.fullmatch(r'[0-9a-f]{64}', digest)):
                raise ValueError('Unsafe stage path or hash')
        for name, encoded in stage['payloads'].items():
            if sha256(base64.b64decode(encoded, validate=True)).hexdigest() != stage['after'][name]:
                raise ValueError('Stage payload differs from its hash')
        changed_tests = {n for n in stage['after'] if n.startswith('tests/')
                         and PurePosixPath(n).name.startswith('test_') and n.endswith('.py')}
        if not changed_tests <= set(stage['test_plan']['test_files']):
            raise ValueError('Every changed test file must be in the required selection')
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate commit IDs')
    if data['correction_of'] is not None:
        proof = data['correction_of']
        if (set(proof) != {'plan_sha256', 'remaining_commit_ids'}
                or not re.fullmatch(r'[0-9a-f]{64}', proof['plan_sha256'])
                or proof['remaining_commit_ids'] != ids):
            raise ValueError('Correction must retain the exact remaining commit sequence')
    return data


def public_plan(data):
    return {**{k: v for k, v in data.items() if k not in ('stages', 'apply_repository')},
            'stages': [{k: v for k, v in s.items() if k != 'payloads'} for s in data['stages']]}


def remaining_commits(plan, progress, *, result_head):
    """Use only with an independently native-validated failed Result and its log."""
    ids = [s['commit_id'] for s in plan['stages']]
    done = progress['committed']
    completed_ids = [s['commit_id'] for s in done]
    if (progress['plan_sha256'] != sha256(canonical(plan)).hexdigest()
            or progress['phase'] != 'failed' or completed_ids != ids[:len(done)]
            or progress['remaining_commit_ids'] != ids[len(done):]
            or progress['actual_head'] != result_head):
        raise ValueError('Unproven remaining commit sequence')
    parent = plan['binding']['base_commit']
    for row in done:
        if row['parent'] != parent or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', row['commit']):
            raise ValueError('Unproven completed commit chain')
        parent = row['commit']
    if result_head != parent:
        raise ValueError('HEAD moved without a proved completed stage; inspect the Result')
    return plan['stages'][len(done):]


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
        if (self.root != Path(self.data['apply_repository']) or self.root.name == 'specroad-codex'
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
        if not (self.root / '.venv/bin/python').is_file():
            raise ValueError('The existing project test interpreter is required')
        self.report_dir = self.workspace()

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
            mode = path.lstat().st_mode
            if (not stat.S_ISREG(mode) or mode & 0o7111
                    or sha256(path.read_bytes()).hexdigest() != digest):
                raise ValueError('Unexpected stage bytes/type/mode: ' + name)

    def before(self, stage, head):
        self.location()
        if self.head() != head or not self.changed() <= set(stage['after']):
            raise ValueError('Foreign changes or HEAD movement before stage')
        self.bytes_match(stage['before'])
        for name in set(stage['after']) - set(stage['before']):
            if os.path.lexists(self.root / name):
                raise ValueError('New stage path already exists: ' + name)

    def install(self, stage):
        from patchharbor.models import BundlePayload
        from patchharbor.payload_files import write_bundle_payloads
        payloads = [BundlePayload(relative_path=name, content=base64.b64decode(raw, validate=True), unix_mode=0o644)
                    for name, raw in stage['payloads'].items()]
        write_bundle_payloads(payloads, cwd=self.root)
        self.bytes_match(stage['after'])

    def pending(self, stage, head):
        self.location()
        if self.head() != head or self.changed() != set(stage['after']):
            raise ValueError('Stage scope differs from the intended commit')
        self.bytes_match(stage['after'])
        if self.git('diff', '--summary') or self.git('diff', '--cached', '--summary'):
            # New regular files are checked after staging; deletions/type/mode
            # changes are deliberately not a supported payload in contract v1.
            if self.git('diff', '--summary'):
                raise ValueError('Unexpected mode, type or deletion change')

    def test(self, stage, head):
        directory = self.report_dir / stage['commit_id']
        directory.mkdir(mode=0o700)
        plan_path = directory / 'test-plan.json'
        plan_path.write_bytes(canonical(stage['test_plan']))
        scratch = directory / 'tmp'; scratch.mkdir(mode=0o700)
        environment = dict(os.environ)
        for key in ('TMPDIR', 'TMP', 'TEMP', 'PYTEST_DEBUG_TEMPROOT'):
            environment[key] = str(scratch)
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
        paths = sorted(stage['after'])
        self.git('add', '--', *paths)
        self.pending(stage, head)
        if (self.names('diff', '--cached', '--no-renames', '--name-only', '-z') != set(paths)
                or self.names('diff', '--no-renames', '--name-only', '-z')
                or self.names('ls-files', '--others', '--exclude-standard', '-z')):
            raise ValueError('Index has unexpected commit contents')
        self.git('diff', '--cached', '--check')
        for name, digest in stage['after'].items():
            if sha256(self.git('show', ':' + name)).hexdigest() != digest:
                raise ValueError('Index bytes differ from the tested stage')
        body = ('SpecRoad-Bundle: ' + self.data['bundle_number'] + '\nSpecRoad-Commit-ID: '
                + stage['commit_id'] + '\nApply-Selection-SHA256: ' + evidence['selection_sha256'])
        output = self.git('commit', '-m', stage['message'], '-m', body)
        print(output.decode(errors='replace'), end='', flush=True)
        completed = self.head()
        if (self.git('rev-parse', 'HEAD^').decode().strip() != head
                or self.git('log', '-1', '--format=%s').decode().strip() != stage['message']
                or self.names('diff', '--no-renames', '--name-only', '-z', head, completed) != set(paths)):
            raise ValueError('Actual commit differs from the tested stage; retain and inspect')
        for name, digest in stage['after'].items():
            if sha256(self.git('show', completed + ':' + name)).hexdigest() != digest:
                raise ValueError('Committed bytes differ from the tested stage')
        return completed

    def clean(self, head):
        self.location()
        if self.head() != head or self.git('status', '--porcelain=v1', '--untracked-files=all', '-z'):
            raise ValueError('The completed commit is not clean')
