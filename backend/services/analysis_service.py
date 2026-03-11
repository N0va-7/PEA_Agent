from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.infra.config import Settings
from backend.models.tables import AnalysisJob, EmailAnalysis
from backend.repositories.analysis_repo import AnalysisRepository
from backend.repositories.job_repo import JobRepository
from backend.workflow.graph import create_email_analysis_workflow


STAGE_LABELS = {
    "queued": "已入队",
    "running": "执行中",
    "fingerprint_email": "邮件指纹计算",
    "check_existing_analysis": "缓存检查",
    "email_parser": "邮件解析",
    "url_extractor": "URL 提取",
    "url_reputation_vt": "VT URL 信誉",
    "url_model_analysis": "URL 模型分析",
    "attachment_sandbox": "附件沙箱",
    "content_review": "正文内容复核",
    "decision_engine": "综合决策",
    "report_renderer": "报告生成",
    "persist_analysis": "结果持久化",
    "cached": "命中缓存",
    "succeeded": "任务成功",
    "failed": "任务失败",
}

WORKFLOW_STAGES = {
    "fingerprint_email",
    "check_existing_analysis",
    "email_parser",
    "url_extractor",
    "url_reputation_vt",
    "url_model_analysis",
    "attachment_sandbox",
    "content_review",
    "decision_engine",
    "report_renderer",
    "persist_analysis",
}


@dataclass
class AnalysisService:
    settings: Settings
    session_factory: Any
    analysis_repo: AnalysisRepository
    job_repo: JobRepository
    report_store: Any

    def __post_init__(self):
        self._graph = create_email_analysis_workflow(
            settings=self.settings,
            analysis_repo=self.analysis_repo,
            session_factory=self.session_factory,
            report_store=self.report_store,
        )

    def _label(self, stage: str | None) -> str:
        return STAGE_LABELS.get(stage or "", stage or "")

    def _event(
        self,
        event_type: str,
        *,
        status: str,
        stage: str | None = None,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "type": event_type,
            "status": status,
            "stage": stage,
            "stage_label": self._label(stage) if stage else "",
            "message": message or "",
            "at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            payload["metadata"] = metadata
        return payload

    def _append_event(self, job_id: str, event: dict[str, Any], *, current_stage: str | None = None):
        with self.session_factory() as db:
            self.job_repo.append_progress_event(db, job_id, event, current_stage=current_stage)

    def submit_job(self, raw_eml: bytes) -> str:
        job_id = str(uuid4())
        queued_event = self._event(
            "job_queued",
            status="queued",
            stage="queued",
            message="任务已入队，等待执行",
        )
        with self.session_factory() as db:
            self.job_repo.create(
                db,
                job_id,
                current_stage="queued",
                progress_events=[queued_event],
            )
        return job_id

    def process_job(self, job_id: str, raw_eml: bytes):
        try:
            with self.session_factory() as db:
                self.job_repo.mark_running(db, job_id)
            self._append_event(
                job_id,
                self._event("job_started", status="running", stage="running", message="任务开始执行"),
                current_stage="running",
            )

            initial_state = {
                "raw_eml_content": raw_eml,
                "message_id": "",
                "email_fingerprint": "",
                "analysis_id": "",
                "is_cached_result": False,
                "report_path": "",
                "created_at": "",
                "parsed_email": {},
                "url_extraction": {},
                "url_reputation": {},
                "url_analysis": {},
                "content_review": {},
                "attachment_analysis": {},
                "decision": {},
                "report": {},
                "execution_trace": [],
            }
            result: dict[str, Any] = dict(initial_state)
            started_nodes: set[str] = set()

            if hasattr(self._graph, "stream"):
                for output in self._graph.stream(initial_state, config={"configurable": {"thread_id": f"job-{job_id}"}}):
                    if not isinstance(output, dict):
                        continue
                    for node_name, node_update in output.items():
                        if node_name.startswith("__"):
                            continue

                        if node_name not in started_nodes:
                            started_nodes.add(node_name)
                            self._append_event(
                                job_id,
                                self._event(
                                    "stage_started",
                                    status="running",
                                    stage=node_name,
                                    message=f"开始执行：{self._label(node_name)}",
                                ),
                                current_stage=node_name,
                            )

                        if isinstance(node_update, dict):
                            result.update(node_update)

                        self._append_event(
                            job_id,
                            self._event(
                                "stage_done",
                                status="running",
                                stage=node_name,
                                message=f"执行完成：{self._label(node_name)}",
                            ),
                            current_stage=node_name,
                        )
            else:
                result = self._graph.invoke(initial_state, config={"configurable": {"thread_id": f"job-{job_id}"}})
                for stage in result.get("execution_trace", []):
                    if stage in STAGE_LABELS:
                        self._append_event(
                            job_id,
                            self._event(
                                "stage_started",
                                status="running",
                                stage=stage,
                                message=f"开始执行：{self._label(stage)}",
                            ),
                            current_stage=stage,
                        )
                        self._append_event(
                            job_id,
                            self._event(
                                "stage_done",
                                status="running",
                                stage=stage,
                                message=f"执行完成：{self._label(stage)}",
                            ),
                            current_stage=stage,
                        )

            analysis_id = result.get("analysis_id")
            status = "cached" if result.get("is_cached_result") else "succeeded"
            final_event_type = "job_cached" if status == "cached" else "job_succeeded"

            with self.session_factory() as db:
                self.job_repo.mark_finished(db, job_id, status=status, analysis_id=analysis_id)
            self._append_event(
                job_id,
                self._event(
                    final_event_type,
                    status=status,
                    stage=status,
                    message=self._label(status),
                    metadata={"analysis_id": analysis_id},
                ),
                current_stage=status,
            )
        except Exception as exc:
            with self.session_factory() as db:
                self.job_repo.mark_finished(db, job_id, status="failed", analysis_id=None, error=str(exc))
            self._append_event(
                job_id,
                self._event(
                    "job_failed",
                    status="failed",
                    stage="failed",
                    message=str(exc),
                ),
                current_stage="failed",
            )

    def get_job(self, job_id: str) -> AnalysisJob | None:
        with self.session_factory() as db:
            return self.job_repo.get_by_id(db, job_id)

    def get_job_progress(self, job_id: str) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if not job:
            return None
        events = list(job.progress_events or [])
        completed_stages = [evt.get("stage") for evt in events if evt.get("type") == "stage_done" and evt.get("stage")]
        unique_completed: list[str] = []
        seen = set()
        for stage in completed_stages:
            if stage not in seen:
                seen.add(stage)
                unique_completed.append(stage)

        stage_path: list[str] = []
        seen_path = set()
        for evt in events:
            stage = evt.get("stage")
            if stage in WORKFLOW_STAGES and stage not in seen_path:
                seen_path.add(stage)
                stage_path.append(stage)

        if job.status == "cached":
            total_stages = 2
        else:
            total_stages = len(stage_path)
            current_stage = job.current_stage or ""
            if current_stage in WORKFLOW_STAGES and current_stage not in seen_path:
                total_stages += 1
            if job.status in {"queued", "running"}:
                total_stages = max(total_stages, 2)
            else:
                total_stages = max(total_stages, len(unique_completed))

        return {
            "current_stage": job.current_stage,
            "current_stage_label": self._label(job.current_stage),
            "completed_stages": unique_completed,
            "completed_stage_labels": [self._label(stage) for stage in unique_completed],
            "progress_events": events,
            "total_stages": total_stages,
        }

    def get_analysis(self, analysis_id: str) -> EmailAnalysis | None:
        with self.session_factory() as db:
            return self.analysis_repo.get_by_id(db, analysis_id)

    def list_analyses(
        self,
        *,
        sender: str | None = None,
        subject: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[EmailAnalysis], int]:
        with self.session_factory() as db:
            return self.analysis_repo.list(
                db,
                sender=sender,
                subject=subject,
                created_from=created_from,
                created_to=created_to,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
                offset=offset,
            )
