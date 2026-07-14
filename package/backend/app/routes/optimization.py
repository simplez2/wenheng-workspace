from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Response, File, Form, UploadFile
from sqlalchemy.orm import Session, defer
from sqlalchemy import func, and_, case
from typing import Any, Dict, List, Optional, Tuple
import json
import io
import os
import secrets
import zipfile
from app.database import SessionLocal, get_db
from app.dependencies import UserCardKey
from app.models.models import User, OptimizationSession, OptimizationSegment, ChangeLog
from app.schemas import (
    OptimizationCreate, SessionResponse, SessionDetailResponse,
    BatchExportConfirmation, BatchFileError, BatchStartResponse,
    QueueStatusResponse, ProgressUpdate, ChangeLogResponse, ExportConfirmation
)
from app.services.optimization_service import OptimizationService
from app.services.concurrency import concurrency_manager
from app.services.stream_manager import stream_manager
from app.security import validate_ai_base_url
from app.utils.auth import generate_session_id
from datetime import datetime
import asyncio
from urllib.parse import quote
from pathlib import Path
from app.config import settings
from app.services.export_service import build_docx, build_pdf
from app.services.document_roundtrip import (
    SUPPORTED_SOURCE_FORMATS,
    build_docx_from_source,
    build_pdf_from_source,
    build_text_from_source,
    delete_source_document,
    parse_source_document,
    source_document_path,
)
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/optimization", tags=["optimization"])

VALID_PROCESSING_MODES = {
    "paper_polish",
    "paper_enhance",
    "paper_polish_enhance",
    "emotion_polish",
}


def _count_active_user_tasks(db: Session, user_id: int) -> int:
    return db.query(OptimizationSession).filter(
        OptimizationSession.user_id == user_id,
        OptimizationSession.status == "processing",
    ).count()


def _count_queued_user_tasks(db: Session, user_id: int) -> int:
    return db.query(OptimizationSession).filter(
        OptimizationSession.user_id == user_id,
        OptimizationSession.status == "queued",
    ).count()


def _validate_processing_mode(processing_mode: str) -> str:
    if processing_mode not in VALID_PROCESSING_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的处理模式。支持的模式: {', '.join(sorted(VALID_PROCESSING_MODES))}",
        )
    return processing_mode


def _initial_stage(processing_mode: str) -> str:
    if processing_mode == "emotion_polish":
        return "emotion_polish"
    if processing_mode == "paper_enhance":
        return "enhance"
    return "polish"


def _safe_upload_filename(filename: Optional[str]) -> str:
    normalized = (filename or "document").replace("\\", "/").split("/")[-1]
    normalized = normalized.replace("\x00", "").strip()
    return normalized[:255] or "document"


def _ensure_usage_capacity(user: User, requested: int):
    usage_limit = user.usage_limit if user.usage_limit is not None else settings.DEFAULT_USAGE_LIMIT
    usage_count = user.usage_count or 0
    if usage_limit > 0 and usage_count + requested > usage_limit:
        remaining = max(usage_limit - usage_count, 0)
        raise HTTPException(
            status_code=403,
            detail=f"剩余可用次数为 {remaining}，不足以提交 {requested} 个任务",
        )


def _ensure_queue_capacity(db: Session, user: User, requested: int):
    outstanding = _count_active_user_tasks(db, user.id) + _count_queued_user_tasks(db, user.id)
    queue_limit = max(settings.MAX_QUEUED_TASKS_PER_USER, 1)
    if outstanding + requested > queue_limit:
        raise HTTPException(
            status_code=429,
            detail=f"当前账号最多保留 {queue_limit} 个处理中或排队任务，请等待部分任务完成后再提交",
        )


def get_current_user(card_key: str, db: Session = Depends(get_db)) -> User:
    """获取当前用户"""
    user = db.query(User).filter(
        User.card_key == card_key,
        User.is_active.is_(True)
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="无效的卡密")

    user.last_used = datetime.utcnow()
    db.commit()

    return user


def _create_file_session(
    db: Session,
    user: User,
    prepared: Dict[str, Any],
    processing_mode: str,
    batch_id: Optional[str] = None,
    batch_index: Optional[int] = None,
) -> Tuple[OptimizationSession, str]:
    session = OptimizationSession(
        user_id=user.id,
        session_id=generate_session_id(),
        original_text=prepared["original_text"],
        source_format=prepared["source_format"],
        source_filename=prepared["filename"],
        source_manifest=json.dumps(prepared["manifest"], ensure_ascii=False),
        batch_id=batch_id,
        batch_index=batch_index,
        preserve_format=True,
        processing_mode=processing_mode,
        current_stage=_initial_stage(processing_mode),
        status="queued",
        progress=0.0,
        total_segments=len(prepared["segments"]),
    )
    db.add(session)
    db.flush()
    for index, segment_text in enumerate(prepared["segments"]):
        db.add(OptimizationSegment(
            session_id=session.id,
            segment_index=index,
            stage=session.current_stage,
            original_text=segment_text,
            status="pending",
        ))
    source_path = source_document_path(session.session_id, prepared["source_format"])
    with open(source_path, "wb") as handle:
        handle.write(prepared["content"])
    return session, source_path


async def _prepare_uploaded_file(file: UploadFile) -> Dict[str, Any]:
    filename = _safe_upload_filename(file.filename)
    source_format = Path(filename).suffix.lower().lstrip(".")
    if source_format not in SUPPORTED_SOURCE_FORMATS:
        raise HTTPException(status_code=400, detail="仅支持 .txt、.md、.docx 和 .pdf 文件")

    content = await file.read()
    max_size_mb = settings.MAX_UPLOAD_FILE_SIZE_MB or 25
    if len(content) > max_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件不能超过 {max_size_mb} MB")
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")

    try:
        original_text, manifest, segments = await asyncio.to_thread(
            parse_source_document,
            content,
            source_format,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"无法读取文件: {exc}") from exc
    if not segments:
        raise HTTPException(status_code=400, detail="文件中没有可处理的文字")
    return {
        "filename": filename,
        "source_format": source_format,
        "content": content,
        "original_text": original_text,
        "manifest": manifest,
        "segments": segments,
    }


async def run_optimization(session_id: int):
    """Run one optimization with a task-owned database session."""
    db = SessionLocal()
    try:
        session_obj = db.query(OptimizationSession).filter(
            OptimizationSession.id == session_id
        ).first()
        if not session_obj:
            return
        service = OptimizationService(db, session_obj)
        await service.start_optimization()
    except Exception as exc:
        print(f"[ERROR] Optimization task {session_id} failed: {exc}", flush=True)
    finally:
        db.close()


async def run_batch_optimizations(session_ids: List[int]):
    results = await asyncio.gather(
        *(run_optimization(session_id) for session_id in session_ids),
        return_exceptions=True,
    )
    for session_id, result in zip(session_ids, results):
        if isinstance(result, Exception):
            print(f"[ERROR] Batch task {session_id} failed: {result}", flush=True)


@router.post("/start", response_model=SessionResponse)
async def start_optimization(
    card_key: UserCardKey,
    data: OptimizationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """开始优化任务"""
    user = get_current_user(card_key, db)

    user_configs = [data.polish_config, data.enhance_config, data.emotion_config]
    if any(user_configs) and not settings.ALLOW_USER_AI_CONFIG:
        raise HTTPException(status_code=403, detail="User-provided AI configuration is disabled")
    for config in user_configs:
        if config and config.base_url:
            try:
                validate_ai_base_url(config.base_url)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    usage_count = user.usage_count or 0
    _ensure_usage_capacity(user, 1)
    _ensure_queue_capacity(db, user, 1)
    _validate_processing_mode(data.processing_mode)
    initial_stage = _initial_stage(data.processing_mode)

    session_id = generate_session_id()
    session = OptimizationSession(
        user_id=user.id,
        session_id=session_id,
        original_text=data.original_text,
        processing_mode=data.processing_mode,
        current_stage=initial_stage,
        status="queued",
        progress=0.0,
        polish_model=data.polish_config.model if data.polish_config else None,
        polish_api_key=data.polish_config.api_key if data.polish_config else None,
        polish_base_url=data.polish_config.base_url if data.polish_config else None,
        enhance_model=data.enhance_config.model if data.enhance_config else None,
        enhance_api_key=data.enhance_config.api_key if data.enhance_config else None,
        enhance_base_url=data.enhance_config.base_url if data.enhance_config else None,
        emotion_model=data.emotion_config.model if data.emotion_config else None,
        emotion_api_key=data.emotion_config.api_key if data.emotion_config else None,
        emotion_base_url=data.emotion_config.base_url if data.emotion_config else None
    )

    db.add(session)
    user.usage_count = usage_count + 1
    db.commit()
    db.refresh(session)

    # 添加后台任务
    background_tasks.add_task(run_optimization, session.id)

    return session


@router.post("/start-file", response_model=SessionResponse)
async def start_file_optimization(
    card_key: UserCardKey,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    processing_mode: str = Form("paper_polish_enhance"),
    db: Session = Depends(get_db),
):
    user = get_current_user(card_key, db)
    _validate_processing_mode(processing_mode)
    _ensure_usage_capacity(user, 1)
    _ensure_queue_capacity(db, user, 1)
    prepared = await _prepare_uploaded_file(file)
    source_path = None
    try:
        session, source_path = _create_file_session(db, user, prepared, processing_mode)
        user.usage_count = (user.usage_count or 0) + 1
        db.commit()
        db.refresh(session)
    except Exception:
        db.rollback()
        if source_path and os.path.exists(source_path):
            os.unlink(source_path)
        raise
    background_tasks.add_task(run_optimization, session.id)
    return session


@router.post("/start-files", response_model=BatchStartResponse)
async def start_file_batch(
    card_key: UserCardKey,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    processing_mode: str = Form("paper_polish_enhance"),
    db: Session = Depends(get_db),
):
    user = get_current_user(card_key, db)
    _validate_processing_mode(processing_mode)
    max_files = max(settings.MAX_BATCH_FILES, 1)
    if not files:
        raise HTTPException(status_code=400, detail="请选择至少一个文件")
    if len(files) > max_files:
        raise HTTPException(status_code=413, detail=f"每批最多导入 {max_files} 个文件")
    _ensure_usage_capacity(user, 1)
    _ensure_queue_capacity(db, user, 1)

    total_limit = max(settings.MAX_BATCH_TOTAL_SIZE_MB, 1) * 1024 * 1024
    declared_total = sum(
        upload.size for upload in files
        if isinstance(upload.size, int) and upload.size > 0
        and Path(_safe_upload_filename(upload.filename)).suffix.lower().lstrip(".") in SUPPORTED_SOURCE_FORMATS
    )
    if declared_total > total_limit:
        raise HTTPException(
            status_code=413,
            detail=f"单批文件总大小不能超过 {settings.MAX_BATCH_TOTAL_SIZE_MB} MB",
        )

    prepared_files: List[Dict[str, Any]] = []
    rejected: List[BatchFileError] = []
    total_size = 0
    for upload in files:
        filename = _safe_upload_filename(upload.filename)
        try:
            prepared = await _prepare_uploaded_file(upload)
            total_size += len(prepared["content"])
            if total_size > total_limit:
                raise HTTPException(
                    status_code=413,
                    detail=f"单批文件总大小不能超过 {settings.MAX_BATCH_TOTAL_SIZE_MB} MB",
                )
            prepared_files.append(prepared)
        except HTTPException as exc:
            if exc.status_code == 413 and total_size > total_limit:
                raise
            rejected.append(BatchFileError(filename=filename, detail=str(exc.detail)))

    if not prepared_files:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "没有可提交的文件",
                "files": [item.model_dump() for item in rejected],
            },
        )

    _ensure_usage_capacity(user, len(prepared_files))
    _ensure_queue_capacity(db, user, len(prepared_files))
    batch_id = secrets.token_urlsafe(16)
    sessions: List[OptimizationSession] = []
    source_paths: List[str] = []
    try:
        for batch_index, prepared in enumerate(prepared_files):
            session, source_path = _create_file_session(
                db,
                user,
                prepared,
                processing_mode,
                batch_id=batch_id,
                batch_index=batch_index,
            )
            sessions.append(session)
            source_paths.append(source_path)
        user.usage_count = (user.usage_count or 0) + len(sessions)
        db.commit()
        for session in sessions:
            db.refresh(session)
    except Exception:
        db.rollback()
        for source_path in source_paths:
            if os.path.exists(source_path):
                os.unlink(source_path)
        raise

    background_tasks.add_task(run_batch_optimizations, [session.id for session in sessions])
    task_limit = user.task_concurrency_limit or settings.DEFAULT_TASK_CONCURRENCY_LIMIT
    available_user_slots = max(task_limit - _count_active_user_tasks(db, user.id), 0)
    manager_status = await concurrency_manager.get_status()
    available_global_slots = max(
        manager_status["max_users"] - manager_status["current_users"],
        0,
    )
    immediate_slots = min(len(sessions), available_user_slots, available_global_slots)
    queued_count = len(sessions) - immediate_slots
    return BatchStartResponse(
        batch_id=batch_id,
        accepted=sessions,
        rejected=rejected,
        total_files=len(files),
        processing_limit=task_limit,
        queued_count=queued_count,
    )


@router.get("/status", response_model=QueueStatusResponse)
async def get_queue_status(
    card_key: UserCardKey,
    session_id: str = None,
    db: Session = Depends(get_db)
):
    """获取队列状态"""
    user = get_current_user(card_key, db)

    status = await concurrency_manager.get_status(session_id)
    task_limit = user.task_concurrency_limit or settings.DEFAULT_TASK_CONCURRENCY_LIMIT
    active_tasks = _count_active_user_tasks(db, user.id)
    queued_tasks = _count_queued_user_tasks(db, user.id)
    usage_limit = user.usage_limit if user.usage_limit is not None else settings.DEFAULT_USAGE_LIMIT
    has_usage = usage_limit == 0 or (user.usage_count or 0) < usage_limit
    status.update({
        "user_active_tasks": active_tasks,
        "user_queued_tasks": queued_tasks,
        "user_task_limit": task_limit,
        "can_submit": has_usage and active_tasks + queued_tasks < max(settings.MAX_QUEUED_TASKS_PER_USER, 1),
        "max_upload_file_size_mb": settings.MAX_UPLOAD_FILE_SIZE_MB,
        "max_batch_files": settings.MAX_BATCH_FILES,
        "max_batch_total_size_mb": settings.MAX_BATCH_TOTAL_SIZE_MB,
    })
    return QueueStatusResponse(**status)


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    card_key: UserCardKey,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """列出用户的所有会话（支持分页）"""
    user = get_current_user(card_key, db)

    # 限制最大返回数量为100，避免一次性加载过多数据
    limit = min(limit, 100)

    # 查询会话及其原始文本长度和预览文本
    results = db.query(
        OptimizationSession,
        func.length(OptimizationSession.original_text).label('original_char_count'),
        func.substring(OptimizationSession.original_text, 1, 50).label('preview_text')
    ).options(
        defer(OptimizationSession.original_text),
    ).filter(
        OptimizationSession.user_id == user.id
    ).order_by(OptimizationSession.created_at.desc(), OptimizationSession.id.desc()).limit(limit).offset(offset).all()

    # 构造响应，手动注入 original_char_count 和 preview_text
    sessions = []
    for session, char_count, preview_text in results:
        session.original_char_count = char_count or 0
        session.preview_text = preview_text or ""
        sessions.append(session)

    return sessions


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: str,
    card_key: UserCardKey,
    db: Session = Depends(get_db)
):
    """获取会话详情"""
    user = get_current_user(card_key, db)

    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 获取段落
    segments = db.query(OptimizationSegment).filter(
        OptimizationSegment.session_id == session.id
    ).order_by(OptimizationSegment.segment_index).all()

    return SessionDetailResponse(
        **session.__dict__,
        segments=[seg.__dict__ for seg in segments]
    )


@router.get("/sessions/{session_id}/progress", response_model=ProgressUpdate)
async def get_session_progress(
    session_id: str,
    card_key: UserCardKey,
    db: Session = Depends(get_db)
):
    """获取会话进度"""
    user = get_current_user(card_key, db)

    # 查询完整会话对象，但避免急切加载关联对象
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    return ProgressUpdate(
        session_id=session.session_id,
        status=session.status,
        progress=session.progress,
        current_position=session.current_position,
        total_segments=session.total_segments,
        current_stage=session.current_stage,
        error_message=session.error_message
    )


@router.get("/sessions/{session_id}/stream")
async def stream_session_progress(
    session_id: str,
    request: Request,
    card_key: UserCardKey,  # 简单的鉴权，实际可能需要更严格的检查
    db: Session = Depends(get_db)
):
    """流式获取会话进度和内容"""
    # 验证用户权限
    user = get_current_user(card_key, db)
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    async def event_generator():
        queue = await stream_manager.connect(session_id)
        try:
            while True:
                if await request.is_disconnected():
                    break

                # 从队列获取消息，设置超时以便检查连接状态
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield message
                except asyncio.TimeoutError:
                    # 发送心跳注释以保持连接活跃
                    yield ": keep-alive\n\n"

        finally:
            await stream_manager.disconnect(session_id, queue)

    return EventSourceResponse(event_generator())


@router.get("/sessions/{session_id}/changes", response_model=List[ChangeLogResponse])
async def get_session_changes(
    session_id: str,
    card_key: UserCardKey,
    db: Session = Depends(get_db)
):
    """获取会话的变更对照"""
    user = get_current_user(card_key, db)

    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    latest_log_subquery = db.query(
        ChangeLog.segment_index,
        ChangeLog.stage,
        func.max(ChangeLog.id).label("latest_id")
    ).filter(
        ChangeLog.session_id == session.id
    ).group_by(
        ChangeLog.segment_index,
        ChangeLog.stage
    ).subquery()

    change_logs = db.query(ChangeLog).join(
        latest_log_subquery,
        and_(
            ChangeLog.segment_index == latest_log_subquery.c.segment_index,
            ChangeLog.stage == latest_log_subquery.c.stage,
            ChangeLog.id == latest_log_subquery.c.latest_id
        )
    ).filter(
        ChangeLog.session_id == session.id
    ).order_by(
        ChangeLog.segment_index,
        case((ChangeLog.stage == "polish", 0), else_=1)
    ).all()

    parsed_changes = []
    for change in change_logs:
        detail = None
        if change.changes_detail:
            try:
                detail = json.loads(change.changes_detail)
            except json.JSONDecodeError:
                detail = {"raw": change.changes_detail}

        parsed_changes.append(
            ChangeLogResponse(
                id=change.id,
                segment_index=change.segment_index,
                stage=change.stage,
                before_text=change.before_text,
                after_text=change.after_text,
                changes_detail=detail,
                created_at=change.created_at
            )
        )

    return parsed_changes


def _build_session_export(
    session: OptimizationSession,
    segments: List[OptimizationSegment],
    export_format: str,
) -> Tuple[bytes, str, str]:
    if session.source_format and export_format != session.source_format:
        raise HTTPException(
            status_code=400,
            detail=f"导入文件必须按原格式导出，请选择 .{session.source_format}",
        )

    optimized_segments = [
        segment.enhanced_text or segment.polished_text or segment.original_text
        for segment in segments
    ]
    original_segments = [segment.original_text for segment in segments]
    final_text = "\n\n".join(optimized_segments)
    source_path = source_document_path(session.session_id, export_format)
    preserve_source = bool(
        session.source_format == export_format
        and session.source_manifest
        and os.path.exists(source_path)
    )
    if session.source_format and not preserve_source:
        raise HTTPException(status_code=500, detail="原始文件模板缺失，已阻止重新排版导出")

    if export_format in {"txt", "md"}:
        content = (
            build_text_from_source(
                source_path,
                session.source_manifest,
                optimized_segments,
                original_segments,
            )
            if preserve_source
            else final_text.encode("utf-8-sig")
        )
        media_type = "text/markdown" if export_format == "md" else "text/plain"
    elif export_format == "docx":
        content = (
            build_docx_from_source(
                source_path,
                session.source_manifest,
                optimized_segments,
                original_segments,
            )
            if preserve_source
            else build_docx(final_text)
        )
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif export_format == "pdf":
        content = (
            build_pdf_from_source(
                source_path,
                session.source_manifest,
                optimized_segments,
                original_segments,
            )
            if preserve_source
            else build_pdf(final_text)
        )
        media_type = "application/pdf"
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")

    if session.source_filename:
        base_name = Path(_safe_upload_filename(session.source_filename)).stem.strip(". ")
    else:
        base_name = f"文衡优化结果_{session.session_id[:8]}"
    base_name = base_name or f"文衡优化结果_{session.session_id[:8]}"
    return content, media_type, f"{base_name}_优化.{export_format}"


@router.post("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    card_key: UserCardKey,
    confirmation: ExportConfirmation,
    db: Session = Depends(get_db)
):
    """导出优化结果"""
    if not confirmation.acknowledge_academic_integrity:
        raise HTTPException(
            status_code=400,
            detail="必须确认学术诚信承诺"
        )

    user = get_current_user(card_key, db)

    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.status != "completed":
        raise HTTPException(status_code=400, detail="会话未完成")

    # 获取所有段落
    segments = db.query(OptimizationSegment).filter(
        OptimizationSegment.session_id == session.id
    ).order_by(OptimizationSegment.segment_index).all()

    export_format = confirmation.export_format
    try:
        content, media_type, filename = _build_session_export(session, segments, export_format)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成 {export_format.upper()} 文件失败: {exc}")

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename=wenheng-result.{export_format}; "
                f"filename*=UTF-8''{quote(filename)}"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/batch/export")
async def export_batch(
    confirmation: BatchExportConfirmation,
    card_key: UserCardKey,
    db: Session = Depends(get_db),
):
    if not confirmation.acknowledge_academic_integrity:
        raise HTTPException(status_code=400, detail="必须确认学术诚信承诺")
    user = get_current_user(card_key, db)
    rows = db.query(OptimizationSession).filter(
        OptimizationSession.session_id.in_(confirmation.session_ids),
        OptimizationSession.user_id == user.id,
    ).all()
    by_session_id = {row.session_id: row for row in rows}
    if len(by_session_id) != len(set(confirmation.session_ids)):
        raise HTTPException(status_code=404, detail="部分任务不存在或不属于当前用户")

    archive = io.BytesIO()
    used_names: Dict[str, int] = {}
    batch_ids = set()
    try:
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for session_id in confirmation.session_ids:
                session = by_session_id[session_id]
                if session.status != "completed":
                    raise HTTPException(status_code=400, detail=f"{session.source_filename or session_id} 尚未完成")
                if not session.source_format:
                    raise HTTPException(status_code=400, detail="批量原格式导出仅支持文件导入任务")
                segments = db.query(OptimizationSegment).filter(
                    OptimizationSegment.session_id == session.id
                ).order_by(OptimizationSegment.segment_index).all()
                content, _, filename = _build_session_export(session, segments, session.source_format)
                stem = Path(filename).stem
                suffix = Path(filename).suffix
                occurrence = used_names.get(filename, 0)
                used_names[filename] = occurrence + 1
                archive_name = filename if occurrence == 0 else f"{stem}_{occurrence + 1}{suffix}"
                bundle.writestr(archive_name, content)
                if session.batch_id:
                    batch_ids.add(session.batch_id)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成批量导出文件失败: {exc}") from exc

    archive.seek(0)
    batch_label = next(iter(batch_ids))[:8] if len(batch_ids) == 1 else datetime.utcnow().strftime("%Y%m%d")
    filename = f"文衡批量优化_{batch_label}.zip"
    return Response(
        content=archive.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                "attachment; filename=wenheng-batch.zip; "
                f"filename*=UTF-8''{quote(filename)}"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    card_key: UserCardKey,
    db: Session = Depends(get_db)
):
    """删除会话"""
    user = get_current_user(card_key, db)

    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    delete_source_document(session.session_id, session.source_format)
    db.delete(session)
    db.commit()

    return {"message": "会话已删除"}


@router.post("/sessions/{session_id}/retry")
async def retry_session(
    session_id: str,
    card_key: UserCardKey,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """继续处理失败或已暂停会话中尚未完成的段落"""
    user = get_current_user(card_key, db)

    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.status not in ["failed", "stopped"]:
        raise HTTPException(status_code=400, detail="仅可对失败或已停止的会话执行重试")

    was_stopped = session.status == "stopped"
    _ensure_queue_capacity(db, user, 1)

    # 保留历史状态信息，服务启动后会清理该提示。
    old_error = session.error_message or "未知错误"
    session.status = "queued"
    session.error_message = (
        "[继续处理中] 正在恢复已暂停任务"
        if was_stopped
        else f"[重试中] 上次失败原因: {old_error}"
    )
    db.commit()

    background_tasks.add_task(run_optimization, session.id)

    return {
        "message": "已继续处理未完成段落" if was_stopped else "已重新排队处理未完成段落"
    }


@router.post("/sessions/{session_id}/stop")
async def stop_session(
    session_id: str,
    card_key: UserCardKey,
    db: Session = Depends(get_db)
):
    """停止正在进行中的会话"""
    user = get_current_user(card_key, db)

    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.status not in ["queued", "processing"]:
        raise HTTPException(status_code=400, detail="只能停止排队中或处理中的会话")

    was_queued = session.status == "queued"
    session.status = "stopped"
    session.error_message = "用户手动停止"
    db.commit()
    if was_queued:
        await concurrency_manager.cancel_queued(session.session_id)

    return {"message": "会话已停止"}
