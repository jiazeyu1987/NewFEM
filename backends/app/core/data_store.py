from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, List, Optional, Tuple

import logging

from ..config import settings
from ..models import SystemStatus


@dataclass
class Frame:
    index: int
    timestamp: datetime
    value: float


class DataStore:
    """
    内存中的时序数据存储，线程安全。
    """

    def __init__(self, buffer_size: int) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._buffer_size = buffer_size
        self._frames: Deque[Frame] = deque(maxlen=buffer_size)
        self._lock = threading.Lock()

        self._frame_count: int = 0
        self._current_value: float = 0.0
        self._baseline: float = 0.0
        self._peak_signal: Optional[int] = None
        self._last_peak_signal: Optional[int] = None
        self._status: SystemStatus = SystemStatus.STOPPED

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
        self._logger.warning("Data store has been reset")

    def get_last_peak_signal(self) -> Optional[int]:
        with self._lock:
            return self._last_peak_signal


# 单例数据存储
data_store = DataStore(buffer_size=settings.buffer_size)
