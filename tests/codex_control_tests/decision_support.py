"""Shared synthetic handoff fixture; no real model, service or user state."""
from copy import deepcopy
from unittest.mock import patch
from specroad_control.automation import Engine, Gate
from specroad_control.job_contract import scope
from specroad_control.ledger import Ledger
from codex_control_tests.automation_support import AutomationCase, FakeCore, FakeCodex


class ClarificationCodex(FakeCodex):
    def __init__(self, case):
        super().__init__(case)
        self.kind = 'spec_clarification'
        self.schemas = []
        self.prompts = []

    def run(self, prompt, schema, directory, **kwargs):
        self.schemas.append(deepcopy(schema))
        self.prompts.append(prompt)
        answer = super().run(prompt, schema, directory, **kwargs)
        answer['status'] = self.kind
        return answer


class DecisionCase(AutomationCase):
    legacy_contract = True

    def setUp(self):
        super().setUp()
        # Pin the delivered v2 behavior for compatibility coverage. New budget
        # scenarios opt out and exercise the actual default.
        if self.legacy_contract:
            self.enterContext(patch('specroad_control.automation.new_contract',
                return_value={'version': 2, 'clarification_allowed': True}))
        self.codex = ClarificationCodex(self)
        self.engine = Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=self.codex)
        self.addCleanup(self.engine.close)

    def ledger(self):
        ledger = Ledger(self.paths.state/'automation.sqlite3', scope(self.config))
        self.addCleanup(ledger.close)
        return ledger

    def follow(self, name='next.zip', **changes):
        row = self.ledger().current()
        changes.setdefault('completed_commit', changes.get('binding', {}).get('base_commit', 'c'*40))
        return self.result(name, previous=row['source'], patch_sha=row['patch_sha'],
                           **changes)
