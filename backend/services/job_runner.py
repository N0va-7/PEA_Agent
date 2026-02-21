import queue
import threading
from collections.abc import Callable
import logging


logger = logging.getLogger(__name__)


class JobRunner:
    def __init__(self):
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = None
        self._handler: Callable[[str, bytes], None] | None = None

    def set_handler(self, handler: Callable[[str, bytes], None]):
        self._handler = handler

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._queue.put((None, None))
        if self._thread:
            self._thread.join(timeout=5)

    def submit(self, job_id: str, raw_eml: bytes):
        self._queue.put((job_id, raw_eml))

    def _run(self):
        while not self._stop_event.is_set():
            job_id, raw_eml = self._queue.get()
            if job_id is None:
                continue
            if self._handler is None:
                continue
            try:
                self._handler(job_id, raw_eml)
            except Exception:
                # Keep worker alive even if unexpected errors escape handler.
                logger.exception("Unhandled exception in job runner handler for job_id=%s", job_id)
                continue
