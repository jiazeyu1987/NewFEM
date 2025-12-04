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
    PeakDetectionConfigResponse,
    PeakSignalResponse,
    RealtimeDataResponse,
    RoiCaptureResponse,
    RoiConfig,
    RoiConfigResponse,
    RoiData,
    RoiFrameRateResponse,
    RoiTimeSeriesPoint,
    DataFpsResponse,
    RoiWindowCaptureResponse,
    RoiWindowCaptureWithPeaksResponse,
    StatusResponse,
    SystemStatus,
    TimeSeriesPoint,
    WindowCaptureResponse,
)
from ..core.data_store import data_store
from ..core.processor import processor
from ..core.roi_capture import roi_capture_service
from ..utils import create_roi_data_with_image, generate_waveform_image_with_peaks
from ..peak_detection import detect_peaks


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
        # 使用ROI帧率来计算时间间隔，实现数据生成与ROI截图同步
        roi_frame_rate = roi_capture_service.get_roi_frame_rate()
        interval = 1.0 / roi_frame_rate  # 动态时间间隔，基于ROI帧率
        current_time = datetime.utcnow()

        if count == 1:
            # 单点请求：只生成最新的数据点
            series.append(TimeSeriesPoint(t=0.0, value=roi_data.gray_value))
        else:
            # 多点请求：生成连续的时间点（向后兼容）
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
    """设置ROI配置并保存到JSON文件"""
    verify_password(password)

    logger.info("🎯 Setting ROI config: (%d,%d) -> (%d,%d)", x1, y1, x2, y2)

    # 创建ROI配置
    roi_config = RoiConfig(x1=x1, y1=y1, x2=x2, y2=y2)

    # 验证坐标
    if not roi_config.validate_coordinates():
        logger.warning("Invalid ROI config: coordinates validation failed")
        raise HTTPException(status_code=400, detail="INVALID_ROI_COORDINATES")

    # 保存到JSON配置文件
    try:
        from ..core.config_manager import get_config_manager
        config_manager = get_config_manager()

        # 更新ROI配置
        roi_updates = {
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2
        }

        success = config_manager.update_config({"default_config": roi_updates}, section="roi_capture")
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update ROI configuration")

        # 保存到文件
        if not config_manager.save_config():
            raise HTTPException(status_code=500, detail="Failed to save ROI configuration")

        # 同时保存到data_store以保持兼容性
        data_store.set_roi_config(roi_config)

        logger.info("✅ ROI config saved to JSON file successfully: size=%dx%d, center=(%d,%d)",
                   roi_config.width, roi_config.height, roi_config.center_x, roi_config.center_y)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save ROI config to JSON: %s", str(e))
        raise HTTPException(status_code=500, detail="FAILED_TO_SET_ROI_CONFIG")

    return RoiConfigResponse(
        timestamp=datetime.utcnow(),
        config=roi_config,
        success=True,
    )


@router.get("/roi/config", response_model=RoiConfigResponse)
async def get_roi_config() -> RoiConfigResponse:
    """获取当前ROI配置（优先从JSON文件读取）"""
    try:
        # 优先从JSON配置文件读取
        from ..core.config_manager import get_config_manager
        config_manager = get_config_manager()

        roi_config_dict = config_manager.get_config(section="roi_capture", key="default_config")
        if roi_config_dict and all(key in roi_config_dict for key in ['x1', 'y1', 'x2', 'y2']):
            # 从JSON配置创建ROI对象
            roi_config = RoiConfig(
                x1=roi_config_dict['x1'],
                y1=roi_config_dict['y1'],
                x2=roi_config_dict['x2'],
                y2=roi_config_dict['y2']
            )
            logger.debug("📍 ROI config loaded from JSON: (%d,%d) -> (%d,%d), size=%dx%d",
                        roi_config.x1, roi_config.y1, roi_config.x2, roi_config.y2,
                        roi_config.width, roi_config.height)
        else:
            # 从data_store读取（向后兼容）
            roi_config = data_store.get_roi_config()
            logger.debug("📍 ROI config loaded from data_store: (%d,%d) -> (%d,%d), size=%dx%d",
                        roi_config.x1, roi_config.y1, roi_config.x2, roi_config.y2,
                        roi_config.width, roi_config.height)

    except Exception as e:
        logger.warning(f"Failed to load ROI config from JSON, using data_store: {e}")
        # 降级到data_store
        roi_config = data_store.get_roi_config()

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

# ROI帧率管理端点
@router.get("/roi/frame-rate", response_model=RoiFrameRateResponse)
async def get_roi_frame_rate() -> RoiFrameRateResponse:
    """获取当前ROI帧率"""
    frame_rate = roi_capture_service.get_roi_frame_rate()

    return RoiFrameRateResponse(
        timestamp=datetime.utcnow(),
        frame_rate=frame_rate,
        success=True,
        message=f"Current ROI frame rate: {frame_rate} FPS"
    )


@router.post("/roi/frame-rate", response_model=RoiFrameRateResponse)
async def set_roi_frame_rate(
    frame_rate: int = Form(...),
    password: str = Form(...),
) -> RoiFrameRateResponse:
    """设置ROI帧率"""
    verify_password(password)

    logger.info("🎯 Setting ROI frame rate: %d FPS", frame_rate)

    # 验证帧率范围
    if not 1 <= frame_rate <= 60:
        logger.error("Invalid ROI frame rate: %d (must be 1-60)", frame_rate)
        error = ErrorResponse(
            timestamp=datetime.utcnow(),
            error_code="INVALID_FRAME_RATE",
            error_message="ROI frame rate must be between 1 and 60",
            details=ErrorDetails(
                parameter="frame_rate",
                value=frame_rate,
                constraint="1 <= frame_rate <= 60"
            )
        )
        return JSONResponse(status_code=400, content=error.model_dump(mode='json'))

    # 设置帧率
    success = roi_capture_service.set_roi_frame_rate(frame_rate)
    if not success:
        error = ErrorResponse(
            timestamp=datetime.utcnow(),
            error_code="FRAME_RATE_SET_FAILED",
            error_message="Failed to set ROI frame rate",
            details=ErrorDetails(
                parameter="frame_rate",
                value=frame_rate,
                constraint="Internal error occurred"
            )
        )
        return JSONResponse(status_code=500, content=error.model_dump(mode='json'))

    logger.info("✅ ROI frame rate set successfully to %d FPS", frame_rate)

    return RoiFrameRateResponse(
        timestamp=datetime.utcnow(),
        frame_rate=frame_rate,
        success=True,
        message=f"ROI frame rate updated to {frame_rate} FPS"
    )


@router.post("/data/fps", response_model=DataFpsResponse)
async def set_data_fps(
    fps: int = Form(...),
    password: str = Form(...),
) -> DataFpsResponse:
    """设置数据生成频率"""
    verify_password(password)

    logger.info("🎯 Setting data generation FPS: %d", fps)

    # 验证FPS范围
    if not 10 <= fps <= 120:
        logger.error("Invalid data FPS: %d (must be 10-120)", fps)
        error = ErrorResponse(
            timestamp=datetime.utcnow(),
            error_code="INVALID_FPS",
            error_message="Data generation FPS must be between 10 and 120",
            details=ErrorDetails(
                parameter="fps",
                value=fps,
                constraint="10 <= fps <= 120"
            )
        )
        return JSONResponse(status_code=400, content=error.model_dump(mode='json'))

    # 保存到JSON配置文件
    try:
        from ..core.config_manager import get_config_manager
        config_manager = get_config_manager()

        updates = {"fps": fps}
        success = config_manager.update_config(updates, section="data_processing")
        config_manager.save_config()

        if not success:
            error = ErrorResponse(
                timestamp=datetime.utcnow(),
                error_code="FPS_SET_FAILED",
                error_message="Failed to save data FPS to configuration file",
                details=ErrorDetails(
                    parameter="fps",
                    value=fps,
                    constraint="JSON file write error"
                )
            )
            return JSONResponse(status_code=500, content=error.model_dump(mode='json'))

        logger.info("✅ Data generation FPS saved to JSON file: %d", fps)

    except Exception as e:
        logger.error("Failed to save data FPS to JSON file: %s", str(e))
        error = ErrorResponse(
            timestamp=datetime.utcnow(),
            error_code="FPS_SET_FAILED",
            error_message="Failed to save data FPS to configuration file",
            details=ErrorDetails(
                parameter="fps",
                value=fps,
                constraint=str(e)
            )
        )
        return JSONResponse(status_code=500, content=error.model_dump(mode='json'))

    logger.info("✅ Data generation FPS set successfully to %d", fps)

    return DataFpsResponse(
        timestamp=datetime.utcnow(),
        fps=fps,
        success=True,
        message=f"Data generation FPS updated to {fps}"
    )


@router.get("/data/fps", response_model=DataFpsResponse)
async def get_data_fps() -> DataFpsResponse:
    """获取当前数据生成频率"""
    from ..config import settings

    return DataFpsResponse(
        timestamp=datetime.utcnow(),
        fps=settings.fps,
        success=True,
        message=f"Current data generation FPS: {settings.fps}"
    )


# 波峰检测配置端点
@router.get("/peak-detection/config", response_model=PeakDetectionConfigResponse)
async def get_peak_detection_config() -> PeakDetectionConfigResponse:
    """获取当前波峰检测配置"""
    return PeakDetectionConfigResponse(
        timestamp=datetime.utcnow(),
        threshold=settings.peak_threshold,
        margin_frames=settings.peak_margin_frames,
        difference_threshold=settings.peak_difference_threshold,
        min_region_length=settings.peak_min_region_length,
        success=True,
        message="Peak detection configuration retrieved successfully"
    )


@router.post("/peak-detection/config", response_model=PeakDetectionConfigResponse)
async def set_peak_detection_config(
    threshold: Optional[float] = Form(None),
    margin_frames: Optional[int] = Form(None),
    difference_threshold: Optional[float] = Form(None),
    min_region_length: Optional[int] = Form(None)
) -> PeakDetectionConfigResponse:
    """设置波峰检测配置参数并保存到JSON文件"""
    logger.info("🔧 Peak detection configuration update requested")

    # 验证配置参数
    updates = {}

    if threshold is not None:
        if not (50.0 <= threshold <= 255.0):
            error = ErrorResponse(
                timestamp=datetime.utcnow(),
                error_code="INVALID_THRESHOLD",
                error_message="Threshold must be between 50.0 and 255.0",
                details=ErrorDetails(
                    parameter="threshold",
                    value=threshold,
                    constraint="Range: 50.0-255.0"
                )
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode='json'))
        updates["threshold"] = threshold

    if margin_frames is not None:
        if not (1 <= margin_frames <= 20):
            error = ErrorResponse(
                timestamp=datetime.utcnow(),
                error_code="INVALID_MARGIN_FRAMES",
                error_message="Margin frames must be between 1 and 20",
                details=ErrorDetails(
                    parameter="margin_frames",
                    value=margin_frames,
                    constraint="Range: 1-20"
                )
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode='json'))
        updates["margin_frames"] = margin_frames

    if difference_threshold is not None:
        if not (0.1 <= difference_threshold <= 10.0):
            error = ErrorResponse(
                timestamp=datetime.utcnow(),
                error_code="INVALID_DIFFERENCE_THRESHOLD",
                error_message="Difference threshold must be between 0.1 and 10.0",
                details=ErrorDetails(
                    parameter="difference_threshold",
                    value=difference_threshold,
                    constraint="Range: 0.1-10.0"
                )
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode='json'))
        updates["difference_threshold"] = difference_threshold

    if min_region_length is not None:
        if not (1 <= min_region_length <= 20):
            error = ErrorResponse(
                timestamp=datetime.utcnow(),
                error_code="INVALID_MIN_REGION_LENGTH",
                error_message="Minimum region length must be between 1 and 20",
                details=ErrorDetails(
                    parameter="min_region_length",
                    value=min_region_length,
                    constraint="Range: 1-20"
                )
            )
            return JSONResponse(status_code=400, content=error.model_dump(mode='json'))
        updates["min_region_length"] = min_region_length

    # 如果有更新，保存到JSON配置文件
    if updates:
        try:
            from ..core.config_manager import get_config_manager
            config_manager = get_config_manager()

            success = config_manager.update_config(updates, section="peak_detection")
            if not success:
                raise HTTPException(status_code=500, detail="Failed to update peak detection configuration")

            # 保存到文件
            if not config_manager.save_config():
                raise HTTPException(status_code=500, detail="Failed to save peak detection configuration")

            logger.info("✅ Peak detection config saved to JSON file: %s", ", ".join(f"{k}={v}" for k, v in updates.items()))

            # 更新运行时settings对象以保持兼容性
            if "threshold" in updates:
                settings.peak_threshold = updates["threshold"]
            if "margin_frames" in updates:
                settings.peak_margin_frames = updates["margin_frames"]
            if "difference_threshold" in updates:
                settings.peak_difference_threshold = updates["difference_threshold"]
            if "min_region_length" in updates:
                settings.peak_min_region_length = updates["min_region_length"]

            # 更新处理器的配置
            if hasattr(processor, '_enhanced_detector'):
                from ..core.enhanced_peak_detector import PeakDetectionConfig
                new_config = PeakDetectionConfig(
                    threshold=settings.peak_threshold,
                    margin_frames=settings.peak_margin_frames,
                    difference_threshold=settings.peak_difference_threshold,
                    min_region_length=settings.peak_min_region_length
                )
                processor._enhanced_detector.update_config(new_config)
                logger.info("🔧 Enhanced peak detector configuration updated: %s", ", ".join(f"{k}={v}" for k, v in updates.items()))

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to save peak detection config to JSON: %s", str(e))
            raise HTTPException(status_code=500, detail="FAILED_TO_SET_PEAK_DETECTION_CONFIG")

    fields_str = ", ".join(f"{k}={v}" for k, v in updates.items()) if updates else "no changes"
    logger.info("✅ Peak detection configuration updated: %s", fields_str)

    return PeakDetectionConfigResponse(
        timestamp=datetime.utcnow(),
        threshold=settings.peak_threshold,
        margin_frames=settings.peak_margin_frames,
        difference_threshold=settings.peak_difference_threshold,
        min_region_length=settings.peak_min_region_length,
        success=True,
        message=f"Peak detection configuration updated: {fields_str}"
    )


# 窗口截取端点
@router.get("/data/window-capture", response_model=WindowCaptureResponse)
async def window_capture(
    count: int = Query(100, ge=50, le=200, description="窗口大小：50-200帧")
) -> WindowCaptureResponse:
    """截取指定帧数的历史数据窗口"""
    logger.info("🖼️ Window capture requested: count=%d", count)

    # 从数据存储中获取指定数量的历史帧
    frames = data_store.get_series(count)
    if not frames:
        logger.warning("Window capture failed: no data available")
        raise HTTPException(status_code=404, detail="No data available for capture")

    # 获取当前状态信息
    _, current_frame_count, _, _, _, baseline = data_store.get_status_snapshot()

    # 计算帧范围
    start_frame = max(0, current_frame_count - len(frames))
    end_frame = current_frame_count - 1

    # 转换为TimeSeriesPoint格式
    series = []
    for frame in frames:
        series.append(TimeSeriesPoint(
            t=(frame.timestamp - frames[0].timestamp).total_seconds(),
            value=frame.value
        ))

    # 构建元数据
    capture_metadata = {
        "start_frame": start_frame,
        "end_frame": end_frame,
        "actual_frame_count": len(frames),
        "baseline": baseline,
        "capture_duration": (frames[-1].timestamp - frames[0].timestamp).total_seconds() if len(frames) > 1 else 0.0,
        "current_frame_count": current_frame_count
    }

    logger.info("✅ Window capture successful: frames=%d, range=(%d,%d), duration=%.3fs",
               len(series), start_frame, end_frame, capture_metadata["capture_duration"])

    return WindowCaptureResponse(
        timestamp=datetime.utcnow(),
        window_size=count,
        frame_range=(start_frame, end_frame),
        series=series,
        capture_metadata=capture_metadata
    )


# ROI窗口截取端点
@router.get("/data/roi-window-capture", response_model=RoiWindowCaptureResponse)
async def roi_window_capture(
    count: int = Query(100, ge=50, le=500, description="ROI窗口大小：50-500帧")
) -> RoiWindowCaptureResponse:
    """截取指定帧数的ROI灰度分析历史数据窗口"""
    logger.info("🖼️ ROI window capture requested: count=%d", count)

    # 从数据存储中获取指定数量的ROI历史帧
    roi_frames = data_store.get_roi_series(count)
    if not roi_frames:
        logger.warning("ROI window capture failed: no ROI data available")
        raise HTTPException(status_code=404, detail="No ROI data available for capture")

    # 获取当前状态信息
    _, current_main_frame_count, _, _, _, _ = data_store.get_status_snapshot()
    roi_count, roi_buffer_size, last_gray_value, last_main_frame_count = data_store.get_roi_status_snapshot()

    # 计算帧范围
    roi_start_frame = max(0, roi_count - len(roi_frames))
    roi_end_frame = roi_count - 1

    # 转换为RoiTimeSeriesPoint格式
    series = []
    for roi_frame in roi_frames:
        series.append(RoiTimeSeriesPoint(
            t=(roi_frame.timestamp - roi_frames[0].timestamp).total_seconds(),
            gray_value=roi_frame.gray_value,
            roi_index=roi_frame.index
        ))

    # 构建ROI配置信息
    roi_config = roi_frames[0].roi_config
    roi_config_dict = {
        "x1": roi_config.x1,
        "y1": roi_config.y1,
        "x2": roi_config.x2,
        "y2": roi_config.y2,
        "width": roi_config.width,
        "height": roi_config.height,
        "center_x": roi_config.center_x,
        "center_y": roi_config.center_y
    }

    # 构建元数据
    capture_metadata = {
        "roi_start_frame": roi_start_frame,
        "roi_end_frame": roi_end_frame,
        "actual_roi_frame_count": len(roi_frames),
        "main_frame_start": roi_frames[0].frame_count if roi_frames else 0,
        "main_frame_end": roi_frames[-1].frame_count if roi_frames else 0,
        "capture_duration": (roi_frames[-1].timestamp - roi_frames[0].timestamp).total_seconds() if len(roi_frames) > 1 else 0.0,
        "current_roi_frame_count": roi_count,
        "current_main_frame_count": current_main_frame_count,
        "roi_buffer_size": roi_buffer_size,
        "last_gray_value": last_gray_value
    }

    # 获取ROI帧率信息
    actual_fps, available_frames = data_store.get_roi_frame_rate_info()
    capture_metadata["actual_roi_fps"] = actual_fps
    capture_metadata["available_roi_frames"] = available_frames

    logger.info("✅ ROI window capture successful: frames=%d, roi_range=(%d,%d), main_range=(%d,%d), duration=%.3fs",
               len(series), roi_start_frame, roi_end_frame,
               capture_metadata["main_frame_start"], capture_metadata["main_frame_end"],
               capture_metadata["capture_duration"])

    return RoiWindowCaptureResponse(
        timestamp=datetime.utcnow(),
        window_size=count,
        roi_frame_range=(roi_start_frame, roi_end_frame),
        main_frame_range=(capture_metadata["main_frame_start"], capture_metadata["main_frame_end"]),
        series=series,
        roi_config=roi_config_dict,
        capture_metadata=capture_metadata
    )


# ROI窗口截取带波峰检测端点
@router.get("/data/roi-window-capture-with-peaks", response_model=RoiWindowCaptureWithPeaksResponse)
async def roi_window_capture_with_peaks(
    count: int = Query(100, ge=50, le=500, description="ROI窗口大小：50-500帧"),
    threshold: Optional[float] = Query(None, ge=0.0, le=255.0, description="波峰检测阈值：0-255（留空使用配置值）"),
    margin_frames: Optional[int] = Query(None, ge=1, le=20, description="边界扩展帧数：1-20（留空使用配置值）"),
    difference_threshold: Optional[float] = Query(None, ge=0.1, le=10.0, description="帧差值阈值：0.1-10.0（留空使用配置值）")
) -> RoiWindowCaptureWithPeaksResponse:
    """截取指定帧数的ROI灰度分析历史数据窗口并进行波峰检测分析"""
    # 使用settings中的默认值，如果查询参数未提供
    if threshold is None:
        threshold = settings.peak_threshold
    if margin_frames is None:
        margin_frames = settings.peak_margin_frames
    if difference_threshold is None:
        difference_threshold = settings.peak_difference_threshold

    logger.info("🔍 ROI window capture with peak detection requested: count=%d, threshold=%.1f, margin=%d, diff=%.2f (using latest config)",
                count, threshold, margin_frames, difference_threshold)

    # 从数据存储中获取指定数量的ROI历史帧
    roi_frames = data_store.get_roi_series(count)
    if not roi_frames:
        logger.warning("ROI window capture with peaks failed: no ROI data available")
        raise HTTPException(status_code=404, detail="No ROI data available for capture")

    # 获取当前状态信息
    _, current_main_frame_count, _, _, _, _ = data_store.get_status_snapshot()
    roi_count, roi_buffer_size, last_gray_value, last_main_frame_count = data_store.get_roi_status_snapshot()

    # 计算帧范围
    roi_start_frame = max(0, roi_count - len(roi_frames))
    roi_end_frame = roi_count - 1

    # 转换为RoiTimeSeriesPoint格式
    series = []
    gray_values = []  # 用于波峰检测的灰度值列表
    for roi_frame in roi_frames:
        gray_values.append(roi_frame.gray_value)
        series.append(RoiTimeSeriesPoint(
            t=(roi_frame.timestamp - roi_frames[0].timestamp).total_seconds(),
            gray_value=roi_frame.gray_value,
            roi_index=roi_frame.index
        ))

    # 构建ROI配置信息
    roi_config = roi_frames[0].roi_config
    roi_config_dict = {
        "x1": roi_config.x1,
        "y1": roi_config.y1,
        "x2": roi_config.x2,
        "y2": roi_config.y2,
        "width": roi_config.width,
        "height": roi_config.height,
        "center_x": roi_config.center_x,
        "center_y": roi_config.center_y
    }

    # 构建元数据
    capture_metadata = {
        "roi_start_frame": roi_start_frame,
        "roi_end_frame": roi_end_frame,
        "actual_roi_frame_count": len(roi_frames),
        "main_frame_start": roi_frames[0].frame_count if roi_frames else 0,
        "main_frame_end": roi_frames[-1].frame_count if roi_frames else 0,
        "capture_duration": (roi_frames[-1].timestamp - roi_frames[0].timestamp).total_seconds() if len(roi_frames) > 1 else 0.0,
        "current_roi_frame_count": roi_count,
        "current_main_frame_count": current_main_frame_count,
        "roi_buffer_size": roi_buffer_size,
        "last_gray_value": last_gray_value
    }

    # 获取ROI帧率信息
    actual_fps, available_frames = data_store.get_roi_frame_rate_info()
    capture_metadata["actual_roi_fps"] = actual_fps
    capture_metadata["available_roi_frames"] = available_frames

    # 执行波峰检测
    logger.info("🎯 Starting peak detection on %d ROI frames with threshold=%.1f", len(gray_values), threshold)
    print(f"\n=== ROI窗口波峰检测开始 ===")
    print(f"窗口大小: {len(gray_values)} 帧")
    print(f"检测参数: 阈值={threshold}, 边界={margin_frames}, 差值阈值={difference_threshold}")

    try:
        green_peaks, red_peaks = detect_peaks(
            curve=gray_values,
            threshold=threshold,
            marginFrames=margin_frames,
            differenceThreshold=difference_threshold
        )

        # 波峰检测结果
        peak_detection_results = {
            "green_peaks": green_peaks,
            "red_peaks": red_peaks,
            "total_peaks": len(green_peaks) + len(red_peaks),
            "green_peak_count": len(green_peaks),
            "red_peak_count": len(red_peaks)
        }

        # 波峰检测参数
        peak_detection_params = {
            "threshold": threshold,
            "margin_frames": margin_frames,
            "difference_threshold": difference_threshold,
            "data_points": len(gray_values)
        }

        print(f"✅ 波峰检测完成:")
        print(f"   - 绿色波峰 (稳定): {len(green_peaks)} 个: {green_peaks}")
        print(f"   - 红色波峰 (不稳定): {len(red_peaks)} 个: {red_peaks}")
        print(f"   - 总计: {len(green_peaks) + len(red_peaks)} 个波峰")
        print(f"=== ROI窗口波峰检测结束 ===\n")

        logger.info("✅ ROI window peak detection completed: green=%d, red=%d, total=%d",
                    len(green_peaks), len(red_peaks), len(green_peaks) + len(red_peaks))

    except Exception as e:
        logger.error("❌ Peak detection failed: %s", str(e))
        print(f"❌ 波峰检测失败: {str(e)}")
        peak_detection_results = {"error": str(e)}
        peak_detection_params = {"error": True}

    logger.info("✅ ROI window capture with peaks successful: frames=%d, roi_range=(%d,%d), main_range=(%d,%d), duration=%.3fs",
               len(series), roi_start_frame, roi_end_frame,
               capture_metadata["main_frame_start"], capture_metadata["main_frame_end"],
               capture_metadata["capture_duration"])

    return RoiWindowCaptureWithPeaksResponse(
        timestamp=datetime.utcnow(),
        window_size=count,
        roi_frame_range=(roi_start_frame, roi_end_frame),
        main_frame_range=(capture_metadata["main_frame_start"], capture_metadata["main_frame_end"]),
        series=series,
        roi_config=roi_config_dict,
        capture_metadata=capture_metadata,
        peak_detection_results=peak_detection_results,
        peak_detection_params=peak_detection_params
    )


# 生成带有波峰标注的波形图像端点
@router.get("/data/waveform-with-peaks")
async def waveform_with_peaks(
    count: int = Query(100, ge=10, le=500, description="波形数据点数：10-500"),
    threshold: Optional[float] = Query(None, ge=50.0, le=255.0, description="波峰检测阈值：50-255（留空使用配置值）"),
    margin_frames: Optional[int] = Query(None, ge=1, le=20, description="边界扩展帧数：1-20（留空使用配置值）"),
    difference_threshold: Optional[float] = Query(None, ge=0.1, le=10.0, description="帧差值阈值：0.1-10.0（留空使用配置值）")
):
    """生成带有波峰标注的波形图像"""
    # 使用settings中的默认值，如果查询参数未提供
    if threshold is None:
        threshold = settings.peak_threshold
    if margin_frames is None:
        margin_frames = settings.peak_margin_frames
    if difference_threshold is None:
        difference_threshold = settings.peak_difference_threshold

    logger.info("🎨 Waveform with peaks image requested: count=%d, threshold=%.1f, margin=%d, diff=%.2f (using latest config)",
                count, threshold, margin_frames, difference_threshold)

    # 获取ROI历史数据
    roi_frames = data_store.get_roi_series(count)
    if not roi_frames:
        # 如果没有ROI数据，使用模拟数据
        import numpy as np
        time_points = np.linspace(0, 10, count)
        # 生成模拟波形：基线 + 噪声 + 几个波峰
        baseline = 100
        noise = np.random.normal(0, 5, count)

        # 添加几个模拟波峰
        signal = np.ones(count) * baseline + noise
        # 添加绿色波峰（较强的）
        for peak_pos in [30, 60, 85]:
            if peak_pos < count:
                peak_width = 5
                for i in range(max(0, peak_pos - peak_width), min(count, peak_pos + peak_width + 1)):
                    signal[i] += 40 * np.exp(-((i - peak_pos) ** 2) / 8)

        # 添加红色波峰（较弱的）
        for peak_pos in [20, 45, 75]:
            if peak_pos < count:
                peak_width = 3
                for i in range(max(0, peak_pos - peak_width), min(count, peak_pos + peak_width + 1)):
                    signal[i] += 25 * np.exp(-((i - peak_pos) ** 2) / 6)

        curve_data = signal.tolist()
    else:
        # 使用真实ROI数据
        curve_data = [frame.gray_value for frame in roi_frames]

    # 执行波峰检测
    green_peaks, red_peaks = detect_peaks(
        curve=curve_data,
        threshold=threshold,
        marginFrames=margin_frames,
        differenceThreshold=difference_threshold
    )

    # 生成带有波峰标注的波形图像
    try:
        waveform_image = generate_waveform_image_with_peaks(
            curve_data=curve_data,
            green_peaks=green_peaks,
            red_peaks=red_peaks,
            width=600,
            height=300
        )

        logger.info("✅ Waveform with peaks image generated successfully: green=%d, red=%d",
                   len(green_peaks), len(red_peaks))

        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "image_data": waveform_image,
            "metadata": {
                "data_points": len(curve_data),
                "green_peaks": len(green_peaks),
                "red_peaks": len(red_peaks),
                "total_peaks": len(green_peaks) + len(red_peaks),
                "detection_params": {
                    "threshold": threshold,
                    "margin_frames": margin_frames,
                    "difference_threshold": difference_threshold
                },
                "data_range": {
                    "min": min(curve_data) if curve_data else 0,
                    "max": max(curve_data) if curve_data else 0,
                    "avg": sum(curve_data) / len(curve_data) if curve_data else 0
                }
            }
        }

    except Exception as e:
        logger.error("Error generating waveform image: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate waveform image: {str(e)}")


# ============================================================================
# 统一配置管理API端点
# ============================================================================

@router.get("/config", summary="获取完整配置", response_model=dict)
async def get_config(
    section: Optional[str] = Query(None, description="配置节名称，如 'server', 'peak_detection' 等"),
    password: str = Query(..., description="管理密码")
):
    """
    获取配置信息

    Args:
        section: 可选的配置节名称，如果不提供则返回完整配置
        password: 管理密码

    Returns:
        配置信息字典
    """
    if password != settings.password:
        raise HTTPException(status_code=401, detail="密码错误")

    try:
        from ..core.config_manager import get_config_manager
        config_manager = get_config_manager()

        if section:
            config = config_manager.get_config(section=section)
            if config is None:
                raise HTTPException(status_code=404, detail=f"配置节 '{section}' 不存在")
            return {"section": section, "config": config}
        else:
            config = config_manager.get_full_config()
            return {"config": config}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.post("/config", summary="更新配置")
async def update_config(
    section: Optional[str] = Query(None, description="配置节名称"),
    key: Optional[str] = Query(None, description="配置键名称"),
    value: Optional[str] = Query(None, description="配置值（JSON字符串）"),
    config_data: Optional[str] = Query(None, description="完整配置数据（JSON字符串）"),
    password: str = Query(..., description="管理密码")
):
    """
    更新配置信息

    Args:
        section: 配置节名称（可选）
        key: 配置键名称（可选）
        value: 配置值，单个值更新时使用（JSON格式）
        config_data: 完整配置数据，批量更新时使用
        password: 管理密码

    Returns:
        更新结果
    """
    if password != settings.password:
        raise HTTPException(status_code=401, detail="密码错误")

    try:
        from ..core.config_manager import get_config_manager
        config_manager = get_config_manager()

        success = False

        if config_data is not None:
            # 批量更新配置
            try:
                import json
                parsed_config_data = json.loads(config_data) if isinstance(config_data, str) else config_data

                if isinstance(parsed_config_data, dict):
                    if section:
                        # 更新指定配置节
                        success = config_manager.update_config(parsed_config_data, section=section)
                    else:
                        # 更新多个配置节
                        success = config_manager.update_config(parsed_config_data)
                else:
                    raise HTTPException(status_code=400, detail="config_data 必须为字典格式")
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="config_data JSON格式错误")
        elif value is not None and section and key:
            # 更新单个配置值
            try:
                # value可能是JSON字符串，需要解析
                import json
                parsed_value = json.loads(value) if isinstance(value, str) else value
                success = config_manager.set_config(parsed_value, section=section, key=key)
            except json.JSONDecodeError:
                # 如果不是JSON，直接使用字符串值
                success = config_manager.set_config(value, section=section, key=key)
        else:
            raise HTTPException(status_code=400, detail="请提供有效的更新参数")

        if not success:
            raise HTTPException(status_code=500, detail="配置更新失败")

        # 保存配置到文件
        if not config_manager.save_config():
            raise HTTPException(status_code=500, detail="配置保存失败")

        logger.info(f"配置已更新: section={section}, key={key}")
        return {"success": True, "message": "配置更新成功"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


@router.post("/config/reload", summary="重新加载配置")
async def reload_config(
    password: str = Query(..., description="管理密码")
):
    """
    重新加载配置文件

    Args:
        password: 管理密码

    Returns:
        重新加载结果
    """
    if password != settings.password:
        raise HTTPException(status_code=401, detail="密码错误")

    try:
        from ..core.config_manager import get_config_manager
        config_manager = get_config_manager()

        # 重新加载配置文件
        if config_manager.reload_config():
            logger.info("配置文件重新加载成功")
            return {"success": True, "message": "配置文件重新加载成功"}
        else:
            raise HTTPException(status_code=500, detail="配置文件重新加载失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新加载配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"重新加载配置失败: {str(e)}")


@router.get("/config/export", summary="导出配置")
async def export_config(
    password: str = Query(..., description="管理密码")
):
    """
    导出配置为JSON格式

    Args:
        password: 管理密码

    Returns:
        JSON格式的配置字符串
    """
    if password != settings.password:
        raise HTTPException(status_code=401, detail="密码错误")

    try:
        from ..core.config_manager import get_config_manager
        config_manager = get_config_manager()

        config_json = config_manager.export_config()

        return JSONResponse(
            content={
                "success": True,
                "config_json": config_json,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    except Exception as e:
        logger.error(f"导出配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"导出配置失败: {str(e)}")


@router.post("/config/import", summary="导入配置")
async def import_config(
    config_json: str = Form(..., description="JSON格式的配置字符串"),
    password: str = Form(..., description="管理密码")
):
    """
    从JSON字符串导入配置

    Args:
        config_json: JSON格式的配置字符串
        password: 管理密码

    Returns:
        导入结果
    """
    if password != settings.password:
        raise HTTPException(status_code=401, detail="密码错误")

    try:
        from ..core.config_manager import get_config_manager
        config_manager = get_config_manager()

        if config_manager.import_config(config_json):
            logger.info("配置导入成功")
            return {"success": True, "message": "配置导入成功"}
        else:
            raise HTTPException(status_code=400, detail="配置格式无效或验证失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导入配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"导入配置失败: {str(e)}")


app = create_app()
