"""Small isolated native-Core doubles; no real Apply, services or model calls."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import zipfile
import zlib

from specroad_control.apply_reconcile_proof import canonical, hashed, public_plan
from specroad_control.job_contract import new_contract
from specroad_control.local import json_write, private_dir
from codex_control_tests.automation_support import AutomationCase, FakeCore, CORE_SCRIPT, read_package
from codex_control_tests.test_recovery import LedgerContext


def patch_package(path, data, *, extra=''):
    encoded = base64.b64encode(zlib.compress(canonical(data))).decode()
    script = "#!/bin/sh\npython3 - <<'SPECROAD_APPLY_COMMIT_PLAN'\nimport json, zlib, base64\n"
    script += 'DATA = json.loads(zlib.decompress(base64.b64decode(' + repr(encoded) + ')))\n'
    script += extra + '\nSPECROAD_APPLY_COMMIT_PLAN\n'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('patch.json', json.dumps({'marker': 'patch-harbor', 'format_version': 1,
                                                 'entrypoint': 'run.sh', **data['binding']}))
        archive.writestr('PATCHHARBOR_META/CHAT_INSTRUCTIONS.md', 'Isolated test double.')
        archive.writestr('PATCHHARBOR_META/environment.json', '{}')
        archive.writestr('run.sh', script)
    return ReconcileCore().patch(path)


class ReconcileCore(FakeCore):
    def patch(self, path):
        with zipfile.ZipFile(path) as archive:
            metadata = json.loads(archive.read('patch.json'))
        return {'kind': 'patch', 'binding': {k: metadata[k] for k in
                ('repo_id', 'base_commit', 'fingerprint_algorithm', 'state_fingerprint')},
                'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(), 'path': str(path)}


def progress_log(data, head='c' * 40):
    committed = []
    parent = data['binding']['base_commit']
    for index, stage in enumerate(data['stages']):
        commit = head if index == len(data['stages']) - 1 else 'd' * 40
        committed.append({'commit_id': stage['commit_id'], 'parent': parent, 'commit': commit,
                          'gate': {'selection_sha256': 'e' * 64, 'observations_sha256': 'f' * 64,
                                   'tests': 100, 'required_tests': 10, 'partition_index': index}})
        parent = commit
    final = {'format_version': 1, 'kind': 'specroad-apply-progress-v1', 'phase': 'completed',
             'plan_sha256': hashed(public_plan(data)), 'source_result_sha256': data['source_result_sha256'],
             'active_commit_id': None, 'actual_head': head, 'committed': committed,
             'remaining_commit_ids': [], 'error': None}
    return 'SPECROAD_APPLY_PLAN ' + canonical(public_plan(data)).decode() + '\nSPECROAD_APPLY_PROGRESS ' + canonical(final).decode() + '\n'


class ReconcileCase(AutomationCase):
    def result(self, name, **kwargs):
        kwargs.setdefault('captured_at', '2026-01-01T00:00:00Z')
        return super().result(name, **kwargs)

    def setUp(self):
        super().setUp()
        # The isolated Core executable recognizes the same minimal patch container.
        code = CORE_SCRIPT.replace("d=json.loads(z.read('test-facts.json'))",
            "d=json.loads(z.read('test-facts.json')) if 'test-facts.json' in z.namelist() else "
            "{'kind':'patch','binding':{k:json.loads(z.read('patch.json'))[k] for k in "
            "('repo_id','base_commit','state_fingerprint','fingerprint_algorithm')}}")
        self.python.write_text('#!' + __import__('sys').executable + '\n' + code)
        raw = b'print("example")\n'
        digest = hashlib.sha256(raw).hexdigest()
        stages = [{'commit_id': ident, 'message': 'Complete example ' + ident,
                   'before': {'src/example.py': 'f' * 64}, 'after': {'src/example.py': digest},
                   'payloads': {'src/example.py': base64.b64encode(raw).decode()},
                   'source_sha256': 'e' * 64,
                   'test_plan': {'commit_id': ident, 'test_files': ['tests/test_example.py']}}
                  for ident in ('example.R', 'example.C')]
        self.original_data = {'format_version': 1, 'bundle_number': '001',
                              'source_result_sha256': self.seed['sha256'], 'binding': self.seed['binding'],
                              'apply_repository': self.seed['repository_path'], 'branch': 'dev',
                              'initial_dirty': True, 'stages': stages, 'correction_of': None}
        self.original = patch_package(self.exchange / 'original.zip', self.original_data)
        self.checkpoint = self.result('checkpoint.zip', dirty=True,
                                     binding={**self.binding, 'state_fingerprint': 'd' * 16},
                                     captured_at='2026-01-01T01:00:00Z')
        self.resumed_data = deepcopy(self.original_data)
        self.resumed_data.update(bundle_number='002', source_result_sha256=self.checkpoint['sha256'],
                                 binding=self.checkpoint['binding'],
                                 correction_of={'plan_sha256': hashed(public_plan(self.original_data)),
                                                'remaining_commit_ids': ['example.R', 'example.C']})
        self.resumed_data['stages'][0]['before'] = deepcopy(self.resumed_data['stages'][0]['after'])
        self.create_output()
        self.directory = self.paths.state / 'jobs' / self.seed['sha256']
        private_dir(self.directory)
        selected = new_contract(2, allowed=False)
        attempt = {'source_sha256': self.seed['sha256'], 'thread_id': self.thread,
                   'number': 0, 'request_contract': selected,
                   'request_source': {k: self.seed[k] for k in ('path', 'sha256', 'binding', 'run_id')}}
        self.answer = {'source_result_sha256': self.seed['sha256'], 'status': 'patch_ready',
                       'patch_sha256': self.original['sha256'], 'message': 'Ready.'}
        json_write(self.directory / 'attempt.json', attempt)
        json_write(self.directory / 'completion.json', self.answer)
        json_write(self.directory / 'protocol-completion.json',
                   {'completed': True, 'thread_id': self.thread, 'transport': 'exec', 'answer': self.answer})
        with LedgerContext(self.paths, self.config) as ledger:
            ledger.bind_contract(selected)
            ledger.change('running')
            ledger.change('waiting_result', patch_sha=self.original['sha256'], output_kind='patch_ready')
        json_write(self.paths.state_file, {'schema': 1, 'desired': 'paused', 'active_job': False,
                                          'phase': 'paused', 'pid': 1, 'run_id': self.thread,
                                          'started_at': 1.0, 'updated_at': 1.0})

    def create_output(self, *, extra='', log=None, **changes):
        self.resumed = patch_package(self.exchange / 'resumed.zip', self.resumed_data, extra=extra)
        self.final = self.result('final.zip', previous=self.checkpoint, patch_sha=self.resumed['sha256'],
                                 **({'completed_commit': 'c' * 40, 'captured_at': '2026-01-01T02:00:00Z'} | changes))
        with zipfile.ZipFile(self.final['path'], 'a') as archive:
            archive.writestr('logs/execution.log', progress_log(self.resumed_data) if log is None else log)
        self.final = read_package(Path(self.final['path']))
