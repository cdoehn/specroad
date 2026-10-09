"""Pure candidate phase values, without scheduling or execution authority."""


def phase_name(remaining):
    return remaining[0]['phase'] if remaining else 'finalize'


def frontier(remaining):
    return [remaining[0]['unit_id']] if remaining else []


def next_action(remaining):
    return ({'operation': 'process_declared_unit', 'unit_id': remaining[0]['unit_id']}
            if remaining else {'operation': 'finalize_declared_work'})


def progress(completed, total):
    return {'completed_units': completed, 'total_units': total}
