"""Host-sized test processes, bounded concurrency and inherited CPU priority."""
import argparse
import json
import os
import stat
from pathlib import Path
from .cpu_capacity import available_cpus

POLICY = 'verification/test_execution_policy.json'
DEFAULT_WORKER_LIMIT = 10
NICE_MINIMUM = 10
NESTED = 'SPECROAD_NESTED_TEST_RUN'
POLICY_VALUE = {'format_version': 1, 'worker_limit': 10, 'nice_minimum': 10}


def positive_limit(value):
    try:
        number = int(value)
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError('Worker limit must be a positive integer') from error
    if isinstance(value, bool) or str(number) != str(value) or number < 1:
        raise argparse.ArgumentTypeError('Worker limit must be a positive integer')
    return number


def enabled(root):
    path = Path(root) / POLICY
    if not path.exists() and not path.is_symlink():
        return False
    if path.is_symlink() or not path.is_file():
        raise ValueError('Invalid test execution policy file')
    for parent in path.absolute().parents:
        if not stat.S_ISDIR(parent.lstat().st_mode):
            raise ValueError('Linked execution policy parent')
    before = path.stat()
    if before.st_nlink != 1 or before.st_size > 4096:
        raise ValueError('Invalid execution policy file size or links')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate execution policy key')
            result[key] = value
        return result
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size) != (
            after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size):
        raise ValueError('Execution policy changed while reading')
    value = json.loads(raw, object_pairs_hook=unique)
    if value != POLICY_VALUE or any(type(n) is not int for n in value.values()):
        raise ValueError('Unknown test execution policy')
    return True


def select_workers(root, workers=None, *, worker_limit=DEFAULT_WORKER_LIMIT, environment=None):
    if type(worker_limit) is not int or worker_limit < 1:
        raise ValueError('Worker limit must be a positive integer')
    automatic = workers is None or workers in ('auto', 'logical')
    if not automatic and (type(workers) is not int or workers < 1):
        raise ValueError('Workers must be positive or automatic')
    if not enabled(root):
        return (4 if automatic else workers), None
    env = os.environ if environment is None else environment
    nested = env.get(NESTED, '0')
    if nested not in ('0', '1'):
        raise ValueError('Invalid nested-test context')
    cpus = available_cpus()
    count = min(cpus, worker_limit, cpus if automatic else workers, 1 if nested == '1' else cpus)
    resources = dict(format_version=1, available_cpus=cpus, worker_limit=worker_limit,
                     workers=count, nested=nested == '1', nice_minimum=NICE_MINIMUM)
    return count, resources


def validate_resources(value):
    fields = {'format_version', 'available_cpus', 'worker_limit', 'workers', 'nested', 'nice_minimum'}
    if (type(value) is not dict or set(value) != fields
            or any(type(value[k]) is not int for k in fields - {'nested'})
            or value['format_version'] != 1 or value['nice_minimum'] != NICE_MINIMUM
            or type(value['nested']) is not bool
            or min(value['available_cpus'], value['worker_limit'], value['workers']) < 1
            or value['workers'] > min(value['available_cpus'], value['worker_limit'])
            or (value['nested'] and value['workers'] != 1)):
        raise ValueError('Invalid host test resource proof')
    return value


def lower_priority():
    if not all(hasattr(os, name) for name in ('getpriority', 'setpriority', 'PRIO_PROCESS')):
        raise ValueError('This test policy requires POSIX process priorities')
    current = os.getpriority(os.PRIO_PROCESS, 0)
    if current < NICE_MINIMUM:
        os.setpriority(os.PRIO_PROCESS, 0, NICE_MINIMUM)
    actual = os.getpriority(os.PRIO_PROCESS, 0)
    if actual < NICE_MINIMUM:
        raise ValueError('Lower test priority could not be established')
    return actual


def configure_pytest(config, root):
    if config.getoption('collectonly') or not enabled(root):
        return None
    if hasattr(config, 'workerinput'):
        resources = validate_resources(config.workerinput.get('sr_host_resources'))
    else:
        count, resources = select_workers(root, config.getoption('numprocesses', default=None),
            worker_limit=config.getoption('worker_limit'))
        if config.getoption('dist', default='no') != 'worksteal':
            raise ValueError('Host test execution requires worksteal')
        maximum = config.getoption('maxprocesses', default=None)
        if maximum is not None:
            if type(maximum) is not int or maximum < 1:
                raise ValueError('Invalid xdist worker maximum')
            count = min(count, maximum)
            resources['workers'] = count
        config.option.numprocesses = count
        # xdist constructed its process list in pytest_cmdline_main, before
        # pytest_configure. Keep that list in sync for direct -n requests too.
        config.option.tx = ['popen'] * count
    actual = lower_priority()
    os.environ[NESTED] = '1'
    return {**resources, 'nice_actual': actual}


def verify_resources(observation, expected):
    value = observation.get('host_resources')
    if expected is None:
        return
    validate_resources(expected)
    if (type(value) is not dict or set(value) != set(expected) | {'nice_actual'}
            or {k: value[k] for k in expected} != expected
            or type(value['nice_actual']) is not int or not NICE_MINIMUM <= value['nice_actual'] <= 19
            or len(observation.get('workers', ())) != expected['workers']):
        raise ValueError('Test workers or CPU priority differ from the bound resource policy')
