from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SystemStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class HealthResponse(BaseModel):
    status: str = "ok"
    system: str = "NewFEM API Server"
    version: str = "3.0.0"


class StatusResponse(BaseModel):
    status: SystemStatus
    frame_count: int
    current_value: float
    peak_signal: Optional[int] = Field(
        None, description="1: HE peak, 0: non-HE peak, null: no peak"
    )
    buffer_size: int
    baseline: float
    timestamp: datetime


class TimeSeriesPoint(BaseModel):
    t: float
    value: float


class RoiData(BaseModel):
    width: int
    height: int
    pixels: str
    gray_value: float
    format: str = "text"


class RealtimeDataResponse(BaseModel):
    type: str = "realtime_data"
    timestamp: datetime
    frame_count: int
    series: List[TimeSeriesPoint]
    roi_data: RoiData
    peak_signal: Optional[int]
    baseline: float


class BaseSuccessResponse(BaseModel):
    type: str
    timestamp: datetime
    success: bool = True
    data: Dict[str, Any]


class ErrorDetails(BaseModel):
    parameter: Optional[str] = None
    value: Optional[Any] = None
    constraint: Optional[str] = None


class ErrorResponse(BaseModel):
    type: str = "error"
    timestamp: datetime
    error_code: str
    error_message: str
    details: Optional[ErrorDetails] = None


class PeakSignalResponse(BaseModel):
    type: str = "peak_signal"
    timestamp: datetime
    signal: Optional[int]
    has_peak: bool
    current_value: float
    frame_count: int


class ControlStatusResponse(BaseModel):
    type: str = "status"
    timestamp: datetime
    server_status: SystemStatus
    connected_clients: int
    last_peak_signal: Optional[int]


class ControlCommandStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class ControlCommandResponse(BaseModel):
    """
    控制类命令（start/stop/pause/resume）的响应结构。
    """

    type: str = "control_response"
    timestamp: datetime
    command: str
    status: ControlCommandStatus
    message: str


class AnalyzeEvent(BaseModel):
    t: float
    type: str
    score: float


class AnalyzeSeriesPoint(BaseModel):
    t: float
    value: float
    ref: float
    std: float
    high: float
    orange: float


class AnalyzeResponse(BaseModel):
    has_hem: bool
    events: List[AnalyzeEvent]
    baseline: float
    series: List[AnalyzeSeriesPoint]
    realtime: bool
    peak_signal: Optional[int]
    frame_count: int
