from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.config import Settings
from app.schemas import (
    JobCreateResponse,
    JobStatusResponse,
    JsonJobCreateRequest,
    RuleDetailResponse,
    RuleListResponse,
    RuleMutationResponse,
    RuleWriteRequest,
)
from app.service import AnalysisService
from app.web import demo_page_response


def create_app(service: AnalysisService | None = None) -> FastAPI:
    sandbox = service or AnalysisService(Settings())

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await sandbox.start()
        try:
            yield
        finally:
            await sandbox.stop()

    app = FastAPI(title="Attachment Analysis Sandbox", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    router = APIRouter()
    app.state.analysis_service = sandbox

    @router.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "rules_version": sandbox.rules.version,
            "queue_backend": sandbox.settings.queue_backend,
            "object_store_backend": sandbox.settings.object_store_backend,
        }

    @router.get("/", include_in_schema=False)
    async def demo_page() -> Response:
        return demo_page_response()

    @router.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    @router.post("/analysis/jobs", response_model=JobCreateResponse, status_code=202)
    async def create_job(
        request: Request,
        file: UploadFile | None = File(default=None),
        filename: str | None = Form(default=None),
        source_id: str | None = Form(default=None),
        declared_mime: str | None = Form(default=None),
        content_sha256: str | None = Form(default=None),
    ) -> JobCreateResponse:
        content_type = request.headers.get("content-type", "")
        try:
            if "application/json" in content_type:
                payload = JsonJobCreateRequest.model_validate(await request.json())
                job = await sandbox.submit_json(**payload.model_dump())
                return JobCreateResponse(job_id=job.job_id)
            if file is None or source_id is None:
                raise HTTPException(status_code=400, detail="multipart requests require file and source_id")
            uploaded_filename = filename or file.filename or "attachment.bin"
            job = await sandbox.submit_inline(
                filename=uploaded_filename,
                source_id=source_id,
                content=await file.read(),
                declared_mime=declared_mime or file.content_type,
                content_sha256=content_sha256,
            )
            return JobCreateResponse(job_id=job.job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/analysis/jobs/{job_id}", response_model=JobStatusResponse)
    async def get_job(job_id: str) -> JobStatusResponse:
        job = await sandbox.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status,
            verdict=job.verdict,
            risk_score=job.risk_score,
            reasons=job.reasons,
            normalized_type=job.normalized_type,
            artifacts=job.artifacts,
            rule_version=job.rule_version,
            sample_sha256=job.sample_sha256,
            source_id=job.source_id,
        )

    @router.get("/internal/quarantine")
    async def quarantine_dump() -> JSONResponse:
        return JSONResponse(await sandbox.get_quarantine())

    @router.get("/rules", response_model=RuleListResponse)
    async def list_rules() -> RuleListResponse:
        return RuleListResponse(
            rules_version=sandbox.analysis_version,
            rules=await sandbox.list_rules(),
        )

    @router.get("/rules/{rule_path:path}", response_model=RuleDetailResponse)
    async def get_rule(rule_path: str) -> RuleDetailResponse:
        try:
            return RuleDetailResponse.model_validate(await sandbox.get_rule(rule_path))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/rules", response_model=RuleMutationResponse, status_code=201)
    async def create_rule(payload: RuleWriteRequest) -> RuleMutationResponse:
        try:
            rule = await sandbox.create_rule(rule_path=payload.path, content=payload.content)
            return RuleMutationResponse(rule=rule, rules_version=sandbox.analysis_version)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"rule compile failed: {exc}") from exc

    @router.put("/rules/{rule_path:path}", response_model=RuleMutationResponse)
    async def update_rule(rule_path: str, payload: RuleWriteRequest) -> RuleMutationResponse:
        if payload.path != rule_path:
            raise HTTPException(status_code=400, detail="payload path must match URL path")
        try:
            rule = await sandbox.update_rule(rule_path=rule_path, content=payload.content)
            return RuleMutationResponse(rule=rule, rules_version=sandbox.analysis_version)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"rule compile failed: {exc}") from exc

    @router.delete("/rules/{rule_path:path}", status_code=204)
    async def delete_rule(rule_path: str) -> Response:
        try:
            await sandbox.delete_rule(rule_path)
            return Response(status_code=204)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"rule compile failed: {exc}") from exc

    app.include_router(router)
    return app
