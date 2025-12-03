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
    format: str = "base64"


class RealtimeDataResponse(BaseModel):
    type: str = "realtime_data"
    timestamp: datetime
    frame_count: int
    series: List[TimeSeriesPoint]
    roi_data: RoiData
    peak_signal: Optional[int]
    enhanced_peak: Optional[EnhancedPeakSignal] = None
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


class RoiConfig(BaseModel):
    """ROI配置模型"""
    x1: int = Field(0, ge=0, description="ROI左上角X坐标")
    y1: int = Field(0, ge=0, description="ROI左上角Y坐标")
    x2: int = Field(100, ge=0, description="ROI右下角X坐标")
    y2: int = Field(100, ge=0, description="ROI右下角Y坐标")

    @property
    def center_x(self) -> int:
        """ROI中心X坐标"""
        return (self.x1 + self.x2) // 2

    @property
    def center_y(self) -> int:
        """ROI中心Y坐标"""
        return (self.y1 + self.y2) // 2

    @property
    def width(self) -> int:
        """ROI宽度"""
        return abs(self.x2 - self.x1)

    @property
    def height(self) -> int:
        """ROI高度"""
        return abs(self.y2 - self.y1)

    def validate_coordinates(self) -> bool:
        """验证坐标有效性"""
        return self.x1 < self.x2 and self.y1 < self.y2 and self.width > 0 and self.height > 0


class RoiConfigResponse(BaseModel):
    """ROI配置响应模型"""
    type: str = "roi_config"
    timestamp: datetime
    config: RoiConfig
    success: bool = True


class RoiCaptureResponse(BaseModel):
    """ROI截图响应模型"""
    type: str = "roi_capture"
    timestamp: datetime
    success: bool = True
    roi_data: RoiData
    config: RoiConfig
    message: str = "ROI capture successful"


class RoiFrameRateResponse(BaseModel):
    """ROI帧率设置响应模型"""
    type: str = "roi_frame_rate"
    timestamp: datetime
    frame_rate: int
    success: bool = True
    message: str = "ROI frame rate updated successfully"


class PeakRegionData(BaseModel):
    """波峰区域数据模型"""
    start_frame: int
    end_frame: int
    peak_frame: int
    max_value: float
    color: str  # 'green' or 'red'
    confidence: float
    difference: float


class PeakDetectionConfigResponse(BaseModel):
    """波峰检测配置响应模型"""
    type: str = "peak_detection_config"
    timestamp: datetime
    threshold: float
    margin_frames: int
    difference_threshold: float
    min_region_length: int
    success: bool = True
    message: str = "Peak detection configuration retrieved successfully"


class EnhancedPeakSignal(BaseModel):
    """增强波峰信号模型"""
    signal: Optional[int]  # 1 for peak, None for no peak
    color: Optional[str]  # 'green' or 'red'
    confidence: float
    threshold: float
    in_peak_region: bool
    frame_count: int


class AnalyzeResponse(BaseModel):
    has_hem: bool
    events: List[AnalyzeEvent]
    baseline: float
    series: List[AnalyzeSeriesPoint]
    realtime: bool
    peak_signal: Optional[int]
    enhanced_peak: Optional[EnhancedPeakSignal] = None
    peak_regions: List[PeakRegionData] = []
    frame_count: int
