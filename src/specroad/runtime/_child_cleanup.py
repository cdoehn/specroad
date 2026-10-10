"""Internal lifecycle strategy; the trusted adapter supplies its error type."""


def finish_child(process, primary, cleanup_error):
    """Attempt every owned cleanup; defer handled interruption until afterwards."""
    failures, interruption = [], None

    def attempt(operation, action):
        nonlocal interruption
        while True:
            try:
                action()
                return True
            except (KeyboardInterrupt, SystemExit) as error:
                if interruption is None:
                    interruption = error
            except InterruptedError:
                continue
            except BaseException as error:
                failures.append((operation, error))
                return False

    attempt('poll', process.poll)
    stopped = process.returncode is not None
    if not stopped:
        stopped = attempt('kill', process.kill)
    # A failed kill may leave a running child. Do not convert that concrete
    # failure into an unbounded wait or pretend that the process was collected.
    if stopped:
        attempt('wait', process.wait)
    for name in ('stdin', 'stdout', 'stderr'):
        stream = getattr(process, name)
        if stream is not None:
            attempt('close_' + name, stream.close)
    if process.returncode is None:
        attempt('poll', process.poll)
    if failures:
        error = cleanup_error(process, failures, interrupted=interruption is not None)
        raise error from (primary if primary is not None else failures[0][1])
    if interruption is not None and primary is None:
        raise interruption
