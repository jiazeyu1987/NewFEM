from __future__ import annotations

import math
import threading
import time
from datetime import datetime
from typing import Optional

import logging

from ..config import settings
from ..models import SystemStatus
from .data_store import data_store


class DataProcessor:
    """
    模拟 60 FPS 数据生成和简单波峰检测的后台线程。
    实际算法可根据需求进一步替换。
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            self._logger.info("DataProcessor already running, start() ignored")
            return
        self._stop_event.clear()
        data_store.set_status(SystemStatus.RUNNING)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._logger.info("DataProcessor thread started with fps=%d", settings.fps)

    def stop(self) -> None:
        self._stop_event.set()
        data_store.set_status(SystemStatus.STOPPED)
        self._logger.info("DataProcessor stop requested")

    def _run(self) -> None:
        interval = 1.0 / float(settings.fps)
        base_value = 120.0
        t = 0.0

        while not self._stop_event.is_set():
            start_time = time.perf_counter()

            # 简单模拟一个带噪声的波形信号
            # 例如基于正弦波 + 随机扰动，并在阈值上方触发 peak_signal
            signal = base_value + 10.0 * math.sin(2 * math.pi * 0.5 * t)

            # 简单峰值检测：当前值相对基线超过阈值即认为有峰
            # 注意这里先用前一轮的 baseline 进行判断，简化实现
            _, _, _, _, _, baseline = data_store.get_status_snapshot()
            threshold = 8.0
            peak_signal: Optional[int] = None
            if signal - baseline > threshold:
                peak_signal = 1
                self._logger.info(
                    "🔴 PEAK DETECTED! signal=%.3f baseline=%.3f threshold=%.3f difference=%.3f",
                    signal,
                    baseline,
                    threshold,
                    signal - baseline
                )

            now = datetime.utcnow()
            data_store.add_frame(value=signal, timestamp=now, peak_signal=peak_signal)

            # 高频信号生成日志改为DEBUG级别，避免控制台噪音
            self._logger.debug(
                "📊 Signal Generated: t=%.3f value=%.3f baseline=%.3f peak_signal=%s",
                t,
                signal,
                baseline,
                str(peak_signal) if peak_signal is not None else "null"
            )

            t += interval
            elapsed = time.perf_counter() - start_time
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
        self._logger.info("DataProcessor thread loop exited")


processor = DataProcessor()
