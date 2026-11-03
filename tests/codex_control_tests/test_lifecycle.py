import unittest
from specroad_control.errors import ControlError
from specroad_control.lifecycle import Lifecycle

class LifecycleTests(unittest.TestCase):
    def test_pause_resume_idle(self):
        model = Lifecycle()
        self.assertEqual(model.phase, 'idle')
        model.request('pause')
        self.assertEqual(model.phase, 'paused')
        with self.assertRaises(ControlError): model.begin_job()
        model.request('resume')
        model.begin_job()
        self.assertEqual(model.phase, 'working')

    def test_pause_drains_job(self):
        model = Lifecycle()
        model.begin_job(); model.request('pause')
        self.assertTrue(model.active_job)
        self.assertEqual(model.phase, 'pausing')
        model.finish_job()
        self.assertEqual(model.phase, 'paused')

    def test_stop_drains_job(self):
        model = Lifecycle(); model.begin_job(); model.request('stop')
        self.assertTrue(model.active_job)
        self.assertEqual(model.phase, 'stopping')
        with self.assertRaises(ControlError): model.request('resume')
        with self.assertRaises(ControlError): model.begin_job()
        model.finish_job()
        self.assertEqual(model.phase, 'stopped')

    def test_no_second_job_or_unknown_completion(self):
        model = Lifecycle()
        with self.assertRaises(ControlError): model.finish_job()
        model.begin_job()
        with self.assertRaises(ControlError): model.begin_job()

    def test_stops_are_idempotent(self):
        model = Lifecycle('paused')
        model.request('stop'); model.request('stop')
        self.assertEqual(model.phase, 'stopped')
        with self.assertRaises(ControlError): model.request('pause')

    def test_invalid_command_has_no_effect(self):
        model = Lifecycle()
        with self.assertRaises(ControlError): model.request('force-stop')
        self.assertEqual(model.phase, 'idle')
