"""Order an already fixed selection for xdist's initial worksteal queues."""

UNKNOWN_DURATION_NS = 300_000_000_000


def worker_order(indices, tests, workers):
    """Balance equal-count initial worksteal queues, longest tests first per queue.

    xdist owns execution and subsequent stealing. Its initial queues divide the
    collection by remaining test count / remaining workers. Matching these sizes
    avoids putting every long test into the first contiguous initial queue.
    """
    if type(workers) is not int or workers < 1:
        raise ValueError('Worker count must be positive')
    remaining = len(indices)
    capacities = []
    for left in range(workers, 0, -1):
        capacity = remaining // left
        capacities.append(capacity)
        remaining -= capacity
    lanes = [[] for _ in capacities]
    loads = [0] * workers
    for index in sorted(indices, key=lambda i: (-tests[i]['estimate_ns'], tests[i]['nodeid'])):
        lane = min((i for i in range(workers) if len(lanes[i]) < capacities[i]),
                   key=lambda i: (loads[i], i))
        lanes[lane].append(index)
        loads[lane] += tests[index]['estimate_ns']
    return [i for lane in lanes for i in lane], max(loads)


def latest_runtime_order(selected, snapshot, workers):
    """Use the frozen latest measurements as hints, never to select/drop tests.

    Invalid/incomplete latest attempts already have duration None. Like CI's
    default, unknown tests get a five-minute scheduling estimate; this is not
    a measurement and is never written to history or used by the Apply filter.
    Inputs were validated by filter_latest before the required-test union.
    """
    durations = {row['test_id']: row['duration_ns'] for row in snapshot['tests']}
    tests = []
    for node, identity in selected.items():
        duration = durations[identity]
        tests.append({'nodeid': node, 'estimate_ns':
                      UNKNOWN_DURATION_NS if duration is None else max(1, duration)})
    order, _ = worker_order(range(len(tests)), tests, workers)
    return [tests[index]['nodeid'] for index in order]
