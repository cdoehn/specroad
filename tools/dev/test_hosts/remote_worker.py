"""Reviewed xdist 3.8 bootstrap: remote paths never inherit coordinator paths."""

if __name__ == '__channelexec__':
    import os
    from pathlib import Path
    import sys

    workerinput, original_args, options, original_path = channel.receive()
    profile = workerinput['sr_pool_worker']
    root = Path(profile['root'])
    os.chdir(root)
    sys.dont_write_bytecode = True
    # Preserve only interpreter-owned paths. All project paths come from this
    # exact snapshot; no editable coordinator checkout can leak into a worker.
    sys.path[:] = [str(root / p) for p in ('tools', 'tests', 'src')] + [p for p in sys.path if p and not p.startswith(str(root))]
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    for name, value in (('PYTEST_XDIST_TESTRUNUID', workerinput['testrunuid']),
                        ('PYTEST_XDIST_WORKER', workerinput['workerid']),
                        ('PYTEST_XDIST_WORKER_COUNT', str(workerinput['workercount']))):
        os.environ[name] = value
    from dev.test_hosts.environment import environment, digest
    from dev.test_hosts.snapshot import inventory, fingerprint
    from verification_support.identity import source_identity
    if (digest(environment()) != profile['environment_sha256']
            or fingerprint(inventory(root)) != profile['snapshot_sha256']
            or source_identity(root) != profile['source_sha256']):
        raise ValueError('Worker environment or snapshot differs before collection')
    from xdist.remote import _prepareconfig, setup_config, WorkerInteractor
    args = ['-o', 'addopts=', '--disable-plugin-autoload', '-p', 'no:cacheprovider',
            '-p', 'no:doctest', '-p', 'xdist.plugin', '--sr-expected-tests', str(len(profile['selected'])),
            *profile['selected']]
    config = _prepareconfig(args, None)
    setup_config(config, None)
    config.workerinput = workerinput
    config.workeroutput = {}
    interactor = WorkerInteractor(config, channel)
    config.hook.pytest_cmdline_main(config=config)
