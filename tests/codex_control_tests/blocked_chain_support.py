"""Small synthetic partial Apply and changed correction; never real user state."""
import base64
from copy import deepcopy
import difflib
from hashlib import sha1, sha256
import json
from pathlib import Path
import sys
import zipfile

from specroad_control.apply_reconcile_proof import canonical, hashed, public_plan
from specroad_control.job_contract import new_contract
from specroad_control.local import json_write, private_dir
from codex_control_tests.automation_support import AutomationCase, CORE_SCRIPT, read_package
from codex_control_tests.apply_reconcile_support import patch_package, ReconcileCore
from codex_control_tests.test_recovery import LedgerContext


def git_blob(raw):
    return sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def diff_files(before, after):
    chunks = []
    for name in sorted(set(before) & set(after)):
        if before[name] == after[name]:
            continue
        chunks.extend(['diff --git a/' + name + ' b/' + name + '\n',
                       'index ' + git_blob(before[name]) + '..' + git_blob(after[name]) + ' 100644\n'])
        chunks.extend(difflib.unified_diff(before[name].decode().splitlines(True), after[name].decode().splitlines(True),
                                          fromfile='a/' + name, tofile='b/' + name))
    return ''.join(chunks).encode()


def snapshot_members(base, work):
    tracked = [{'path': name, 'git_mode': '100644', 'size': len(raw), 'object_id': git_blob(raw)} for name, raw in sorted(base.items())]
    untracked = [{'path': name, 'mode': '100644', 'size': len(raw), 'sha256': sha256(raw).hexdigest()}
                 for name, raw in sorted(work.items()) if name not in base]
    members = {'base/' + name: raw for name, raw in base.items()}
    members.update({'untracked/' + name: raw for name, raw in work.items() if name not in base})
    members.update({'changes/staged.patch': b'', 'changes/unstaged.patch': diff_files(base, work)})
    return tracked, untracked, members


def stage(ident, before, updates):
    return {'commit_id': ident, 'message': 'Implement ' + ident,
            'before': {name: sha256(before[name]).hexdigest() for name in updates if name in before},
            'after': {name: sha256(raw).hexdigest() for name, raw in updates.items()},
            'payloads': {name: base64.b64encode(raw).decode() for name, raw in updates.items()},
            'source_sha256': 'e' * 64,
            'test_plan': {'format_version': 1, 'commit_id': ident, 'test_ids': [],
                          'test_files': ['tests/test_example.py'], 'reason': 'Exercise preserved and corrected behavior.'}}


def log_for(data, commits, *, failed=False):
    parent, rows = data['binding']['base_commit'], []
    for index, (s, commit) in enumerate(zip(data['stages'], commits)):
        rows.append({'commit_id': s['commit_id'], 'parent': parent, 'commit': commit,
                     'gate': {'tests': 10, 'required_tests': 2, 'partition_index': index,
                              'selection_sha256': 'e' * 64, 'observations_sha256': 'f' * 64}})
        parent = commit
    final = {'kind': 'specroad-apply-progress-v1', 'format_version': 1, 'phase': 'failed' if failed else 'completed',
             'source_result_sha256': data['source_result_sha256'], 'plan_sha256': hashed(public_plan(data)),
             'active_commit_id': data['stages'][len(commits)]['commit_id'] if failed else None,
             'actual_head': parent, 'committed': rows, 'error': 'Test gate failed.' if failed else None,
             'remaining_commit_ids': [s['commit_id'] for s in data['stages'][len(commits):]]}
    return b'SPECROAD_APPLY_PLAN ' + canonical(public_plan(data)) + b'\nSPECROAD_APPLY_PROGRESS ' + canonical(final) + b'\n'


class BlockedChainCase(AutomationCase):
    def result(self, name, *, base=None, work=None, log=b'', **kwargs):
        kwargs.setdefault('captured_at', '2026-01-01T00:00:00Z')
        fact = super().result(name, **kwargs)
        base = self.initial_files if base is None else base
        work = base if work is None else work
        tracked, untracked, members = snapshot_members(base, work)
        with zipfile.ZipFile(fact['path']) as archive:
            data = {name: archive.read(name) for name in archive.namelist()}
        manifest = json.loads(data['manifest.json'])
        manifest.update(base_entries=tracked, untracked_entries=untracked)
        data.update(members); data['manifest.json'] = canonical(manifest); data['logs/execution.log'] = log
        with zipfile.ZipFile(fact['path'], 'w') as archive:
            for name, raw in data.items(): archive.writestr(name, raw)
        return read_package(Path(fact['path']))

    def setUp(self):
        self.initial_files = {'src/example.py': b'value = 0\n', 'spec/example.md': b'Original contract\n',
                              'tests/test_example.py': b'def test_example():\n    assert True\n'}
        super().setUp()
        code = CORE_SCRIPT.replace("d=json.loads(z.read('test-facts.json'))",
            "d=json.loads(z.read('test-facts.json')) if 'test-facts.json' in z.namelist() else "
            "{'kind':'patch','binding':{k:json.loads(z.read('patch.json'))[k] for k in "
            "('repo_id','base_commit','state_fingerprint','fingerprint_algorithm')}}")
        self.python.write_text('#!' + sys.executable + '\n' + code)
        clarification = {'spec/example.md': b'Authorized reference contract\n'}
        self.prefix_files = self.initial_files | clarification
        work = {'src/example.py': b'value = 1\n', 'src/new.py': b'new = 1\n',
                'tests/test_example.py': b'def test_example():\n    assert 1 == 1\n'}
        self.dirty_files = self.prefix_files | work
        right = {'src/example.py': b'value = 2\n'}
        clean = {'src/example.py': b'value = (2)\n'}
        self.original_data = {'format_version': 1, 'bundle_number': '001', 'source_result_sha256': self.seed['sha256'],
                              'binding': self.seed['binding'], 'apply_repository': self.seed['repository_path'],
                              'branch': 'dev', 'initial_dirty': False, 'correction_of': None,
                              'stages': [stage('CLARIFY', self.initial_files, clarification),
                                         stage('example.W', self.prefix_files, work),
                                         stage('example.R', self.dirty_files, right),
                                         stage('example.C', self.dirty_files | right, clean)]}
        self.original = patch_package(self.exchange / 'original.zip', self.original_data)
        self.create_checkpoint()
        corrected = work | {'src/example.py': b'value = 11\n', 'src/new.py': b'new = 11\n'}
        corrected_right = {'src/example.py': b'value = 12\n'}
        corrected_clean = {'src/example.py': b'value = (12)\n'}
        self.resumed_data = {**deepcopy(self.original_data), 'bundle_number': '002', 'initial_dirty': True,
                             'binding': self.checkpoint['binding'], 'source_result_sha256': self.checkpoint['sha256'],
                             'correction_of': {'plan_sha256': hashed(public_plan(self.original_data)),
                                               'remaining_commit_ids': ['example.W', 'example.R', 'example.C']},
                             'stages': [stage('example.W', self.dirty_files, corrected),
                                        stage('example.R', self.dirty_files | corrected, corrected_right),
                                        stage('example.C', self.dirty_files | corrected | corrected_right, corrected_clean)]}
        self.final_files = self.dirty_files | corrected | corrected_right | corrected_clean
        self.create_output()
        self.directory = self.paths.state / 'jobs' / self.seed['sha256']; private_dir(self.directory)
        selected = new_contract(2, allowed=False)
        attempt = {'source_sha256': self.seed['sha256'], 'thread_id': self.thread, 'number': 0,
                   'request_contract': selected,
                   'request_source': {key: self.seed[key] for key in ('path', 'sha256', 'binding', 'run_id')}}
        self.answer = {'source_result_sha256': self.seed['sha256'], 'status': 'blocked', 'patch_sha256': '',
                       'message': 'Reference format needs an explicit decision.'}
        json_write(self.directory / 'attempt.json', attempt)
        json_write(self.directory / 'completion.json', self.answer)
        json_write(self.directory / 'protocol-completion.json',
                   {'completed': True, 'thread_id': self.thread, 'transport': 'exec', 'answer': self.answer})
        with LedgerContext(self.paths, self.config) as ledger:
            ledger.bind_contract(selected); ledger.change('running'); ledger.change('uncertain', error='dev_blocked')
        json_write(self.paths.state_file, {'schema': 1, 'desired': 'paused', 'active_job': False, 'phase': 'paused',
                                          'pid': 1, 'run_id': self.thread, 'started_at': 1.0, 'updated_at': 1.0})

    def create_checkpoint(self, *, log=None, **changes):
        self.checkpoint = self.result('checkpoint.zip', previous=self.seed, patch_sha=self.original['sha256'],
            base=self.prefix_files, work=self.dirty_files,
            log=log_for(self.original_data, ['d' * 40], failed=True) if log is None else log,
            **({'binding': {**self.binding, 'base_commit': 'd' * 40, 'state_fingerprint': 'd' * 16},
                'dirty': True, 'success': False, 'primary_kind': 'entrypoint_exit',
                'captured_at': '2026-01-01T01:00:00Z'} | changes))

    def create_output(self, *, extra='', log=None, **changes):
        self.resumed_data.update(binding=self.checkpoint['binding'], source_result_sha256=self.checkpoint['sha256'])
        self.resumed = patch_package(self.exchange / 'resumed.zip', self.resumed_data, extra=extra)
        self.final = self.result('final.zip', previous=self.checkpoint, patch_sha=self.resumed['sha256'],
            base=self.final_files, log=log_for(self.resumed_data, ['e' * 40, 'f' * 40, 'c' * 40]) if log is None else log,
            **({'binding': {**self.binding, 'base_commit': 'c' * 40}, 'completed_commit': 'c' * 40,
                'captured_at': '2026-01-01T02:00:00Z'} | changes))
