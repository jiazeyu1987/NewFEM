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
    RoiCaptureResponse,
    RoiConfig,
    RoiConfigResponse,
    RoiData,
    StatusResponse,
    SystemStatus,
    TimeSeriesPoint,
)
from ..core.data_store import data_store
from ..core.processor import processor
from ..core.roi_capture import roi_capture_service


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
        return JSONResponse(status_code=exc.status_code, content=error.model_dump(mode='json'))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        now = datetime.utcnow()
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        error = ErrorResponse(
            timestamp=now,
            error_code="INTERNAL_ERROR",
            error_message="Internal server error",
        )
        return JSONResponse(status_code=500, content=error.model_dump(mode='json'))

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
    logger.debug("📈 Realtime data requested: count=%d", count)
    frames = data_store.get_series(count)
    if not frames:
        # 如果没有数据，返回空序列和默认 ROI
        now = datetime.utcnow()
        logger.info("⚠️ Realtime data requested but no frames available - returning empty response")
        return RealtimeDataResponse(
            timestamp=now,
            frame_count=0,
            series=[],
            roi_data=RoiData(
                width=200,
                height=150,
                # 为无数据情况生成默认的"无数据"图片
                pixels=create_roi_data_with_image(0.0)[0],
                gray_value=0.0,
                format="base64",
            ),
            peak_signal=None,
            baseline=0.0,
        )

    # 获取状态快照
    (
        _status,
        frame_count,
        current_value,
        peak_signal,
        _buffer_size,
        baseline,
    ) = data_store.get_status_snapshot()

    # 只有在ROI已配置时才返回实时ROI数据，否则返回空数据
    roi_configured, roi_config = data_store.get_roi_status()
    if roi_configured:
        # ROI已配置，实时截图
        try:
            roi_data = roi_capture_service.capture_roi(roi_config)
            if roi_data is None:
                # 截图失败时返回空数据
                logger.warning("ROI capture failed in realtime_data, returning empty data")
                roi_data = RoiData(
                    width=roi_config.width,
                    height=roi_config.height,
                    pixels="roi_capture_failed",
                    gray_value=baseline,  # 使用基线值作为fallback
                    format="text",
                )
        except Exception as e:
            logger.error("Error capturing ROI in realtime_data: %s", str(e))
            roi_data = RoiData(
                width=roi_config.width,
                height=roi_config.height,
                pixels="roi_capture_error",
                gray_value=baseline,  # 使用基线值作为fallback
                format="text",
            )
    else:
        # ROI未配置，返回空数据
        roi_data = RoiData(
            width=0,
            height=0,
            pixels="roi_not_configured",
            gray_value=baseline,  # 使用基线值
            format="text",
        )

    # 生成时间序列数据
    if roi_configured and roi_data.format == "base64":
        # ROI已配置且有真实截图数据，使用ROI灰度值生成时间序列
        series = []
        interval = 1.0 / 60  # 60 FPS时间间隔
        current_time = datetime.utcnow()

        for i in range(count):
            # 生成连续的时间点，最近的点在前
            t = i * interval
            # 使用ROI灰度值
            value = roi_data.gray_value
            series.append(TimeSeriesPoint(t=t, value=value))

        # 更新current_value为ROI灰度值
        current_value = roi_data.gray_value
    else:
        # ROI未配置或无真实数据，使用模拟数据
        series = [
            TimeSeriesPoint(
                t=(frame.timestamp - frames[0].timestamp).total_seconds(),
                value=frame.value,
            )
            for frame in frames
        ]

    logger.debug(
        "📊 Realtime data response: frame_count=%d points=%d last_value=%.3f peak_signal=%s baseline=%.3f data_source=%s",
        frame_count,
        len(series),
        series[-1].value if series else 0.0,
        str(peak_signal),
        baseline,
        "roi_gray_value" if roi_configured and roi_data.format == "base64" else "simulated",
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
    logger.info("🎛️ Control command received: raw='%s' upper='%s' lower='%s'", cmd_raw, cmd_upper, cmd_lower)

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
        return JSONResponse(content=resp.model_dump(mode='json'))

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
        return JSONResponse(content=resp.model_dump(mode='json'))

    # 控制检测流程的命令使用 control_response 格式
    if cmd_lower == "start_detection":
        # 检查ROI是否已配置
        if not data_store.is_roi_configured():
            logger.warning("Attempted to start detection without ROI configuration")
            error = ErrorResponse(
                timestamp=now,
                error_code="ROI_NOT_CONFIGURED",
                error_message="ROI must be configured before starting detection",
                details=ErrorDetails(
                    parameter="ROI",
                    value="not configured",
                    constraint="ROI configuration is required before detection"
                )
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode='json'))

        processor.start()
        system_status = data_store.get_status()
        resp = ControlCommandResponse(
            timestamp=now,
            command="start_detection",
            status="success",
            message="Detection started",
        )
        logger.info("✅ Detection started successfully, status=%s", system_status)
        return JSONResponse(content=resp.model_dump(mode='json'))

    if cmd_lower == "stop_detection":
        processor.stop()
        system_status = data_store.get_status()
        resp = ControlCommandResponse(
            timestamp=now,
            command="stop_detection",
            status="success",
            message="Detection stopped",
        )
        logger.info("⏹️ Detection stopped successfully, status=%s", system_status)
        return JSONResponse(content=resp.model_dump(mode='json'))

    if cmd_lower == "pause_detection":
        processor.stop()
        resp = ControlCommandResponse(
            timestamp=now,
            command="pause_detection",
            status="success",
            message="Detection paused",
        )
        logger.info("Control pause_detection executed")
        return JSONResponse(content=resp.model_dump(mode='json'))

    if cmd_lower == "resume_detection":
        processor.start()
        resp = ControlCommandResponse(
            timestamp=now,
            command="resume_detection",
            status="success",
            message="Detection resumed",
        )
        logger.info("Control resume_detection executed")
        return JSONResponse(content=resp.model_dump(mode='json'))

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
    return JSONResponse(status_code=400, content=error.model_dump(mode='json'))


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


# ROI配置端点
@router.post("/roi/config", response_model=RoiConfigResponse)
async def set_roi_config(
    x1: int = Form(...),
    y1: int = Form(...),
    x2: int = Form(...),
    y2: int = Form(...),
    password: str = Form(...),
) -> RoiConfigResponse:
    """设置ROI配置"""
    verify_password(password)

    logger.info("🎯 Setting ROI config: (%d,%d) -> (%d,%d)", x1, y1, x2, y2)

    # 创建ROI配置
    roi_config = RoiConfig(x1=x1, y1=y1, x2=x2, y2=y2)

    # 暂时简化验证
    if not roi_config.validate_coordinates():
        logger.warning("Invalid ROI config: coordinates validation failed")
        raise HTTPException(status_code=400, detail="INVALID_ROI_COORDINATES")

    # 保存配置
    try:
        data_store.set_roi_config(roi_config)
        logger.info("✅ ROI config set successfully: size=%dx%d, center=(%d,%d)",
                   roi_config.width, roi_config.height, roi_config.center_x, roi_config.center_y)
    except ValueError as e:
        logger.error("Failed to set ROI config: %s", str(e))
        raise HTTPException(status_code=400, detail="FAILED_TO_SET_ROI_CONFIG")

    return RoiConfigResponse(
        timestamp=datetime.utcnow(),
        config=roi_config,
        success=True,
    )


@router.get("/roi/config", response_model=RoiConfigResponse)
async def get_roi_config() -> RoiConfigResponse:
    """获取当前ROI配置"""
    roi_config = data_store.get_roi_config()

    logger.debug("📍 Current ROI config: (%d,%d) -> (%d,%d), size=%dx%d",
                roi_config.x1, roi_config.y1, roi_config.x2, roi_config.y2,
                roi_config.width, roi_config.height)

    return RoiConfigResponse(
        timestamp=datetime.utcnow(),
        config=roi_config,
        success=True,
    )


@router.post("/roi/capture", response_model=RoiCaptureResponse)
async def capture_roi(
    password: str = Form(...),
) -> RoiCaptureResponse:
    """
    手动执行ROI截图（已弃用，建议使用realtime_data获取实时ROI截图）
    """
    verify_password(password)

    logger.info("📸 Manual ROI capture requested (deprecated)")

    # 获取当前ROI配置
    roi_config = data_store.get_roi_config()

    # 执行真实的ROI截图
    roi_data = roi_capture_service.capture_roi(roi_config)
    if roi_data is None:
        logger.error("Failed to capture ROI")
        raise HTTPException(status_code=500, detail="ROI_CAPTURE_FAILED")

    logger.info("✅ Manual ROI captured successfully: size=%dx%d, gray=%.2f",
               roi_data.width, roi_data.height, roi_data.gray_value)

    return RoiCaptureResponse(
        timestamp=datetime.utcnow(),
        success=True,
        roi_data=roi_data,
        config=roi_config,
        message="Manual ROI capture successful (use realtime_data for automatic capture)",
    )


app = create_app()
