"""Pinned xdist adapter: permission before each attempt, lease through teardown."""
import os
import time

from xdist.remote import WorkerInteractor, Marker, worker_title

from .lease import Lease, LeaseBusy


class LiveWorker(WorkerInteractor):
    def __init__(self, config, channel):
        super().__init__(config, channel)
        self.control = config.workerinput['sr_live_channel']
        self.sequence = 0
        config._sr_live_leases = []
        self.moves = config.workerinput.get('sr_moves', False)
        self.ready = False
        self.token = None

    def checkpoint(self, kind, value):
        self.sequence += 1
        self.control.send(dict(sequence=self.sequence, kind=kind, value=value))
        if self.control.receive(timeout=60) != dict(sequence=self.sequence, acknowledged=True):
            raise ValueError('Attempt checkpoint not acknowledged')

    def permit(self, slot=None):
        self.sequence += 1
        self.control.send(dict(sequence=self.sequence, index=self.nextitem_index, slot=slot))
        reply = self.control.receive(timeout=60)
        if type(reply) is not dict or set(reply) != ({'sequence', 'allowed', 'token'} if self.moves else {'sequence', 'allowed'}) or reply['sequence'] != self.sequence or type(reply['allowed']) is not bool:
            raise ValueError('Invalid live worker acknowledgement')
        if self.moves and slot is not None and reply['allowed']:
            self.token = reply['token']
        return reply['allowed']

    def run_one_test(self):
        if self.moves and not self.ready:
            from .pytest_pool import worker_proof
            state = self.config._specroad_verification
            self.checkpoint('ready', dict(endpoint=os.environ['SPECROAD_ATTEMPT_SOCKET'],
                secret=os.environ['SPECROAD_ATTEMPT_SECRET'], proof=worker_proof(self.config, state.host_resources)))
            self.ready = True
        while self.permit():
            try:
                lease = Lease(self.config.workerinput['sr_pool_worker']['budget'])
            except LeaseBusy:
                time.sleep(0.2)
                continue
            try:
                if not self.permit(lease.slot):
                    break
                # Retain native nextitem/fixture semantics. The controller always
                # sends a successor or shutdown before permitting an attempt.
                self.item_index = self.nextitem_index
                self.nextitem_index = self.torun.get()
                item = self.session.items[self.item_index]
                nextitem = None if self.nextitem_index is Marker.SHUTDOWN else self.session.items[self.nextitem_index]
                started = time.monotonic_ns()
                if self.moves:
                    from .attempt_supervisor import worker_request
                    state = self.config._specroad_verification
                    state.history.start(state.history_run, item.nodeid, state.ledger.aliases[item.nodeid], state.worker_id)
                    self.config._sr_prestarted_attempt = item.nodeid
                    worker_request('arm', token=self.token, index=self.item_index, slot=lease.slot,
                                   nodeid=item.nodeid, start=started)
                    self.checkpoint('started', dict(token=self.token, start=started))
                worker_title('[pytest-xdist running] ' + item.nodeid)
                self.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
                ended = time.monotonic_ns()
                record = dict(nodeid=item.nodeid, slot=lease.slot, start=started, end=ended)
                if self.moves:
                    worker_request('complete', token=self.token, end=ended)
                    self.checkpoint('complete', dict(token=self.token, end=ended))
                    record['token'] = self.token
                self.config._sr_live_leases.append(record)
            finally:
                lease.close()
            worker_title('[pytest-xdist idle]')
            self.sendevent('runtest_protocol_complete', item_index=self.item_index, duration=(ended-started)/1e9)
            if self.moves and self.control.receive(timeout=60) != dict(completed=self.token):
                raise ValueError('Native completion was not acknowledged')
            return
        # The controller requeues only this worker's unstarted reservations,
        # and only after a normal workerfinished with no active attempt.
        self.nextitem_index = Marker.SHUTDOWN
