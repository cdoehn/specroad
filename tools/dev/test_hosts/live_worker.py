"""Pinned xdist adapter: permission before each attempt, lease through teardown."""
import time

from xdist.remote import WorkerInteractor, Marker, worker_title

from .lease import Lease, LeaseBusy


class LiveWorker(WorkerInteractor):
    def __init__(self, config, channel):
        super().__init__(config, channel)
        self.control = config.workerinput['sr_live_channel']
        self.sequence = 0
        config._sr_live_leases = []

    def permit(self, slot=None):
        self.sequence += 1
        self.control.send(dict(sequence=self.sequence, index=self.nextitem_index, slot=slot))
        reply = self.control.receive(timeout=60)
        if type(reply) is not dict or set(reply) != {'sequence', 'allowed'} or reply['sequence'] != self.sequence or type(reply['allowed']) is not bool:
            raise ValueError('Invalid live worker acknowledgement')
        return reply['allowed']

    def run_one_test(self):
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
                worker_title('[pytest-xdist running] ' + item.nodeid)
                self.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
                ended = time.monotonic_ns()
                self.config._sr_live_leases.append(dict(nodeid=item.nodeid, slot=lease.slot, start=started, end=ended))
            finally:
                lease.close()
            worker_title('[pytest-xdist idle]')
            self.sendevent('runtest_protocol_complete', item_index=self.item_index, duration=(ended-started)/1e9)
            return
        # The controller requeues only this worker's unstarted reservations,
        # and only after a normal workerfinished with no active attempt.
        self.nextitem_index = Marker.SHUTDOWN
