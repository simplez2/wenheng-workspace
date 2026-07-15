import asyncio
import io
import time
import zipfile
from pathlib import Path
from typing import Annotated, List, Literal, Optional
from urllib.parse import quote

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.agent_schemas import (
    AgentBatchResponse,
    AgentCapabilitiesResponse,
    AgentRejectedFile,
    AgentTaskLinks,
    AgentTaskListResponse,
    AgentTaskResponse,
    AgentTaskSource,
    AgentTextTaskCreate,
    ProcessingMode,
    TaskStatus,
)
from app.config import settings
from app.database import get_db
from app.models.models import OptimizationSegment, OptimizationSession
from app.routes import optimization as optimization_routes
from app.schemas import OptimizationCreate
from app.services.concurrency import ai_request_limiter, concurrency_manager
from app.services.document_roundtrip import SUPPORTED_SOURCE_FORMATS


router = APIRouter()
bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="WenhengCardKey",
    description="Use the user card key as a Bearer token.",
)

TERMINAL_STATUSES = {"completed", "failed", "stopped"}
RETRYABLE_STATUSES = {"failed", "stopped"}


async def get_agent_card_key(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Depends(bearer_scheme),
    ] = None,
    x_card_key: Annotated[Optional[str], Header(alias="X-Card-Key")] = None,
) -> str:
    """Prefer standard Bearer auth while retaining an X-Card-Key fallback."""
    value = ""
    if credentials and credentials.scheme.lower() == "bearer":
        value = credentials.credentials
    elif x_card_key:
        value = x_card_key
    value = value.strip()
    if not value:
        raise HTTPException(status_code=401, detail="Missing API key")
    return value


AgentCardKey = Annotated[str, Depends(get_agent_card_key)]


def _owned_session(db: Session, user_id: int, task_id: str) -> OptimizationSession:
    session = (
        db.query(OptimizationSession)
        .filter(
            OptimizationSession.session_id == task_id,
            OptimizationSession.user_id == user_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Task not found")
    return session


def _batch_sessions(
    db: Session, user_id: int, batch_id: str
) -> List[OptimizationSession]:
    sessions = (
        db.query(OptimizationSession)
        .filter(
            OptimizationSession.batch_id == batch_id,
            OptimizationSession.user_id == user_id,
        )
        .order_by(
            OptimizationSession.batch_index.asc(),
            OptimizationSession.id.asc(),
        )
        .all()
    )
    if not sessions:
        raise HTTPException(status_code=404, detail="Batch not found")
    return sessions


def _task_links(task_id: str) -> AgentTaskLinks:
    base = f"/api/v1/agent/tasks/{task_id}"
    return AgentTaskLinks(
        self=base,
        wait=f"{base}/wait",
        result=f"{base}/result",
        cancel=f"{base}/cancel",
        resume=f"{base}/resume",
    )


async def _task_response(session: OptimizationSession) -> AgentTaskResponse:
    queue_position = None
    estimated_wait_seconds = None
    if session.status == "queued":
        queue_status = await concurrency_manager.get_status(session.session_id)
        queue_position = queue_status.get("your_position")
        estimated_wait_seconds = queue_status.get("estimated_wait_time")

    total_segments = session.total_segments or 0
    if session.status == "completed":
        current_segment = total_segments
    elif session.status == "queued" or not total_segments:
        current_segment = 0
    else:
        current_segment = min((session.current_position or 0) + 1, total_segments)

    return AgentTaskResponse(
        task_id=session.session_id,
        batch_id=session.batch_id,
        batch_index=session.batch_index,
        status=session.status,
        terminal=session.status in TERMINAL_STATUSES,
        retryable=session.status in RETRYABLE_STATUSES,
        result_ready=session.status == "completed",
        progress=round(session.progress or 0.0, 2),
        stage=session.current_stage or "polish",
        processing_mode=session.processing_mode or "paper_polish_enhance",
        current_segment=current_segment,
        total_segments=total_segments,
        queue_position=queue_position,
        estimated_wait_seconds=estimated_wait_seconds,
        source=AgentTaskSource(
            filename=session.source_filename,
            format=session.source_format,
            preserve_format=bool(session.preserve_format),
        ),
        error=session.error_message,
        created_at=session.created_at,
        updated_at=session.updated_at,
        completed_at=session.completed_at,
        links=_task_links(session.session_id),
    )


async def _batch_response(
    batch_id: str,
    sessions: List[OptimizationSession],
    rejected: Optional[List[AgentRejectedFile]] = None,
    requested: Optional[int] = None,
) -> AgentBatchResponse:
    tasks = await asyncio.gather(*(_task_response(session) for session in sessions))
    counts = {
        status: sum(1 for task in tasks if task.status == status)
        for status in ("completed", "processing", "queued", "failed", "stopped")
    }
    terminal = all(task.terminal for task in tasks)
    result_ready = bool(tasks) and all(task.result_ready for task in tasks)
    if result_ready:
        status = "completed"
    elif counts["processing"]:
        status = "processing"
    elif counts["queued"]:
        status = "queued"
    elif counts["failed"] and counts["completed"]:
        status = "partial_failed"
    elif counts["failed"]:
        status = "failed"
    elif counts["stopped"]:
        status = "stopped"
    else:
        status = "pending"

    base = f"/api/v1/agent/batches/{batch_id}"
    return AgentBatchResponse(
        batch_id=batch_id,
        status=status,
        terminal=terminal,
        result_ready=result_ready,
        requested=requested if requested is not None else len(tasks),
        accepted=len(tasks),
        total=len(tasks),
        completed=counts["completed"],
        processing=counts["processing"],
        queued=counts["queued"],
        failed=counts["failed"],
        stopped=counts["stopped"],
        rejected=rejected or [],
        tasks=list(tasks),
        links={
            "self": base,
            "wait": f"{base}/wait",
            "result": f"{base}/result",
        },
    )


@router.get(
    "/capabilities",
    response_model=AgentCapabilitiesResponse,
    tags=["system"],
    summary="Describe Agent API capabilities and active limits",
)
async def capabilities(card_key: AgentCardKey, db: Session = Depends(get_db)):
    user = optimization_routes.get_current_user(card_key, db)
    manager_status = await concurrency_manager.get_status()
    return AgentCapabilitiesResponse(
        processing_modes=[
            "paper_polish",
            "paper_enhance",
            "paper_polish_enhance",
            "emotion_polish",
        ],
        input_formats=sorted(SUPPORTED_SOURCE_FORMATS),
        max_upload_file_size_mb=settings.MAX_UPLOAD_FILE_SIZE_MB,
        max_batch_files=settings.MAX_BATCH_FILES,
        max_batch_total_size_mb=settings.MAX_BATCH_TOTAL_SIZE_MB,
        max_concurrent_tasks=manager_status["max_users"],
        max_concurrent_ai_requests=ai_request_limiter.limit,
        user_task_concurrency_limit=(
            user.task_concurrency_limit or settings.DEFAULT_TASK_CONCURRENCY_LIMIT
        ),
        max_outstanding_tasks_per_user=settings.MAX_QUEUED_TASKS_PER_USER,
        endpoints={
            "docs": "/api/v1/agent/docs",
            "openapi": "/api/v1/agent/openapi.json",
            "tasks": "/api/v1/agent/tasks",
            "batches": "/api/v1/agent/batches",
        },
    )


@router.post(
    "/tasks/text",
    response_model=AgentTaskResponse,
    status_code=202,
    tags=["tasks"],
    summary="Create a text optimization task",
)
async def create_text_task(
    data: AgentTextTaskCreate,
    background_tasks: BackgroundTasks,
    card_key: AgentCardKey,
    db: Session = Depends(get_db),
):
    session = await optimization_routes.start_optimization(
        card_key=card_key,
        data=OptimizationCreate(
            original_text=data.text,
            processing_mode=data.processing_mode,
        ),
        background_tasks=background_tasks,
        db=db,
    )
    return await _task_response(session)


@router.post(
    "/tasks/file",
    response_model=AgentTaskResponse,
    status_code=202,
    tags=["tasks"],
    summary="Create a format-preserving file task",
)
async def create_file_task(
    background_tasks: BackgroundTasks,
    card_key: AgentCardKey,
    file: UploadFile = File(...),
    processing_mode: ProcessingMode = Form("paper_polish_enhance"),
    db: Session = Depends(get_db),
):
    session = await optimization_routes.start_file_optimization(
        card_key=card_key,
        background_tasks=background_tasks,
        file=file,
        processing_mode=processing_mode,
        db=db,
    )
    return await _task_response(session)


@router.post(
    "/batches/files",
    response_model=AgentBatchResponse,
    status_code=202,
    tags=["batches"],
    summary="Create a batch of format-preserving file tasks",
)
async def create_file_batch(
    background_tasks: BackgroundTasks,
    card_key: AgentCardKey,
    files: List[UploadFile] = File(...),
    processing_mode: ProcessingMode = Form("paper_polish_enhance"),
    db: Session = Depends(get_db),
):
    result = await optimization_routes.start_file_batch(
        card_key=card_key,
        background_tasks=background_tasks,
        files=files,
        processing_mode=processing_mode,
        db=db,
    )
    sessions = _batch_sessions(
        db, optimization_routes.get_current_user(card_key, db).id, result.batch_id
    )
    rejected = [
        AgentRejectedFile(filename=item.filename, detail=item.detail)
        for item in result.rejected
    ]
    return await _batch_response(
        result.batch_id,
        sessions,
        rejected,
        requested=result.total_files,
    )


@router.get(
    "/tasks",
    response_model=AgentTaskListResponse,
    tags=["tasks"],
    summary="List tasks",
)
async def list_tasks(
    card_key: AgentCardKey,
    status: Optional[TaskStatus] = None,
    batch_id: Optional[str] = Query(None, max_length=64),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    user = optimization_routes.get_current_user(card_key, db)
    query = db.query(OptimizationSession).filter(OptimizationSession.user_id == user.id)
    if status:
        query = query.filter(OptimizationSession.status == status)
    if batch_id:
        query = query.filter(OptimizationSession.batch_id == batch_id)
    sessions = (
        query.order_by(
            OptimizationSession.created_at.desc(),
            OptimizationSession.id.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    tasks = await asyncio.gather(*(_task_response(session) for session in sessions))
    return AgentTaskListResponse(
        tasks=list(tasks),
        limit=limit,
        offset=offset,
        returned=len(tasks),
    )


@router.get(
    "/tasks/{task_id}",
    response_model=AgentTaskResponse,
    tags=["tasks"],
    summary="Get task status",
)
async def get_task(task_id: str, card_key: AgentCardKey, db: Session = Depends(get_db)):
    user = optimization_routes.get_current_user(card_key, db)
    return await _task_response(_owned_session(db, user.id, task_id))


@router.get(
    "/tasks/{task_id}/wait",
    response_model=AgentTaskResponse,
    tags=["tasks"],
    summary="Wait until a task reaches a terminal state or timeout",
)
async def wait_for_task(
    task_id: str,
    card_key: AgentCardKey,
    timeout_seconds: float = Query(60, ge=0, le=300),
    poll_interval: float = Query(1, ge=0.25, le=5),
    db: Session = Depends(get_db),
):
    user = optimization_routes.get_current_user(card_key, db)
    deadline = time.monotonic() + timeout_seconds
    while True:
        db.expire_all()
        session = _owned_session(db, user.id, task_id)
        if session.status in TERMINAL_STATUSES or time.monotonic() >= deadline:
            return await _task_response(session)
        await asyncio.sleep(min(poll_interval, max(deadline - time.monotonic(), 0)))


@router.post(
    "/tasks/{task_id}/cancel",
    response_model=AgentTaskResponse,
    tags=["tasks"],
    summary="Cancel a queued or running task",
)
async def cancel_task(
    task_id: str,
    card_key: AgentCardKey,
    db: Session = Depends(get_db),
):
    await optimization_routes.stop_session(task_id, card_key, db)
    user = optimization_routes.get_current_user(card_key, db)
    return await _task_response(_owned_session(db, user.id, task_id))


@router.post(
    "/tasks/{task_id}/resume",
    response_model=AgentTaskResponse,
    status_code=202,
    tags=["tasks"],
    summary="Resume a stopped task or retry a failed task",
)
async def resume_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    card_key: AgentCardKey,
    db: Session = Depends(get_db),
):
    await optimization_routes.retry_session(task_id, card_key, background_tasks, db)
    user = optimization_routes.get_current_user(card_key, db)
    return await _task_response(_owned_session(db, user.id, task_id))


@router.get(
    "/tasks/{task_id}/result",
    tags=["results"],
    summary="Download a completed task result",
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def download_task_result(
    task_id: str,
    card_key: AgentCardKey,
    acknowledge_academic_integrity: bool = Query(False),
    export_format: Optional[Literal["txt", "md", "docx", "pdf"]] = Query(
        None,
        alias="format",
    ),
    db: Session = Depends(get_db),
):
    if not acknowledge_academic_integrity:
        raise HTTPException(
            status_code=400,
            detail="Set acknowledge_academic_integrity=true before downloading results",
        )
    user = optimization_routes.get_current_user(card_key, db)
    session = _owned_session(db, user.id, task_id)
    if session.status != "completed":
        raise HTTPException(status_code=409, detail="Task is not completed")
    segments = (
        db.query(OptimizationSegment)
        .filter(OptimizationSegment.session_id == session.id)
        .order_by(OptimizationSegment.segment_index)
        .all()
    )
    resolved_format = session.source_format or export_format or "txt"
    content, media_type, filename = optimization_routes._build_session_export(
        session,
        segments,
        resolved_format,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename=wenheng-result.{resolved_format}; "
                f"filename*=UTF-8''{quote(filename)}"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/batches/{batch_id}",
    response_model=AgentBatchResponse,
    tags=["batches"],
    summary="Get batch status",
)
async def get_batch(
    batch_id: str,
    card_key: AgentCardKey,
    db: Session = Depends(get_db),
):
    user = optimization_routes.get_current_user(card_key, db)
    return await _batch_response(batch_id, _batch_sessions(db, user.id, batch_id))


@router.get(
    "/batches/{batch_id}/wait",
    response_model=AgentBatchResponse,
    tags=["batches"],
    summary="Wait until a batch reaches a terminal state or timeout",
)
async def wait_for_batch(
    batch_id: str,
    card_key: AgentCardKey,
    timeout_seconds: float = Query(60, ge=0, le=300),
    poll_interval: float = Query(1, ge=0.25, le=5),
    db: Session = Depends(get_db),
):
    user = optimization_routes.get_current_user(card_key, db)
    deadline = time.monotonic() + timeout_seconds
    while True:
        db.expire_all()
        sessions = _batch_sessions(db, user.id, batch_id)
        response = await _batch_response(batch_id, sessions)
        if response.terminal or time.monotonic() >= deadline:
            return response
        await asyncio.sleep(min(poll_interval, max(deadline - time.monotonic(), 0)))


@router.get(
    "/batches/{batch_id}/result",
    tags=["results"],
    summary="Download a completed batch as a ZIP archive",
    responses={200: {"content": {"application/zip": {}}}},
)
async def download_batch_result(
    batch_id: str,
    card_key: AgentCardKey,
    acknowledge_academic_integrity: bool = Query(False),
    db: Session = Depends(get_db),
):
    if not acknowledge_academic_integrity:
        raise HTTPException(
            status_code=400,
            detail="Set acknowledge_academic_integrity=true before downloading results",
        )
    user = optimization_routes.get_current_user(card_key, db)
    sessions = _batch_sessions(db, user.id, batch_id)
    if any(session.status != "completed" for session in sessions):
        raise HTTPException(status_code=409, detail="Batch is not completed")

    archive = io.BytesIO()
    used_names = {}
    try:
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for session in sessions:
                if not session.source_format:
                    raise HTTPException(
                        status_code=400,
                        detail="Batch results require file-based tasks",
                    )
                segments = (
                    db.query(OptimizationSegment)
                    .filter(OptimizationSegment.session_id == session.id)
                    .order_by(OptimizationSegment.segment_index)
                    .all()
                )
                content, _, filename = optimization_routes._build_session_export(
                    session,
                    segments,
                    session.source_format,
                )
                occurrence = used_names.get(filename, 0)
                used_names[filename] = occurrence + 1
                if occurrence:
                    path = Path(filename)
                    filename = f"{path.stem}_{occurrence + 1}{path.suffix}"
                bundle.writestr(filename, content)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    archive.seek(0)
    filename = f"wenheng-batch-{batch_id[:8]}.zip"
    return Response(
        content=archive.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
