"""Export only checkpoints whose native outbound effect is fully accounted for."""
from contextlib import contextmanager
from ..qualification.errors import require


@contextmanager
def passive_guard(current):
    value = current.as_dict()
    if value['command_class'] == 'transport_operational':
        from .transport import checked
        _, _, evidence = checked(current)
        require(not evidence or value['state'] == 'completed',
                'outbound_pending_export_requires_inspection', exit_code=6)
    yield
