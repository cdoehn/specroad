"""Bound native rejection successors; isolated protocol/file-map evidence only."""
import base64
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from specroad_control.apply_reconcile_proof import canonical, hashed, public_plan
from specroad_control.apply_snapshot import snapshot
from specroad_control.automation import Engine, Gate
from specroad_control.errors import ControlError
from specroad_control.handoff_rebase import CAPABILITY, CAPABILITY_PATH, original, rejection
from specroad_control.job_contract import new_contract
from specroad_control.mixed_contract import MIXED
from specroad_control.mixed_evidence import verify_handoff
from codex_control_tests.apply_reconcile_support import ReconcileCore, patch_package
from codex_control_tests.mixed_support import MixedCase


class CurrentCore(ReconcileCore):
    def __init__(self):
        self.error = None
        self.override = {}

    def call(self, operation, path):
        assert operation == 'current'
        if self.error:
            raise ControlError(self.error, 'Isolated current-state refusal.')
        source = self.result(path)
        return {'kind': 'current', **{k: source[k] for k in
            ('sha256', 'binding', 'repository_path', 'dirty')}, **self.override}


class RebaseCase(MixedCase):
    def result(self, name, *, base=None, work=None, **kwargs):
        if base is None:
            self.files[CAPABILITY_PATH] = canonical(CAPABILITY)
        return super().result(name, base=base, work=work, **kwargs)

    def setUp(self):
        super().setUp()
        self.core = CurrentCore()
        self.engine.core = self.core
        self.engine.exchange.core = self.core

    def refusal(self, *, busy=False, name='refused.zip', previous=None, **changes):
        source = previous or self.ledger().current()['source']
        _, work = snapshot(source)
        files = {name: raw for name, (mode, raw) in work.items()}
        binding = dict(source['binding'])
        if not busy:
            binding['base_commit'] = 'f' * 40 if binding['base_commit'] != 'f' * 40 else 'e' * 40
            files['src/other.py'] = b'preserved = True\n'
        kwargs = {'previous': source, 'patch_sha': self.latest_patch['sha256'],
                  'base': files, 'work': files, 'binding': binding, 'success': False,
                  'primary_kind': 'repository_busy' if busy else 'state_mismatch',
                  'entrypoint_started': False, 'completed_commit': None,
                  'captured_at': '2026-01-02T00:00:00Z'}
        kwargs.update(changes)
        result = self.result(name, **kwargs)
        self.engine.gate.set(False)
        return result

    def rebase(self, result):
        data = deepcopy(self.latest_data)
        previous, progress = original(self.engine, result)
        data.update(binding=result['binding'], source_result_sha256=result['sha256'],
                    initial_dirty=result['dirty'], bundle_number='556',
                    correction_of={'plan_sha256': hashed(previous),
                                   'remaining_commit_ids': progress['remaining_commit_ids']})
        _, files = snapshot(result)
        for stage in data['stages']:
            stage['before'] = {name: sha256(files[name][1]).hexdigest()
                               for name in stage['after'] if name in files}
            files.update({name: ('100644', base64.b64decode(raw))
                          for name, raw in stage['payloads'].items()})
        return data
