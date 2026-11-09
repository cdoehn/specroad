"""One pre-opened, thread-owned durable history connection per host pool."""
from concurrent.futures import ThreadPoolExecutor
import threading

from verification_support.runtime_history import RuntimeHistory


class HistoryWriter:
    """Serialize short FULL transactions; never initialize inside a worker RPC."""

    def __init__(self, root):
        self._lock = threading.Lock()
        self._closed = False
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='runtime-history')
        try:
            # The full integrity check completes before workers receive tests.
            self._history = self._executor.submit(RuntimeHistory, root).result()
        except BaseException:
            self._executor.shutdown(wait=True)
            raise

    def _call(self, method, *args, **kwargs):
        with self._lock:
            if self._closed:
                raise ValueError('Host history writer is closed')
            result = self._executor.submit(getattr(self._history, method), *args, **kwargs)
        # A caller may acknowledge only after the native transaction commits.
        return result.result()

    def start(self, *args, **kwargs):
        return self._call('start', *args, **kwargs)

    def observe(self, *args, **kwargs):
        return self._call('observe', *args, **kwargs)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            # Submitted writes drain before close, on the owning thread.
            closed = self._executor.submit(self._history.close)
        try:
            closed.result()
        finally:
            self._executor.shutdown(wait=True)
