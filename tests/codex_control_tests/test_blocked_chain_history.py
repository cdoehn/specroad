"""Transaction and authority oracles against a complete isolated in-memory ledger."""
from copy import deepcopy
import json
import sqlite3
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from specroad_control.apply_reconcile_history import (complete, history_hash, persist, stable, validate_history)
from specroad_control.apply_reconcile_proof import hashed
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract
from specroad_control.ledger import Ledger


class BlockedHistoryTests(TestCase):
    def setUp(self):
        self.ledger = Ledger.__new__(Ledger); self.ledger.db = sqlite3.connect(':memory:', isolation_level=None)
        self.ledger.db.row_factory = sqlite3.Row; self.addCleanup(self.ledger.close)
        b = {'repo_id': str(uuid4()), 'base_commit': 'a' * 40, 'state_fingerprint': 'b' * 16,
             'fingerprint_algorithm': 'patchharbor-state-v1'}
        source = {'kind': 'result', 'binding': b, 'sha256': 'a' * 64, 'run_id': str(uuid4()),
                  'path': '/isolated/source.zip', 'repository_path': '/isolated/apply', 'operation': 'bundle',
                  'dry_run': False, 'success': True, 'primary_kind': 'success', 'entrypoint_started': False,
                  'patch_sha256': None, 'expected': None, 'completed_commit': None, 'dirty': False,
                  'captured_at': '2026-01-01T00:00:00Z'}
        original = {'kind': 'patch', 'binding': b, 'sha256': 'b' * 64, 'path': '/isolated/original.zip'}
        checkpoint = {**source, 'binding': {**b, 'base_commit': 'd' * 40, 'state_fingerprint': 'd' * 16},
                      'sha256': 'c' * 64, 'run_id': str(uuid4()), 'path': '/isolated/checkpoint.zip',
                      'operation': 'apply', 'expected': b, 'patch_sha256': original['sha256'], 'entrypoint_started': True,
                      'success': False, 'primary_kind': 'entrypoint_exit', 'dirty': True}
        resumed = {**original, 'binding': checkpoint['binding'], 'sha256': 'd' * 64, 'path': '/isolated/resumed.zip'}
        result = {**source, 'binding': {**b, 'base_commit': 'c' * 40}, 'sha256': 'e' * 64, 'run_id': str(uuid4()),
                  'path': '/isolated/result.zip', 'operation': 'apply', 'expected': checkpoint['binding'],
                  'patch_sha256': resumed['sha256'], 'entrypoint_started': True, 'completed_commit': 'c' * 40}
        self.chain = dict(source=source, original=original, checkpoint=checkpoint, resumed=resumed, result=result)
        for key in ('original_plan_sha256', 'resumed_plan_sha256', 'program_sha256', 'completion_sha256',
                    'checkpoint_progress_sha256', 'snapshot_sha256'): self.chain[key] = 'f' * 64
        db = self.ledger.db
        db.execute('CREATE TABLE meta(id INTEGER PRIMARY KEY, version INTEGER, scope TEXT, seed TEXT, current TEXT)')
        db.execute('CREATE TABLE jobs(run_id TEXT PRIMARY KEY, sha TEXT UNIQUE, source TEXT, stage TEXT, patch_sha TEXT, error TEXT, updated REAL)')
        db.execute('INSERT INTO meta VALUES(1,1,?,?,?)', ('0' * 64, source['sha256'], source['run_id']))
        db.execute("INSERT INTO jobs VALUES(?,?,?,'uncertain',NULL,'dev_blocked',1.0)",
                   (source['run_id'], source['sha256'], json.dumps(source)))
        self.ledger.seed_sha = source['sha256']; self.ledger.bind_contract(new_contract(2, allowed=False))
        self.doc = {'version': 2, 'scope': '0' * 64, 'config_sha256': '1' * 64, 'history_sha256': history_hash(self.ledger),
                    'evidence': {key: '2' * 64 for key in ('attempt.json', 'protocol-completion.json', 'completion.json')},
                    'artifacts': self.chain}

    def test_additive_intent_and_atomic_adoption_leave_original_authority_intact(self):
        before = history_hash(self.ledger); persist(self.ledger, self.doc)
        self.assertEqual(history_hash(self.ledger), before)
        complete(self.ledger, self.doc, self.chain)
        self.assertEqual(self.ledger.current()['sha'], self.chain['result']['sha256'])
        self.assertEqual(self.ledger.request_contract(), new_contract(2, allowed=False))
        old = self.ledger.db.execute('SELECT stage,patch_sha,error FROM jobs WHERE sha=?', (self.chain['source']['sha256'],)).fetchone()
        self.assertEqual(tuple(old), ('done', None, 'dev_blocked')); self.assertIsNone(validate_history(self.ledger))

    def test_failure_after_insert_rolls_back_job_contract_and_proof_state(self):
        persist(self.ledger, self.doc); before = history_hash(self.ledger)
        original = self.ledger._insert_contract
        def fail_after_insert(*args):
            original(*args); raise sqlite3.OperationalError('simulated full disk')
        with patch.object(self.ledger, '_insert_contract', fail_after_insert):
            with self.assertRaises(ControlError) as caught: complete(self.ledger, self.doc, self.chain)
        self.assertEqual(caught.exception.code, 'apply_reconciliation_persist_failed')
        self.assertEqual(history_hash(self.ledger), before); self.assertEqual(validate_history(self.ledger), self.doc)

    def test_substituted_adoption_facts_fail_before_any_history_change(self):
        persist(self.ledger, self.doc); before = history_hash(self.ledger)
        changed = deepcopy(self.chain); changed['result']['sha256'] = '3' * 64
        with self.assertRaises(ControlError): complete(self.ledger, self.doc, changed)
        self.assertEqual(history_hash(self.ledger), before); self.assertEqual(validate_history(self.ledger), self.doc)

    def test_unknown_handoff_never_restores_exhausted_budget(self):
        self.ledger.db.execute('UPDATE clarification_budgets SET remaining=0')
        self.doc['history_sha256'] = history_hash(self.ledger); persist(self.ledger, self.doc)
        complete(self.ledger, self.doc, self.chain)
        self.assertEqual(self.ledger.request_contract(), new_contract(0, allowed=False))

    def test_archive_path_change_preserves_the_same_chain(self):
        persist(self.ledger, self.doc); moved = deepcopy(self.chain)
        for name in ('source', 'original', 'checkpoint', 'resumed', 'result'): moved[name]['path'] = '/archive/' + name + '.zip'
        self.assertEqual(stable(moved), stable(self.chain)); complete(self.ledger, self.doc, moved)
        self.assertEqual(self.ledger.current()['source']['path'], '/archive/result.zip')
