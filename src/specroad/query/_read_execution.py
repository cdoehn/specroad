"""Shared completion and cleanup for owned, process-local read producers."""


def complete_work(work, *, call=None):
    """Keep the existing 128-unit drive and close on success or any failure."""
    try:
        if call is None:
            while not work.advance(128):
                pass
        else:
            while not work.advance(128, call=call):
                pass
        return work.result
    finally:
        work.close()
