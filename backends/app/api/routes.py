from __future__ import annotations

from datetime import datetime
from typing import Optional

import logging

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import settings
from ..logging_config import init_logging
from ..models import (
    AnalyzeEvent,
    AnalyzeResponse,
    AnalyzeSeriesPoint,
    ControlCommandResponse,
    ControlStatusResponse,
    ErrorDetails,
    ErrorResponse,
    HealthResponse,
    PeakSignalResponse,
    RealtimeDataResponse,
    RoiData,
    StatusResponse,
    SystemStatus,
    TimeSeriesPoint,
)
from ..core.data_store import data_store
from ..core.processor import processor


router = APIRouter()
logger = logging.getLogger("newfem.api")


def create_app() -> FastAPI:
    # 确保日志系统已初始化
    init_logging()
    logger.info("Creating FastAPI application instance")

    app = FastAPI(title="NewFEM API Server", version="3.0.0")

    # CORS 配置
    if settings.enable_cors:
        logger.info("Enabling CORS, allowed_origins=%s", settings.allowed_origins)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(o) for o in settings.allowed_origins],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 统一异常处理，返回文档中定义的错误格式
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        now = datetime.utcnow()
        logger.warning("HTTPException on %s %s: %s", request.method, request.url.path, exc.detail)
        error = ErrorResponse(
            timestamp=now,
            error_code=exc.detail if isinstance(exc.detail, str) else "HTTP_ERROR",
            error_message=str(exc.detail),
        )
        return JSONResponse(status_code=exc.status_code, content=error.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        now = datetime.utcnow()
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        error = ErrorResponse(
            timestamp=now,
            error_code="INTERNAL_ERROR",
            error_message="Internal server error",
        )
        return JSONResponse(status_code=500, content=error.model_dump())

    app.include_router(router)
    return app


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    logger.debug("Health endpoint called")
    return HealthResponse()


@router.get("/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    (
        system_status,
        frame_count,
        current_value,
        peak_signal,
        buffer_size,
        baseline,
    ) = data_store.get_status_snapshot()

    logger.debug(
        "Status endpoint snapshot status=%s frame_count=%d current=%.3f peak_signal=%s buffer_size=%d baseline=%.3f",
        system_status,
        frame_count,
        current_value,
        str(peak_signal),
        buffer_size,
        baseline,
    )

    return StatusResponse(
        status=system_status,
        frame_count=frame_count,
        current_value=current_value,
        peak_signal=peak_signal,
        buffer_size=buffer_size,
        baseline=baseline,
        timestamp=datetime.utcnow(),
    )


@router.get("/data/realtime", response_model=RealtimeDataResponse)
async def realtime_data(
    count: int = Query(100, ge=1, le=1000, description="Number of data points"),
) -> RealtimeDataResponse:
    logger.debug("Realtime data requested with count=%d", count)
    frames = data_store.get_series(count)
    if not frames:
        # 如果没有数据，返回空序列和默认 ROI
        now = datetime.utcnow()
        logger.info("Realtime data requested but no frames available")
        return RealtimeDataResponse(
            timestamp=now,
            frame_count=0,
            series=[],
            roi_data=RoiData(
                width=200,
                height=150,
                pixels="no_data",
                gray_value=0.0,
            ),
            peak_signal=None,
            baseline=0.0,
        )

    # 以最后一帧的时间为基准计算相对时间
    series = [
        TimeSeriesPoint(
            t=(frame.timestamp - frames[0].timestamp).total_seconds(),
            value=frame.value,
        )
        for frame in frames
    ]

    (
        _status,
        frame_count,
        current_value,
        peak_signal,
        _buffer_size,
        baseline,
    ) = data_store.get_status_snapshot()

    roi_data = RoiData(
        width=200,
        height=150,
        pixels=f"simulated_roi_{current_value:.1f}",
        gray_value=current_value,
    )

    logger.debug(
        "Realtime data response frame_count=%d points=%d last_value=%.3f peak_signal=%s baseline=%.3f",
        frame_count,
        len(series),
        series[-1].value if series else 0.0,
        str(peak_signal),
        baseline,
    )

    return RealtimeDataResponse(
        timestamp=datetime.utcnow(),
        frame_count=frame_count,
        series=series,
        roi_data=roi_data,
        peak_signal=peak_signal,
        baseline=baseline,
    )


def verify_password(password: str) -> None:
    if password != settings.password:
        logger.warning("Password verification failed")
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")
    logger.debug("Password verification succeeded")


@router.post("/control")
async def control(
    command: str = Form(...),
    password: str = Form(...),
) -> JSONResponse:
    verify_password(password)

    cmd_raw = command.strip()
    cmd_upper = cmd_raw.upper()
    cmd_lower = cmd_raw.lower()
    now = datetime.utcnow()
    logger.info("Control command received: raw=%s upper=%s lower=%s", cmd_raw, cmd_upper, cmd_lower)

    if cmd_upper == "PEAK_SIGNAL":
        (
            _status,
            frame_count,
            current_value,
            peak_signal,
            _buffer_size,
            _baseline,
        ) = data_store.get_status_snapshot()
        resp = PeakSignalResponse(
            timestamp=now,
            signal=peak_signal,
            has_peak=peak_signal is not None,
            current_value=current_value,
            frame_count=frame_count,
        )
        logger.debug(
            "Control PEAK_SIGNAL response signal=%s frame_count=%d current_value=%.3f",
            str(peak_signal),
            frame_count,
            current_value,
        )
        return JSONResponse(content=resp.model_dump())

    if cmd_upper == "STATUS":
        system_status = data_store.get_status()
        resp = ControlStatusResponse(
            timestamp=now,
            server_status=system_status,
            connected_clients=0,
            last_peak_signal=data_store.get_last_peak_signal(),
        )
        logger.debug(
            "Control STATUS response status=%s last_peak_signal=%s",
            system_status,
            str(data_store.get_last_peak_signal()),
        )
        return JSONResponse(content=resp.model_dump())

    # 控制检测流程的命令使用 control_response 格式
    if cmd_lower == "start_detection":
        processor.start()
        system_status = data_store.get_status()
        resp = ControlCommandResponse(
            timestamp=now,
            command="start_detection",
            status="success",
            message="Detection started",
        )
        logger.info("Control start_detection executed, status=%s", system_status)
        return JSONResponse(content=resp.model_dump())

    if cmd_lower == "stop_detection":
        processor.stop()
        system_status = data_store.get_status()
        resp = ControlCommandResponse(
            timestamp=now,
            command="stop_detection",
            status="success",
            message="Detection stopped",
        )
        logger.info("Control stop_detection executed, status=%s", system_status)
        return JSONResponse(content=resp.model_dump())

    if cmd_lower == "pause_detection":
        processor.stop()
        resp = ControlCommandResponse(
            timestamp=now,
            command="pause_detection",
            status="success",
            message="Detection paused",
        )
        logger.info("Control pause_detection executed")
        return JSONResponse(content=resp.model_dump())

    if cmd_lower == "resume_detection":
        processor.start()
        resp = ControlCommandResponse(
            timestamp=now,
            command="resume_detection",
            status="success",
            message="Detection resumed",
        )
        logger.info("Control resume_detection executed")
        return JSONResponse(content=resp.model_dump())

    # 未知命令
    error = ErrorResponse(
        timestamp=now,
        error_code="INVALID_COMMAND",
        error_message="Unsupported command",
        details=ErrorDetails(
            parameter="command",
            value=command,
            constraint="Must be one of PEAK_SIGNAL, STATUS, START_DETECT, STOP_DETECT, RESET",
        ),
    )
    logger.warning("Control received invalid command: %s", command)
    return JSONResponse(status_code=400, content=error.model_dump())


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    realtime: Optional[bool] = Form(None),
    duration: Optional[float] = Form(10.0),
    file: Optional[UploadFile] = File(None),
    roi_x: Optional[float] = Form(None),
    roi_y: Optional[float] = Form(None),
    roi_w: Optional[float] = Form(None),
    roi_h: Optional[float] = Form(None),
    sample_fps: Optional[float] = Form(8.0),
) -> AnalyzeResponse:
    """
    视频分析接口，根据文档规范返回模拟分析结果。
    当前实现不解析视频内容，而是基于内存数据构造示例响应，便于前端联调。
    """

    logger.info(
        "Analyze called realtime=%s duration=%s file=%s roi=(%s,%s,%s,%s) sample_fps=%s",
        realtime,
        duration,
        file.filename if file else None,
        roi_x,
        roi_y,
        roi_w,
        roi_h,
        sample_fps,
    )

    # 参数模式校验：要么实时模式，要么文件模式，不能二者兼有或都无
    realtime_mode = bool(realtime)
    file_mode = file is not None

    if realtime_mode and file_mode or (not realtime_mode and not file_mode):
        logger.warning("Analyze invalid parameter combination: realtime=%s file=%s", realtime, bool(file))
        raise HTTPException(status_code=400, detail="INVALID_PARAMETER")

    # 从数据存储中取一段数据用于模拟分析
    frames = data_store.get_series(100)
    if not frames:
        logger.info("Analyze called but no frame data available, returning empty analysis")
        return AnalyzeResponse(
            has_hem=False,
            events=[],
            baseline=0.0,
            series=[],
            realtime=realtime_mode,
            peak_signal=None,
            frame_count=0,
        )

    (
        _status,
        frame_count,
        _current_value,
        peak_signal,
        _buffer_size,
        baseline,
    ) = data_store.get_status_snapshot()

    # 构造 events：如果存在峰值，则构造一个示例事件
    events: list[AnalyzeEvent] = []
    if peak_signal is not None:
        last_frame = frames[-1]
        events.append(
            AnalyzeEvent(
                t=(last_frame.timestamp - frames[0].timestamp).total_seconds(),
                type="peak_detected",
                score=float(peak_signal),
            )
        )

    # 构造 series：基于帧数据生成统计字段
    series: list[AnalyzeSeriesPoint] = []
    # 简化实现：用 baseline 和当前值构造一些参考值
    for frame in frames:
        deviation = abs(frame.value - baseline)
        series.append(
            AnalyzeSeriesPoint(
                t=(frame.timestamp - frames[0].timestamp).total_seconds(),
                value=frame.value,
                ref=baseline,
                std=deviation / 3.0,
                high=baseline + deviation,
                orange=baseline + deviation / 2.0,
            )
        )

    has_hem = peak_signal is not None

    logger.debug(
        "Analyze response has_hem=%s events=%d points=%d baseline=%.3f peak_signal=%s frame_count=%d",
        has_hem,
        len(events),
        len(series),
        baseline,
        str(peak_signal),
        frame_count,
    )

    return AnalyzeResponse(
        has_hem=has_hem,
        events=events,
        baseline=baseline,
        series=series,
        realtime=realtime_mode,
        peak_signal=peak_signal,
        frame_count=frame_count,
    )


app = create_app()
