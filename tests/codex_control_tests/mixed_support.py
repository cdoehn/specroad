"""Typed native-container doubles, complete file maps; never execute their code."""
import base64
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from codex_control_tests.external_temp import temporary_directory
import unittest
from unittest.mock import patch
from uuid import uuid4
import zipfile

from specroad_control.automation import Engine, Gate
from specroad_control.apply_reconcile_proof import canonical, hashed, public_plan
from specroad_control.job_contract import scope
from specroad_control.ledger import Ledger
from specroad_control.config import Config
from specroad_control.local import Paths, private_dir
from specroad_control.mixed_contract import CAPABILITY, CAPABILITY_PATH, MIXED
from codex_control_tests.automation_support import AutomationCase, read_package
from codex_control_tests.apply_reconcile_support import patch_package, ReconcileCore
from codex_control_tests.blocked_chain_support import snapshot_members, stage, log_for

SPEC = 'docs/specification/SpecRoad_Spezifikation.md'
PLAN = 'docs/implementation/SpecRoad_Implementierungsplan.md'


def write_result(fact, base, work, log):
    tracked, untracked, members = snapshot_members(base, work)
    path = Path(fact['path'])
    with zipfile.ZipFile(path) as archive:
        data = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(data['manifest.json'])
    manifest.update(base_entries=tracked, untracked_entries=untracked)
    data.update(members)
    data['manifest.json'] = canonical(manifest)
    data['logs/execution.log'] = log
    with zipfile.ZipFile(path, 'w') as archive:
        for name, raw in data.items():
            archive.writestr(name, raw)
    return read_package(path)


def postimage(files, stages):
    result = dict(files)
    for value in stages:
        result.update({name: base64.b64decode(raw) for name, raw in value['payloads'].items()})
    return result


class TypedCodex:
    def __init__(self, case):
        self.case, self.calls, self.schemas = case, 0, []
        self.kind = 'patch_ready'
        self.transform = lambda data: data
        self.data = None

    def run(self, prompt, schema, directory, *, authorize, **kwargs):
        assert authorize()
        self.calls += 1
        self.schemas.append(deepcopy(schema))
        ref = json.loads(prompt.splitlines()[1])
        source = self.case.engine.core.result(Path(ref['path']))
        data = self.data or self.case.data(source, mixed=self.kind == MIXED)
        data = self.transform(deepcopy(data))
        self.case.latest_data = data
        patch = patch_package(self.case.exchange / ('typed-' + str(self.calls) + '.zip'), data)
        self.case.latest_patch = patch
        return {'source_result_sha256': source['sha256'], 'status': self.kind,
                'patch_sha256': patch['sha256'], 'message': 'Isolated typed handoff.'}


class MixedCase(unittest.TestCase):
    installed = True

    def result(self, name, *, base=None, work=None, log=b'', **kwargs):
        kwargs.setdefault('captured_at', '2026-01-01T00:00:00Z')
        if self.installed:
            kwargs.setdefault('development_contract', deepcopy(CAPABILITY))
        fact = AutomationCase.result(self, name, **kwargs)
        base = self.files if base is None else base
        return write_result(fact, base, base if work is None else work, log)

    def setUp(self):
        self.files = {'src/example.py': b'value = 0\n', SPEC: b'Contract 1\n', PLAN: b'Open\n',
                      'tests/test_example.py': b'def test_example():\n    assert True\n'}
        if self.installed:
            self.files[CAPABILITY_PATH] = canonical(CAPABILITY)
        # Protocol tests inject their inputs explicitly. Socket transport,
        # bootstrap and host Paths discovery have independent integration tests.
        temporary = temporary_directory(prefix='src-mixed-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        environment = patch.dict(os.environ, {'HOME': str(self.home),
            'XDG_CONFIG_HOME': str(self.home/'cfg'), 'XDG_STATE_HOME': str(self.home/'state'),
            'XDG_RUNTIME_DIR': str(self.home/'run'), 'PYTHONDONTWRITEBYTECODE': '1'})
        environment.start()
        self.addCleanup(environment.stop)
        self.paths = Paths(self.home/'cfg/specroad-control/config.toml',
            self.home/'state/specroad-control', self.home/'run/specroad-control',
            self.home/'cfg/systemd/user/specroad-control.service')
        self.dev = self.home/'specroad-codex'; self.dev.mkdir(); (self.dev/'.git').mkdir()
        self.exchange = self.home/'exchange'; self.exchange.mkdir()
        self.codex_home = self.home/'codex-home'; self.codex_home.mkdir(mode=0o700)
        self.repo_id, self.thread = str(uuid4()), str(uuid4())
        self.binding = {'repo_id': self.repo_id, 'base_commit': 'a'*40, 'state_fingerprint': 'b'*16,
                        'fingerprint_algorithm': 'patchharbor-state-v1'}
        self.seed = self.result('seed.zip')
        self.config = Config(self.dev, self.exchange, self.thread, True, self.repo_id,
            self.home/'unused-core', self.home/'unused-codex', self.codex_home, settle_seconds=.05)
        private_dir(self.paths.state)
        ledger = Ledger(self.paths.state/'automation.sqlite3', scope(self.config), initial=self.seed)
        ledger.close()
        self.codex = TypedCodex(self)
        self.engine = Engine(self.config, self.paths, Gate(), core=ReconcileCore(), codex=self.codex)
        self.addCleanup(self.engine.close)
        self.number = 0

    def ledger(self):
        value = Ledger(self.paths.state / 'automation.sqlite3', scope(self.config))
        self.addCleanup(value.close)
        return value

    def data(self, source=None, *, mixed=False):
        source = source or self.seed
        files, stages = dict(self.files), []
        if mixed:
            changes = {SPEC: b'Contract 2, accepted rationale\n', PLAN: b'Implementation acceptance specified\n'}
            stages.append(stage('CLARIFY', files, changes) | {'role': 'clarification'})
            files.update(changes)
        for index, suffix in enumerate(('W', 'R', 'C'), 1):
            updates = {'src/example.py': ('value = ' + str(index) + '\n').encode()}
            stages.append(stage('feature.' + suffix, files, updates) | {'role': 'implementation'})
            files.update(updates)
        return {'format_version': 2, 'bundle_number': '555', 'source_result_sha256': source['sha256'],
                'binding': source['binding'], 'apply_repository': source['repository_path'], 'branch': 'dev',
                'initial_dirty': source['dirty'], 'correction_of': None, 'stages': stages,
                'handoff_kind': MIXED if mixed else 'patch_ready'}

    def dispatch(self, mixed=False, data=None):
        self.codex.kind = MIXED if mixed else 'patch_ready'
        self.codex.data = data
        self.engine.gate.set(True)
        return self.engine.tick()

    def outcome(self, *, completed=None, dirty=True, mutate_log=None, mutate_base=None):
        self.number += 1
        row = self.ledger().current()
        source, data = row['source'], self.latest_data
        from specroad_control.apply_snapshot import snapshot
        source_base, source_work = snapshot(source)
        source_base = {n: raw for n, (mode, raw) in source_base.items()}
        source_work = {n: raw for n, (mode, raw) in source_work.items()}
        count = len(data['stages']) if completed is None else completed
        commits = [format(100 * self.number + i, '040x') for i in range(1, count + 1)]
        base = postimage(source_work, data['stages'][:count]) if count else source_base
        failed = count < len(data['stages'])
        work = postimage(source_work, data['stages'][:count + 1]) if failed and dirty else base
        log = log_for(data, commits, failed=failed)
        # Rotation is independent of the number of announced commits.
        lines = log.decode().splitlines(); final = json.loads(lines[-1].split(' ', 1)[1])
        for i, item in enumerate(final['committed']):
            item['gate']['partition_index'] = i % 3
        log = lines[0].encode() + b'\nSPECROAD_APPLY_PROGRESS ' + canonical(final) + b'\n'
        if mutate_log:
            log = mutate_log(log)
        if mutate_base:
            base = mutate_base(dict(base)); work = base
        head = commits[-1] if commits else source['binding']['base_commit']
        self.following = self.result('next-' + str(self.number) + '.zip', previous=source,
            patch_sha=row['patch_sha'], base=base, work=work, log=log,
            binding={**source['binding'], 'base_commit': head,
                     'state_fingerprint': format(self.number, '016x') if work != base else 'b' * 16},
            success=not failed, dirty=work != base, completed_commit=None if failed else head,
            primary_kind='entrypoint_exit' if failed else 'success',
            captured_at='2026-01-01T0' + str(self.number) + ':00:00Z')
        self.engine.gate.set(False)
        return self.following

    def correction(self):
        source = self.ledger().current()['source']
        from specroad_control.mixed_evidence import progress
        from specroad_control.apply_snapshot import snapshot
        previous, failed = progress(source)
        data = deepcopy(self.latest_data)
        data['stages'] = data['stages'][len(failed['committed']):]
        data.update(binding=source['binding'], source_result_sha256=source['sha256'],
                    initial_dirty=source['dirty'], bundle_number='556',
                    correction_of={'plan_sha256': hashed(previous),
                                   'remaining_commit_ids': failed['remaining_commit_ids']},
                    handoff_kind=MIXED if data['stages'][0]['role'] == 'clarification' else 'patch_ready')
        _, files = snapshot(source)
        for value in data['stages']:
            value['before'] = {name: sha256(files[name][1]).hexdigest() for name in value['after'] if name in files}
            files.update({name: ('100644', base64.b64decode(raw)) for name, raw in value['payloads'].items()})
        return data
