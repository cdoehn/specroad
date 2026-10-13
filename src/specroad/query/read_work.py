"""Process-local read phases; no persisted Work, early result or project write."""
from ..cli.command_errors import CommandUsageError
from ..cli.results import CommandResult
from ..runtime.control_points import PhaseBoundary
from ..runtime.controlled import _invocation


class ReadCommandWork:
    """Retain loaded inputs and a complete computation across explicit calls.

    Loading, native evaluation and final currentness checks are indivisible
    units. A unit may exceed a soft target; no model scope is dropped. This is
    an owned live iterator, not a durable checkpoint or a command returning 8.
    """

    def __init__(self, command, root, **arguments):
        from .show import _show_steps
        from .trace import _trace_steps
        from .why import _why_steps
        from .impact import _impact_steps
        from .project_query import _query_steps
        from .project_diff import _diff_steps
        handlers = {'artifact.show': _show_steps, 'query': _query_steps,
                    'trace': _trace_steps, 'why': _why_steps,
                    'impact': _impact_steps, 'diff': _diff_steps}
        if type(command) is not str or command not in handlers:
            raise CommandUsageError('Unknown read command')
        self._initialize(handlers[command](root, **arguments))

    def _initialize(self, steps):
        self._steps = steps
        self._result = None
        self._units = 0
        self._phase = 'not_started'
        self._closed = self._failed = False

    @property
    def state(self):
        return {'format_version': 'read-command-work-v1', 'phase': self._phase,
                'units_completed': self._units, 'finished': self._result is not None,
                'command_complete': None if self._result is None else self._result.complete,
                'command_exit_code': None if self._result is None else self._result.exit_code,
                'durable_checkpoint': False, 'project_write_authorized': False}

    @property
    def result(self):
        if self._result is None or self._closed:
            raise ValueError('Read work has no available final result')
        return self._result

    def advance(self, units=1, *, call=None):
        if type(units) is not int or units < 1:
            raise ValueError('A positive work-unit count is required')
        if self._closed or self._failed:
            raise ValueError('Read work is no longer active')
        if call is not None:
            _invocation(call)
        try:
            for _ in range(units):
                if self._result is not None:
                    break
                if call is not None:
                    call.control(PhaseBoundary('work_unit', 'start'))
                try:
                    phase = next(self._steps)
                except StopIteration as completed:
                    if type(completed.value) is not CommandResult:
                        raise TypeError('Read producer did not return a command result')
                    self._result = completed.value
                    self._phase = 'finished'
                else:
                    if phase not in ('loaded', 'evaluated'):
                        raise TypeError('Unknown read producer boundary')
                    self._phase = phase
                self._units += 1
                if call is not None and call.control(PhaseBoundary('work_unit', 'end'))['soft_budget_exceeded']:
                    break
            return self._result is not None
        except BaseException:
            self._failed = True
            self._phase = 'failed'
            self._result = None
            self._steps.close()
            raise

    def close(self):
        if not self._closed:
            self._closed = True
            if self._result is None and not self._failed:
                self._phase = 'cancelled'
            self._steps.close()

    def __enter__(self):
        if self._closed:
            raise ValueError('Read work is closed')
        return self

    def __exit__(self, *unused):
        self.close()


def complete_read_steps(steps, *, call=None):
    """Run the same retained phases to completion for synchronous entry points."""
    work = object.__new__(ReadCommandWork)
    work._initialize(steps)
    try:
        while not work.advance(128, call=call):
            pass
        return work.result
    finally:
        work.close()
