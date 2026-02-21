import base64
import json
import logging
import queue
import threading
from collections.abc import Callable


logger = logging.getLogger(__name__)


class JobRunner:
    def __init__(self, *, backend: str = "memory", redis_url: str = "", queue_name: str = "pea:jobs"):
        self._backend = (backend or "memory").strip().lower()
        if self._backend not in {"memory", "redis"}:
            raise RuntimeError("JOB_QUEUE_BACKEND must be 'memory' or 'redis'.")
        self._queue = queue.Queue()
        self._queue_name = queue_name or "pea:jobs"
        self._stop_event = threading.Event()
        self._thread = None
        self._handler: Callable[[str, bytes], None] | None = None
        self._redis = None

        if self._backend == "redis":
            if not redis_url:
                raise RuntimeError("REDIS_URL is required when JOB_QUEUE_BACKEND=redis.")
            try:
                import redis  # type: ignore
            except Exception as exc:
                raise RuntimeError(
                    "redis package is required when JOB_QUEUE_BACKEND=redis. "
                    "Install dependency: pip install redis"
                ) from exc
            self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
            self._redis.ping()

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
        if self._backend == "redis" and self._redis is not None:
            try:
                self._redis.lpush(self._queue_name, json.dumps({"_stop": True}, ensure_ascii=False))
            except Exception:
                logger.exception("Failed to push stop sentinel to redis queue.")
        else:
            self._queue.put((None, None))
        if self._thread:
            self._thread.join(timeout=5)

    def submit(self, job_id: str, raw_eml: bytes):
        if self._backend == "redis" and self._redis is not None:
            payload = {
                "job_id": job_id,
                "raw_eml_b64": base64.b64encode(raw_eml).decode("ascii"),
            }
            self._redis.lpush(self._queue_name, json.dumps(payload, ensure_ascii=False))
            return
        self._queue.put((job_id, raw_eml))

    def _run(self):
        if self._backend == "redis" and self._redis is not None:
            self._run_redis()
            return
        self._run_memory()

    def _run_memory(self):
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

    def _run_redis(self):
        while not self._stop_event.is_set():
            try:
                item = self._redis.brpop(self._queue_name, timeout=1) if self._redis else None
            except Exception:
                logger.exception("Failed to read from redis queue.")
                continue

            if not item:
                continue

            _, raw_payload = item
            try:
                payload = json.loads(raw_payload)
            except Exception:
                logger.exception("Invalid redis queue payload. skipped.")
                continue
            if payload.get("_stop"):
                continue

            job_id = payload.get("job_id")
            b64 = payload.get("raw_eml_b64")
            if not job_id or not isinstance(b64, str):
                logger.warning("Missing required queue fields. payload skipped.")
                continue
            try:
                raw_eml = base64.b64decode(b64.encode("ascii"))
            except Exception:
                logger.exception("Invalid base64 payload for job_id=%s", job_id)
                continue

            if self._handler is None:
                continue
            try:
                self._handler(str(job_id), raw_eml)
            except Exception:
                logger.exception("Unhandled exception in redis job runner handler for job_id=%s", job_id)
                continue
