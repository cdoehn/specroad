"""Actual isolated worker: automatic continuation without stopping its service."""
from codex_control_tests import test_retry_worker as worker_cases
from specroad_control.daemon import request


class ContinuationWorkerTests(worker_cases.RetryWorkerTests):
    def setUp(self):
        super().setUp()
        self.settings(overload=True,partial_overload=True)

    def test_worker_keeps_running_across_partial_work_overload(self):
        child,_=self.spawn(); state=self.wait_stage('retry_wait')
        self.assertEqual(state['desired'],'running')
        self.assertEqual(state['automation']['retry_mode'],'continuation')
        self.assertIsNone(child.poll())
        self.assertEqual((self.dev/'partial.txt').read_text(),'preserved local work')
        self.settings(mode='no_work')
        self.wait_stage('no_work')
        self.assertEqual(self.calls(),2)
        self.assertIsNone(child.poll())
        self.assertEqual((self.dev/'partial.txt').read_text(),'preserved local work')
        request(self.paths,'stop');self.assertEqual(child.wait(timeout=5),0)
