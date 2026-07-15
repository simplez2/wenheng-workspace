from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


ProcessingMode = Literal[
    "paper_polish",
    "paper_enhance",
    "paper_polish_enhance",
    "emotion_polish",
]

TaskStatus = Literal[
    "queued",
    "processing",
    "completed",
    "failed",
    "stopped",
]


class AgentTextTaskCreate(BaseModel):
    text: str = Field(..., min_length=1, description="Text to optimize")
    processing_mode: ProcessingMode = "paper_polish_enhance"


class AgentTaskSource(BaseModel):
    filename: Optional[str] = None
    format: Optional[str] = None
    preserve_format: bool = False


class AgentTaskLinks(BaseModel):
    self: str
    wait: str
    result: str
    cancel: str
    resume: str


class AgentTaskResponse(BaseModel):
    task_id: str
    batch_id: Optional[str] = None
    batch_index: Optional[int] = None
    status: TaskStatus
    terminal: bool
    retryable: bool
    result_ready: bool
    progress: float
    stage: str
    processing_mode: str
    current_segment: int
    total_segments: int
    queue_position: Optional[int] = None
    estimated_wait_seconds: Optional[int] = None
    source: AgentTaskSource
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    links: AgentTaskLinks


class AgentTaskListResponse(BaseModel):
    tasks: List[AgentTaskResponse]
    limit: int
    offset: int
    returned: int


class AgentRejectedFile(BaseModel):
    filename: str
    detail: str


class AgentBatchResponse(BaseModel):
    batch_id: str
    status: str
    terminal: bool
    result_ready: bool
    requested: int
    accepted: int
    total: int
    completed: int
    processing: int
    queued: int
    failed: int
    stopped: int
    rejected: List[AgentRejectedFile] = Field(default_factory=list)
    tasks: List[AgentTaskResponse]
    links: Dict[str, str]


class AgentCapabilitiesResponse(BaseModel):
    api_version: str = "v1"
    authentication: str = "bearer"
    processing_modes: List[str]
    input_formats: List[str]
    result_acknowledgement_required: bool = True
    max_upload_file_size_mb: int
    max_batch_files: int
    max_batch_total_size_mb: int
    max_concurrent_tasks: int
    max_concurrent_ai_requests: int
    user_task_concurrency_limit: int
    max_outstanding_tasks_per_user: int
    endpoints: Dict[str, str]
