"""Additive request authority and handoff budgets in the existing ledger transaction."""
import sqlite3
from .errors import ControlError
from .job_contract import contract
from .decision_policy import successor_contract
from .mixed_contract import MIXED


class DecisionHistory:
    def request_contract(self):
        try:
            current = self.current()
            has_continuations = self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='clarification_continuations'").fetchone()
            continuations = (self.db.execute('SELECT pending FROM clarification_continuations WHERE sha=?', (current['sha'],)).fetchall() if has_continuations else [])
            has_budgets = self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='clarification_budgets'").fetchone()
            budgets = (self.db.execute('SELECT * FROM clarification_budgets WHERE sha=?', (current['sha'],)).fetchall()
                       if has_budgets else [])
            if len(budgets) > 1:
                raise ValueError
            budget = budgets[0] if budgets else None
            if not self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='request_contracts'").fetchone():
                if budget is not None or continuations:
                    raise ValueError
                return None
            row = self.db.execute('SELECT * FROM request_contracts WHERE sha=?', (current['sha'],)).fetchone()
            if row is None:
                if budget is not None or continuations:
                    raise ValueError
                return None
            if (type(row['allowed']) is not int or row['allowed'] not in (0, 1)
                    or row['output_kind'] not in (None, 'patch_ready', 'spec_clarification', 'patch_ready_with_clarification', 'unknown')
                    or (row['output_kind'] == 'spec_clarification' and not row['allowed'])
                    or (row['output_kind'] is not None and current['patch_sha'] is None)):
                raise ValueError
            selected = {'version': row['version'], 'clarification_allowed': bool(row['allowed'])}
            if row['version'] in (3, 4):
                if budget is None:
                    raise ValueError
                selected.update(clarification_limit=budget['maximum'], clarifications_remaining=budget['remaining'])
            elif budget is not None:
                raise ValueError
            if row['version'] == 4:
                if len(continuations) != 1 or type(continuations[0][0]) is not int or continuations[0][0] not in (0, 1):
                    raise ValueError
                selected['clarification_continuation'] = bool(continuations[0][0])
            elif continuations:
                raise ValueError
            if (row['output_kind'] == MIXED and (row['version'] != 4 or not (selected['clarification_allowed'] or selected['clarification_continuation']))
                    or row['output_kind'] == 'spec_clarification' and row['version'] not in (2, 3)):
                raise ValueError
            return contract(selected)
        except (sqlite3.Error, IndexError, TypeError, ValueError):
            raise ControlError('request_contract_invalid', 'Damaged decision history; preserve it.') from None

    def _insert_contract(self, sha, selected):
        self.db.execute('CREATE TABLE IF NOT EXISTS request_contracts '
                        '(sha TEXT PRIMARY KEY, version INTEGER NOT NULL, allowed INTEGER NOT NULL, output_kind TEXT)')
        self.db.execute('INSERT INTO request_contracts VALUES(?,?,?,NULL)',
                        (sha, selected['version'], int(selected['clarification_allowed'])))
        if selected['version'] in (3, 4):
            self.db.execute('CREATE TABLE IF NOT EXISTS clarification_budgets '
                            '(sha TEXT PRIMARY KEY, maximum INTEGER NOT NULL, remaining INTEGER NOT NULL)')
            self.db.execute('INSERT INTO clarification_budgets VALUES(?,?,?)',
                            (sha, selected['clarification_limit'], selected['clarifications_remaining']))

        if selected['version'] == 4:
            self.db.execute('CREATE TABLE IF NOT EXISTS clarification_continuations (sha TEXT PRIMARY KEY, pending INTEGER NOT NULL)')
            self.db.execute('INSERT INTO clarification_continuations VALUES(?,?)', (sha, int(selected['clarification_continuation'])))

    def bind_contract(self, selected):
        selected = contract(selected)
        with self.transaction():
            previous = self.request_contract()
            if previous is not None and previous != selected:
                raise ControlError('request_contract_changed', 'An existing request cannot gain new decision authority.')
            if previous is None:
                self._insert_contract(self.current()['sha'], selected)
        return selected

    def inherit_contract(self, source, old, *, decision_evidence=None):
        previous = self.request_contract()
        handoff = (self.db.execute('SELECT output_kind FROM request_contracts WHERE sha=?', (old['sha'],)).fetchone()[0]
                   if previous else None)
        return successor_contract(previous, handoff, source, **(decision_evidence or {}))

    def output_kind(self):
        if self.request_contract() is None:
            return None
        return self.db.execute('SELECT output_kind FROM request_contracts WHERE sha=?',
                               (self.current()['sha'],)).fetchone()[0]

    def record_output_contract(self, selected_contract, row, output_kind):
        kind = output_kind or 'unknown'
        if kind not in ('patch_ready', 'spec_clarification', 'patch_ready_with_clarification', 'unknown'):
            raise ControlError('request_contract_invalid', 'Unknown output classification.')
        if kind == MIXED and (selected_contract['version'] != 4 or not (selected_contract['clarification_allowed'] or selected_contract['clarification_continuation'])):
            raise ControlError('clarification_limit', 'No new or proven pending clarification is authorized.')
        if kind == 'spec_clarification' and (selected_contract['version'] not in (2, 3) or not selected_contract['clarification_allowed']):
            raise ControlError('clarification_limit', 'No consecutive clarification handoff is permitted.')
        previous_kind = self.db.execute('SELECT output_kind FROM request_contracts WHERE sha=?', (row['sha'],)).fetchone()[0]
        if previous_kind is not None and output_kind is not None and previous_kind != output_kind:
            raise ControlError('request_contract_changed', 'A recorded handoff cannot be reclassified.')
        self.db.execute('UPDATE request_contracts SET output_kind=COALESCE(output_kind,?) WHERE sha=?', (kind, row['sha']))
