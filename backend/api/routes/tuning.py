from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy import select, update

from backend.api.deps import get_container, get_current_user, require_auth
from backend.container import AppContainer
from backend.infra.errors import raise_api_error
from backend.models.tables import EmailAnalysis, FusionTuningRun, SystemConfig
from backend.schemas.tuning import (
    FusionActivateResponse,
    FusionPrecheckRequest,
    FusionPrecheckResponse,
    FusionRunItem,
    FusionRunListResponse,
    FusionRunRequest,
    FusionRunResponse,
)
from ml.training.tune_fusion_threshold import compute_metrics, frange, load_labeled_scores


router = APIRouter(prefix="/tuning/fusion", tags=["tuning"], dependencies=[Depends(require_auth)])


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _safe_prob(value) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0.0 or parsed > 1.0:
        return None
    return parsed


def _collect_labeled_scores(
    container: AppContainer,
    payload: FusionPrecheckRequest,
) -> tuple[list[tuple[float, float, int]], int, int, int, int]:
    reviewed_from = _to_utc(payload.reviewed_from)
    reviewed_to = _to_utc(payload.reviewed_to)
    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=max(0, container.settings.tuning_recent_days))

    with container.analysis_service.session_factory() as db:
        stmt = select(EmailAnalysis).where(EmailAnalysis.review_label.in_(["malicious", "benign"]))
        if reviewed_from:
            stmt = stmt.where(EmailAnalysis.reviewed_at >= reviewed_from)
        if reviewed_to:
            stmt = stmt.where(EmailAnalysis.reviewed_at <= reviewed_to)

        rows = list(db.execute(stmt).scalars().all())

    valid: list[tuple[float, float, int]] = []
    skipped = 0
    recent_feedback_rows = 0
    for row in rows:
        reviewed_at = _to_utc(row.reviewed_at)
        if reviewed_at and reviewed_at >= recent_cutoff:
            recent_feedback_rows += 1

        url_prob = _safe_prob((row.url_analysis or {}).get("max_possibility"))
        text_prob = _safe_prob((row.body_analysis or {}).get("phishing_probability"))
        if url_prob is None or text_prob is None:
            skipped += 1
            continue
        if row.review_label == "malicious":
            label = 1
        elif row.review_label == "benign":
            label = 0
        else:
            skipped += 1
            continue
        valid.append((url_prob, text_prob, label))

    positives = sum(1 for _, _, y in valid if y == 1)
    negatives = len(valid) - positives
    return valid, skipped, positives, negatives, recent_feedback_rows


def _build_precheck(
    container: AppContainer,
    payload: FusionPrecheckRequest,
) -> tuple[FusionPrecheckResponse, list[tuple[float, float, int]]]:
    valid_rows, skipped_rows, positives, negatives, recent_rows = _collect_labeled_scores(container, payload)
    blocking: list[str] = []
    if len(valid_rows) < container.settings.tuning_min_total_samples:
        blocking.append(
            f"valid_rows={len(valid_rows)} is below min_total={container.settings.tuning_min_total_samples}"
        )
    if positives < container.settings.tuning_min_class_samples:
        blocking.append(
            f"positive_rows={positives} is below min_class={container.settings.tuning_min_class_samples}"
        )
    if negatives < container.settings.tuning_min_class_samples:
        blocking.append(
            f"negative_rows={negatives} is below min_class={container.settings.tuning_min_class_samples}"
        )
    if recent_rows <= 0:
        blocking.append(f"recent_feedback_rows must be > 0 in last {container.settings.tuning_recent_days} day(s)")

    return (
        FusionPrecheckResponse(
            meets_requirements=not blocking,
            blocking_reasons=blocking,
            valid_rows=len(valid_rows),
            skipped_rows=skipped_rows,
            positive_rows=positives,
            negative_rows=negatives,
            recent_feedback_rows=recent_rows,
            min_total_required=container.settings.tuning_min_total_samples,
            min_class_required=container.settings.tuning_min_class_samples,
            recent_days_required=container.settings.tuning_recent_days,
        ),
        valid_rows,
    )


def _require_admin(current_user: str, container: AppContainer):
    if current_user != container.settings.auth_username:
        raise_api_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="forbidden",
            message="Only admin can run or activate fusion tuning.",
        )


@router.post("/precheck", response_model=FusionPrecheckResponse)
def fusion_precheck(
    payload: FusionPrecheckRequest,
    container: AppContainer = Depends(get_container),
):
    precheck, _ = _build_precheck(container, payload)
    return precheck


@router.post("/run", response_model=FusionRunResponse)
def run_fusion_tuning(
    payload: FusionRunRequest,
    container: AppContainer = Depends(get_container),
    current_user: str = Depends(get_current_user),
):
    _require_admin(current_user, container)
    if not payload.confirm:
        raise_api_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="confirm_required",
            message="Set confirm=true after precheck passes.",
        )
    if payload.th_min > payload.th_max:
        raise_api_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_threshold_range",
            message="th_min must be <= th_max.",
        )

    precheck, rows = _build_precheck(container, payload)
    if not precheck.meets_requirements:
        raise_api_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="precheck_failed",
            message="Fusion tuning precheck failed.",
            details=precheck.model_dump(),
        )

    run_id = str(uuid4())
    now = datetime.now(timezone.utc)
    with container.analysis_service.session_factory() as db:
        running = db.execute(
            select(FusionTuningRun).where(FusionTuningRun.status == "running").limit(1)
        ).scalar_one_or_none()
        if running:
            raise_api_error(
                status_code=status.HTTP_409_CONFLICT,
                code="tuning_already_running",
                message="Another fusion tuning run is currently in progress.",
            )

        run = FusionTuningRun(
            id=run_id,
            status="running",
            triggered_by=current_user,
            triggered_at=now,
            reviewed_from=_to_utc(payload.reviewed_from),
            reviewed_to=_to_utc(payload.reviewed_to),
            fpr_target=payload.fpr_target,
            w_step=payload.w_step,
            th_min=payload.th_min,
            th_max=payload.th_max,
            th_step=payload.th_step,
            row_count=precheck.valid_rows,
            positive_count=precheck.positive_rows,
            negative_count=precheck.negative_rows,
            skipped_count=precheck.skipped_rows,
            recent_feedback_count=precheck.recent_feedback_rows,
            precheck=precheck.model_dump(),
        )
        db.add(run)
        db.commit()

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        artifact_dir = Path(container.settings.model_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        dataset_csv = artifact_dir / f"fusion_dataset_{timestamp}_{run_id[:8]}.csv"
        with dataset_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["url_prob", "text_prob", "label"])
            for up, tp, lb in rows:
                writer.writerow([f"{up:.8f}", f"{tp:.8f}", lb])

        url_probs, text_probs, labels = load_labeled_scores(
            csv_path=dataset_csv,
            url_col="url_prob",
            text_col="text_prob",
            label_col="label",
            positive_labels={"1", "true", "phishing", "malicious", "bad"},
        )
        all_results = []
        for w_url in frange(0.0, 1.0, payload.w_step):
            for th in frange(payload.th_min, payload.th_max, payload.th_step):
                all_results.append(
                    compute_metrics(
                        url_probs=url_probs,
                        text_probs=text_probs,
                        labels=labels,
                        w_url_base=w_url,
                        threshold=th,
                    )
                )

        feasible = [m for m in all_results if m.fpr <= payload.fpr_target]
        if feasible:
            feasible.sort(key=lambda m: (-m.recall, -m.f1, m.fpr))
            best = feasible[0]
            ranking_pool = feasible
            reason = f"Selected from candidates with FPR <= {payload.fpr_target:.4f}"
        else:
            all_results.sort(key=lambda m: (m.fpr, -m.recall, -m.f1))
            best = all_results[0]
            ranking_pool = all_results
            reason = f"No candidate met FPR target ({payload.fpr_target:.4f}); selected minimal FPR candidate."

        top_k = ranking_pool[:5]
        result_json = artifact_dir / f"fusion_tuning_{timestamp}_{run_id[:8]}.json"
        result_payload = {
            "csv": str(dataset_csv),
            "row_count": len(labels),
            "fpr_target": payload.fpr_target,
            "selection_reason": reason,
            "best": asdict(best),
            "top_k": [asdict(item) for item in top_k],
            "run_id": run_id,
            "triggered_by": current_user,
            "triggered_at": now.isoformat(),
        }
        result_json.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        with container.analysis_service.session_factory() as db:
            run = db.get(FusionTuningRun, run_id)
            if not run:
                raise RuntimeError("Tuning run disappeared during update.")
            run.status = "succeeded"
            run.finished_at = datetime.now(timezone.utc)
            run.dataset_csv_path = str(dataset_csv)
            run.result_json_path = str(result_json)
            run.best_params = asdict(best)
            run.top_k = [asdict(item) for item in top_k]
            run.selection_reason = reason
            db.commit()

        return FusionRunResponse(
            run_id=run_id,
            status="succeeded",
            triggered_at=now,
            precheck=precheck,
            result_json_path=str(result_json),
            best_params=asdict(best),
        )
    except Exception as exc:
        with container.analysis_service.session_factory() as db:
            run = db.get(FusionTuningRun, run_id)
            if run:
                run.status = "failed"
                run.finished_at = datetime.now(timezone.utc)
                run.error = str(exc)
                db.commit()
        raise_api_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="tuning_run_failed",
            message="Fusion tuning execution failed.",
            details=str(exc),
        )


@router.get("/runs", response_model=FusionRunListResponse)
def list_fusion_runs(
    container: AppContainer = Depends(get_container),
):
    with container.analysis_service.session_factory() as db:
        stmt = select(FusionTuningRun).order_by(FusionTuningRun.triggered_at.desc())
        rows = list(db.execute(stmt).scalars().all())
    return FusionRunListResponse(
        items=[
            FusionRunItem(
                id=row.id,
                status=row.status,
                triggered_by=row.triggered_by,
                triggered_at=row.triggered_at,
                finished_at=row.finished_at,
                activated_at=row.activated_at,
                is_active=bool(row.is_active),
                row_count=row.row_count,
                positive_count=row.positive_count,
                negative_count=row.negative_count,
                skipped_count=row.skipped_count,
                recent_feedback_count=row.recent_feedback_count,
                result_json_path=row.result_json_path,
                best_params=row.best_params,
                selection_reason=row.selection_reason,
                error=row.error,
            )
            for row in rows
        ]
    )


@router.post("/runs/{run_id}/activate", response_model=FusionActivateResponse)
def activate_fusion_run(
    run_id: str,
    container: AppContainer = Depends(get_container),
    current_user: str = Depends(get_current_user),
):
    _require_admin(current_user, container)
    now = datetime.now(timezone.utc)
    result_json_path: str | None = None

    with container.analysis_service.session_factory() as db:
        run = db.get(FusionTuningRun, run_id)
        if not run:
            raise_api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="tuning_run_not_found",
                message="Fusion tuning run not found.",
            )
        if run.status != "succeeded":
            raise_api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="tuning_run_not_succeeded",
                message="Only succeeded runs can be activated.",
            )

        db.execute(update(FusionTuningRun).values(is_active=False))
        run.is_active = True
        run.activated_at = now

        key = "active_fusion_tuning_run_id"
        cfg = db.get(SystemConfig, key)
        if cfg:
            cfg.value = run_id
            cfg.updated_at = now
        else:
            db.add(SystemConfig(key=key, value=run_id, updated_at=now))
        result_json_path = run.result_json_path
        db.commit()

    # Keep compatibility for manual scripts/debugging that inspect latest file.
    if result_json_path:
        src = Path(result_json_path)
        if src.exists():
            latest = Path(container.settings.model_dir) / "fusion_tuning_latest.json"
            latest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    return FusionActivateResponse(run_id=run_id, active_run_id=run_id, activated_at=now)
