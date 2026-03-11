from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
from pathlib import Path

from app.config import Settings
from app.db import create_engine, create_session_factory
from app.models import AnalysisResult, AttachmentObject, CachedAnalysis, JobRecord, QuarantineRecord, Verdict
from app.object_store import FileSystemObjectStore
from app.policy import decide
from app.queueing import InMemoryQueue, JobQueue, RedisQueue
from app.rule_admin import RuleAdminService, rule_summary_payload
from app.repository import Repository
from app.rules import RuleService
from app.scanners import ClamAVScanner
from app.static_scan.engine import StaticScanEngine

ANALYSIS_PIPELINE_VERSION = "static-email-v3"


class AnalysisService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.rules = RuleService(self.settings.rules_root, self.settings.compiled_rules_path)
        self.engine = create_engine(self.settings.database_url)
        self.session_factory = create_session_factory(self.engine)
        self.repository = Repository(self.engine, self.session_factory)
        self.object_store = FileSystemObjectStore(Path(self.settings.object_store_root))
        self.queue: JobQueue = build_queue(self.settings)
        self.rule_admin = RuleAdminService(self.settings.rules_root)
        self.scanner = ClamAVScanner(
            enabled=self.settings.clamav_enabled,
            host=self.settings.clamav_host,
            port=self.settings.clamav_port,
            timeout_seconds=self.settings.clamav_timeout_seconds,
        )
        self.static_engine = StaticScanEngine(self.settings, self.rules)
        self._workers: list[asyncio.Task] = []
        self._stop_event = asyncio.Event()
        self._rules_lock = asyncio.Lock()

    @property
    def analysis_version(self) -> str:
        return f"{self.rules.version}:{self.rules.source_digest[:12]}:{ANALYSIS_PIPELINE_VERSION}"

    async def start(self) -> None:
        await self.repository.initialize()
        recoverable_job_ids = await self.repository.recover_incomplete_jobs(self.settings.stale_job_after_seconds)
        for job_id in recoverable_job_ids:
            await self.queue.put(job_id)
        if self.settings.embedded_worker and not self._workers:
            self._stop_event.clear()
            for _ in range(self.settings.worker_count):
                self._workers.append(asyncio.create_task(self._worker_loop()))

    async def stop(self) -> None:
        self._stop_event.set()
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._workers.clear()
        await self.queue.close()
        await self.engine.dispose()

    async def run_worker_forever(self) -> None:
        await self.repository.initialize()
        recoverable_job_ids = await self.repository.recover_incomplete_jobs(self.settings.stale_job_after_seconds)
        for job_id in recoverable_job_ids:
            await self.queue.put(job_id)
        self._stop_event.clear()
        await self._worker_loop()

    async def submit_inline(
        self,
        *,
        filename: str,
        source_id: str,
        content: bytes,
        declared_mime: str | None,
        content_sha256: str | None,
    ) -> JobRecord:
        actual_sha256 = hashlib.sha256(content).hexdigest()
        if content_sha256 and content_sha256.lower() != actual_sha256:
            raise ValueError("content_sha256 does not match uploaded bytes")
        object_ref = await self.object_store.put(actual_sha256, content)
        await self.repository.upsert_sample(
            sha256=actual_sha256,
            object_ref=object_ref,
            filename=filename,
            declared_mime=declared_mime,
            size_bytes=len(content),
        )
        return await self._submit_job(
            filename=filename,
            source_id=source_id,
            declared_mime=declared_mime,
            sample_sha256=actual_sha256,
            object_ref=object_ref,
        )

    async def submit_reference(
        self,
        *,
        filename: str,
        source_id: str,
        object_ref: str,
        declared_mime: str | None,
        content_sha256: str | None,
    ) -> JobRecord:
        sample = await self.repository.get_sample_by_ref(object_ref)
        if sample is None or not await self.object_store.exists(object_ref):
            raise KeyError("object_ref not found")
        if content_sha256 and content_sha256.lower() != sample.sha256:
            raise ValueError("content_sha256 does not match object_ref")
        return await self._submit_job(
            filename=filename,
            source_id=source_id,
            declared_mime=declared_mime,
            sample_sha256=sample.sha256,
            object_ref=object_ref,
        )

    async def submit_json(
        self,
        *,
        filename: str,
        source_id: str,
        declared_mime: str | None,
        content_sha256: str | None,
        object_ref: str | None,
        content_base64: str | None,
    ) -> JobRecord:
        if object_ref:
            return await self.submit_reference(
                filename=filename,
                source_id=source_id,
                object_ref=object_ref,
                declared_mime=declared_mime,
                content_sha256=content_sha256,
            )
        if content_base64 is None:
            raise ValueError("content_base64 is required")
        try:
            content = base64.b64decode(content_base64, validate=True)
        except ValueError as exc:
            raise ValueError("content_base64 is invalid") from exc
        return await self.submit_inline(
            filename=filename,
            source_id=source_id,
            content=content,
            declared_mime=declared_mime,
            content_sha256=content_sha256,
        )

    async def get_job(self, job_id: str) -> JobRecord | None:
        return await self.repository.get_job(job_id)

    async def get_quarantine(self) -> list[dict]:
        return await self.repository.list_quarantine()

    async def list_rules(self) -> list[dict]:
        async with self._rules_lock:
            return [rule_summary_payload(rule) for rule in self.rule_admin.list_rules()]

    async def get_rule(self, rule_path: str) -> dict:
        async with self._rules_lock:
            rule = self.rule_admin.get_rule(rule_path)
            payload = rule_summary_payload(rule)
            payload["content"] = rule.content
            return payload

    async def create_rule(self, *, rule_path: str, content: str) -> dict:
        async with self._rules_lock:
            return await self._mutate_rule(rule_path=rule_path, content=content, create=True)

    async def update_rule(self, *, rule_path: str, content: str) -> dict:
        async with self._rules_lock:
            return await self._mutate_rule(rule_path=rule_path, content=content, create=False)

    async def delete_rule(self, rule_path: str) -> None:
        async with self._rules_lock:
            previous = self.rule_admin.snapshot(rule_path)
            self.rule_admin.delete_rule(rule_path)
            try:
                self.rules.reload()
            except Exception:
                self.rule_admin.rollback_write(rule_path, previous)
                self.rules.reload()
                raise

    async def _mutate_rule(self, *, rule_path: str, content: str, create: bool) -> dict:
        previous = self.rule_admin.snapshot(rule_path)
        rule = self.rule_admin.write_rule(rule_path=rule_path, content=content, create=create)
        try:
            self.rules.reload()
        except Exception:
            self.rule_admin.rollback_write(rule_path, previous)
            self.rules.reload()
            raise
        payload = rule_summary_payload(rule)
        payload["content"] = rule.content
        return payload

    async def _submit_job(
        self,
        *,
        filename: str,
        source_id: str,
        declared_mime: str | None,
        sample_sha256: str,
        object_ref: str,
    ) -> JobRecord:
        cached = await self.repository.get_cached_analysis(sample_sha256, self.analysis_version)
        job = JobRecord(
            sample_sha256=sample_sha256,
            filename=filename,
            declared_mime=declared_mime,
            source_id=source_id,
            object_ref=object_ref,
        )
        await self.repository.create_job(job)
        if cached is not None:
            result = cached_to_result(cached)
            completed = await self.repository.complete_job(job.job_id, result, sample_sha256, source_id)
            if completed and result.verdict in {Verdict.BLOCK, Verdict.QUARANTINE, Verdict.ERROR}:
                await self.repository.put_quarantine_record(
                    QuarantineRecord(job_id=completed.job_id, sample_sha256=sample_sha256, reasons=result.reasons)
                )
            return completed or job
        await self.queue.put(job.job_id)
        return job

    async def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            job_id = await self.queue.get(self.settings.worker_poll_seconds)
            if job_id is None:
                continue
            try:
                await asyncio.wait_for(self._process_job(job_id), timeout=self.settings.analysis_timeout_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self.repository.fail_job(job_id, str(exc), self.analysis_version)
                job = await self.repository.get_job(job_id)
                if job is not None:
                    await self.repository.put_quarantine_record(
                        QuarantineRecord(job_id=job.job_id, sample_sha256=job.sample_sha256, reasons=job.reasons)
                    )

    async def _process_job(self, job_id: str) -> None:
        job = await self.repository.mark_job_running(job_id)
        if job is None:
            return
        content = await self.object_store.get(job.object_ref)
        if content is None:
            raise KeyError("analysis object missing")
        normalized_type, feature_hits, artifacts = self.static_engine.scan(
            content=content,
            filename=job.filename,
            declared_mime=job.declared_mime,
            sample_sha256=job.sample_sha256,
        )
        feature_hits.extend(await self.scanner.scan(content))
        result = decide(
            normalized_type=normalized_type,
            feature_hits=feature_hits,
            artifacts=artifacts,
            rule_version=self.analysis_version,
        )
        await self.repository.upsert_cached_analysis(job.sample_sha256, result)
        completed = await self.repository.complete_job(job.job_id, result, job.sample_sha256, job.source_id)
        if completed and result.verdict in {Verdict.BLOCK, Verdict.QUARANTINE, Verdict.ERROR}:
            await self.repository.put_quarantine_record(
                QuarantineRecord(job_id=completed.job_id, sample_sha256=job.sample_sha256, reasons=result.reasons)
            )


def build_queue(settings: Settings) -> JobQueue:
    if settings.queue_backend == "redis":
        return RedisQueue(settings.redis_url, settings.redis_queue_name)
    return InMemoryQueue()


def cached_to_result(cached: CachedAnalysis) -> AnalysisResult:
    return AnalysisResult(
        verdict=cached.verdict,
        risk_score=cached.risk_score,
        reasons=cached.reasons,
        normalized_type=cached.normalized_type,
        artifacts=cached.artifacts,
        feature_hits=[],
        rule_version=cached.rule_version,
    )
