"""One canonical outcome, with separate evidence for every authorized attempt."""
from verification_support.outcomes import RunLedger, RANK


class CopyLedger(RunLedger):
    def __init__(self):
        super().__init__()
        self.attempts, self.tokens, self.winners = {}, {}, {}
        self.groups, self.issued = {}, set()
        self.finished = []

    def authorize(self, node, worker, token):
        key = (node, worker)
        if key in self.tokens or token in self.issued:
            raise ValueError('Repeated attempt permission')
        self.tokens[key] = token
        self.attempts[key] = dict(phases={}, worst='not_run', state='running')
        self.groups.setdefault(node, {})[worker] = self.attempts[key]
        self.issued.add(token)

    def observe(self, nodeid, worker, phase, state, *, subtest=False):
        key = (nodeid, worker)
        if key not in self.attempts or phase not in ('setup', 'call', 'teardown') or state not in RANK:
            self.error('unpermitted_copy_report')
            return
        self.workers.add(worker)
        row = self.attempts[key]
        if not subtest:
            if phase in row['phases'] and row['state'] != 'cancelled':
                self.error('duplicate_test_phase')
            row['phases'][phase] = state
        if RANK[state] > RANK[row['worst']]:
            row['worst'] = state
        if state != 'passed':
            self.error('copy_attempt_not_passed')
        if row['state'] == 'cancelled':
            self.cancelled[key]['phases'][phase] = state
        self._project(nodeid)

    def _project(self, node):
        rows = list(self.groups.get(node, {}).values())
        self.worst[node] = max((r['worst'] for r in rows), key=RANK.get, default='not_run')
        if node in self.winners:
            worker = self.winners[node]
            self.phases[node] = dict(self.attempts[node, worker]['phases'])
            self.owners[node] = worker
        elif rows:
            # Progress records only; a running group never supplies pass evidence.
            self.phases[node] = {}

    def completed(self, node, worker, token):
        key = (node, worker)
        if self.tokens.get(key) != token or self.attempts[key]['state'] != 'running':
            raise ValueError('Invalid attempt completion')
        self.attempts[key]['state'] = 'complete'
        self.finished.append(dict(nodeid=node, worker=worker, token=token))
        first = node not in self.winners
        if first:
            self.winners[node] = worker
        self._project(node)
        return first

    def cancel(self, nodeid, worker, token, phases):
        key = (nodeid, worker)
        if self.tokens.get(key) != token or self.attempts[key]['state'] != 'running':
            raise ValueError('Foreign attempt cancellation')
        row = self.attempts[key]
        row['state'] = 'cancelled'
        for phase, state in phases.items():
            if phase in row['phases'] and row['phases'][phase] != state:
                self.error('copy_history_report_mismatch')
            row['phases'][phase] = state
            if RANK[state] > RANK[row['worst']]:
                row['worst'] = state
            if state != 'passed':
                self.error('copy_attempt_not_passed')
        self.cancelled[key] = dict(token=token, phases=dict(row['phases']))
        self._project(nodeid)

    def snapshot(self, exit_code):
        if any(r['state'] == 'running' for r in self.attempts.values()):
            self.error('unresolved_copy_attempt')
        value = super().snapshot(exit_code)
        value['copy_attempts'] = [dict(nodeid=n, worker=w, token=self.tokens[n,w],
                                     phases=dict(row['phases']), state=row['state'], worst=row['worst'])
                                  for (n,w), row in self.attempts.items()]
        value['copy_completions'] = list(self.finished)
        value['copy_winners'] = dict(self.winners)
        return value
