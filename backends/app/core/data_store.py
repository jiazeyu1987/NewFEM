from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, List, Optional, Tuple

import logging

from ..config import settings
from ..models import SystemStatus, RoiConfig


@dataclass
class Frame:
    index: int
    timestamp: datetime
    value: float


@dataclass
class RoiFrame:
    """ROI截图帧数据"""
    index: int
    timestamp: datetime
    gray_value: float
    roi_config: RoiConfig
    frame_count: int  # 主信号帧计数
    capture_duration: float  # ROI截图持续时间


class DataStore:
    """
    内存中的时序数据存储，线程安全。
    """

    def __init__(self, buffer_size: int) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._buffer_size = buffer_size
        self._frames: Deque[Frame] = deque(maxlen=buffer_size)
        self._lock = threading.Lock()

        # ROI历史数据存储 - 独立于主信号数据
        # 默认存储最近500个ROI截图帧（约4分钟，按2FPS计算）
        roi_buffer_size = 500
        self._roi_frames: Deque[RoiFrame] = deque(maxlen=roi_buffer_size)
        self._roi_frame_count: int = 0

        self._frame_count: int = 0
        self._current_value: float = 0.0
        self._baseline: float = 0.0
        self._peak_signal: Optional[int] = None
        self._last_peak_signal: Optional[int] = None
        self._status: SystemStatus = SystemStatus.STOPPED

        # ROI配置
        self._roi_config: RoiConfig = RoiConfig(x1=0, y1=0, x2=200, y2=150)
        self._roi_configured: bool = False  # 标记ROI是否已由用户配置

        # 增强波峰检测信息
        self._enhanced_peak_color: Optional[str] = None  # 'green' or 'red'
        self._enhanced_peak_confidence: float = 0.0
        self._enhanced_peak_threshold: float = 0.0
        self._enhanced_in_peak_region: bool = False
        self._enhanced_peak_frame_count: int = 0

    # 写操作
    def add_frame(
        self,
        value: float,
        timestamp: Optional[datetime] = None,
        peak_signal: Optional[int] = None,
    ) -> Frame:
        if timestamp is None:
            timestamp = datetime.utcnow()
        with self._lock:
            self._frame_count += 1
            frame = Frame(index=self._frame_count, timestamp=timestamp, value=value)
            self._frames.append(frame)
            self._current_value = value
            self._update_baseline_locked()
            self._peak_signal = peak_signal
            if peak_signal is not None:
                self._last_peak_signal = peak_signal
            self._logger.debug(
                "Added frame index=%d value=%.3f baseline=%.3f peak_signal=%s",
                self._frame_count,
                value,
                self._baseline,
                str(peak_signal),
            )
            return frame

    def _update_baseline_locked(self) -> None:
        if not self._frames:
            self._baseline = 0.0
            return
        # 简化实现：最近 N 帧（最多 60 帧）的平均值
        window_size = min(len(self._frames), settings.fps)
        recent_values = [f.value for f in list(self._frames)[-window_size:]]
        self._baseline = sum(recent_values) / window_size

    # 读操作（线程安全快照）
    def get_status_snapshot(self) -> Tuple[SystemStatus, int, float, Optional[int], int, float]:
        with self._lock:
            snapshot = (
                self._status,
                self._frame_count,
                self._current_value,
                self._peak_signal,
                len(self._frames),
                self._baseline,
            )
        self._logger.debug(
            "Status snapshot status=%s frame_count=%d current=%.3f peak_signal=%s buffer_size=%d baseline=%.3f",
            snapshot[0],
            snapshot[1],
            snapshot[2],
            str(snapshot[3]),
            snapshot[4],
            snapshot[5],
        )
        return snapshot

    def get_series(self, count: int) -> List[Frame]:
        with self._lock:
            frames = list(self._frames)
        if count >= len(frames):
            return frames
        return frames[-count:]

    # 状态控制
    def set_status(self, status: SystemStatus) -> None:
        with self._lock:
            self._status = status
        self._logger.info("System status changed to %s", status.value)

    def get_status(self) -> SystemStatus:
        with self._lock:
            return self._status

    def reset(self) -> None:
        with self._lock:
            self._frames.clear()
            self._frame_count = 0
            self._current_value = 0.0
            self._baseline = 0.0
            self._peak_signal = None
            self._last_peak_signal = None
            # 重置ROI配置状态
            self._roi_config = RoiConfig(x1=0, y1=0, x2=200, y2=150)
            self._roi_configured = False
        self._logger.warning("Data store has been reset")

    def get_last_peak_signal(self) -> Optional[int]:
        with self._lock:
            return self._last_peak_signal

    # ROI配置操作
    def set_roi_config(self, roi_config: RoiConfig) -> None:
        """设置ROI配置"""
        with self._lock:
            if roi_config.validate_coordinates():
                self._roi_config = roi_config
                self._roi_configured = True  # 标记为用户已配置
                self._logger.info(
                    "ROI config updated: (%d,%d) -> (%d,%d), size: %dx%d, center: (%d,%d)",
                    roi_config.x1, roi_config.y1, roi_config.x2, roi_config.y2,
                    roi_config.width, roi_config.height, roi_config.center_x, roi_config.center_y
                )
            else:
                self._logger.error("Invalid ROI config: coordinates validation failed")
                raise ValueError("Invalid ROI coordinates")

    def get_roi_config(self) -> RoiConfig:
        """获取ROI配置"""
        with self._lock:
            return self._roi_config

    def is_roi_configured(self) -> bool:
        """检查ROI是否已由用户配置"""
        with self._lock:
            return self._roi_configured

    def get_roi_status(self) -> Tuple[bool, RoiConfig]:
        """获取ROI配置状态和配置"""
        with self._lock:
            return self._roi_configured, self._roi_config

    def add_enhanced_peak(
        self,
        peak_signal: Optional[int],
        peak_color: Optional[str],
        peak_confidence: float,
        threshold: float,
        in_peak_region: bool,
        frame_count: int
    ) -> None:
        """添加增强波峰检测信息"""
        with self._lock:
            self._peak_signal = peak_signal
            if peak_signal == 1:
                self._last_peak_signal = peak_signal
            elif peak_signal is None and self._last_peak_signal == 1:
                self._last_peak_signal = None

            self._enhanced_peak_color = peak_color
            self._enhanced_peak_confidence = peak_confidence
            self._enhanced_peak_threshold = threshold
            self._enhanced_in_peak_region = in_peak_region
            self._enhanced_peak_frame_count = frame_count

    def get_enhanced_peak_status(self) -> Tuple[Optional[str], float, float, bool, int]:
        """获取增强波峰检测状态"""
        with self._lock:
            return (
                self._enhanced_peak_color,
                self._enhanced_peak_confidence,
                self._enhanced_peak_threshold,
                self._enhanced_in_peak_region,
                self._enhanced_peak_frame_count
            )

    def get_enhanced_status_snapshot(self) -> Tuple[
        int, float, float, Optional[int], Optional[int], float,
        Optional[str], float, float, bool, int, bool, RoiConfig
    ]:
        """获取包含增强波峰信息的状态快照"""
        with self._lock:
            return (
                self._frame_count,
                self._current_value,
                self._baseline,
                self._peak_signal,
                self._last_peak_signal,
                float(self._status.value),
                self._enhanced_peak_color,
                self._enhanced_peak_confidence,
                self._enhanced_peak_threshold,
                self._enhanced_in_peak_region,
                self._enhanced_peak_frame_count,
                self._roi_configured,
                self._roi_config
            )

    # ROI历史数据操作
    def add_roi_frame(
        self,
        gray_value: float,
        roi_config: RoiConfig,
        frame_count: int,
        capture_duration: float = 0.5,
        timestamp: Optional[datetime] = None,
    ) -> RoiFrame:
        """添加ROI截图帧数据"""
        if timestamp is None:
            timestamp = datetime.utcnow()

        with self._lock:
            self._roi_frame_count += 1
            roi_frame = RoiFrame(
                index=self._roi_frame_count,
                timestamp=timestamp,
                gray_value=gray_value,
                roi_config=roi_config,
                frame_count=frame_count,
                capture_duration=capture_duration
            )
            self._roi_frames.append(roi_frame)

            # 减少日志频率 - 每50帧记录一次，并改为debug级别
            if self._roi_frame_count % 50 == 0:
                self._logger.debug(
                    "Added ROI frame index=%d gray_value=%.2f frame_count=%d buffer_size=%d",
                    self._roi_frame_count,
                    gray_value,
                    frame_count,
                    len(self._roi_frames)
                )

            return roi_frame

    def get_roi_series(self, count: int) -> List[RoiFrame]:
        """获取最近N个ROI帧数据"""
        with self._lock:
            roi_frames = list(self._roi_frames)

        if count >= len(roi_frames):
            return roi_frames
        return roi_frames[-count:]

    def get_roi_status_snapshot(self) -> Tuple[int, int, float, int]:
        """获取ROI数据状态快照"""
        with self._lock:
            return (
                self._roi_frame_count,
                len(self._roi_frames),
                self._roi_frames[-1].gray_value if self._roi_frames else 0.0,
                self._roi_frames[-1].frame_count if self._roi_frames else 0
            )

    def get_roi_frame_rate_info(self) -> Tuple[float, int]:
        """获取ROI帧率信息"""
        with self._lock:
            if len(self._roi_frames) < 2:
                return 0.0, len(self._roi_frames)

            # 计算实际ROI帧率
            recent_frames = list(self._roi_frames)[-10:]  # 取最近10帧
            if len(recent_frames) >= 2:
                time_span = (recent_frames[-1].timestamp - recent_frames[0].timestamp).total_seconds()
                if time_span > 0:
                    actual_fps = (len(recent_frames) - 1) / time_span
                else:
                    actual_fps = 0.0
            else:
                actual_fps = 0.0

            return actual_fps, len(self._roi_frames)

    def reset_roi_history(self) -> None:
        """重置ROI历史数据"""
        with self._lock:
            self._roi_frames.clear()
            self._roi_frame_count = 0
        self._logger.warning("ROI history has been reset")


# 单例数据存储
data_store = DataStore(buffer_size=settings.buffer_size)
