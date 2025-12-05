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
from .enhanced_peak_detector import EnhancedPeakDetector, PeakDetectionConfig
from .roi_capture import roi_capture_service


class DataProcessor:
    """
    增强型数据处理器，集成ROI灰度值和三参数波峰检测算法。
    支持模拟信号和真实ROI数据的处理。
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._frame_count = 0

        # 初始化增强波峰检测器
        peak_config = PeakDetectionConfig(
            threshold=settings.peak_threshold,
            margin_frames=settings.peak_margin_frames,
            difference_threshold=settings.peak_difference_threshold,
            min_region_length=settings.peak_min_region_length
        )
        self._enhanced_detector = EnhancedPeakDetector(peak_config)

        self._logger.info("DataProcessor initialized with enhanced peak detection")
        self._logger.info(f"Peak detection config: threshold={peak_config.threshold}, "
                         f"margin_frames={peak_config.margin_frames}, "
                         f"difference_threshold={peak_config.difference_threshold}")

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
        self._logger.info("🛑 DataProcessor stop requested - stop_event set, status set to STOPPED")

        # 等待线程真正停止
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)  # 最多等待2秒
            if self._thread.is_alive():
                self._logger.warning("⚠️ DataProcessor thread did not stop within timeout")
            else:
                self._logger.info("✅ DataProcessor thread stopped successfully")

    def _run(self) -> None:
        interval = 1.0 / float(settings.fps)
        base_value = 120.0
        t = 0.0

        while not self._stop_event.is_set():
            start_time = time.perf_counter()
            self._frame_count += 1

            # 获取ROI配置状态
            roi_configured = data_store.is_roi_configured()
            roi_config = data_store.get_roi_config()

            # 根据ROI配置状态选择数据源
            if roi_configured:
                # 使用真实ROI数据
                roi_data = roi_capture_service.capture_roi(roi_config)
                if roi_data and roi_data.gray_value > 0:
                    signal_value = roi_data.gray_value
                    data_source = "ROI"
                else:
                    # ROI截图失败，回退到模拟数据
                    signal_value = base_value + 10.0 * math.sin(2 * math.pi * 0.5 * t)
                    data_source = "Fallback"
            else:
                # 使用模拟数据
                signal_value = base_value + 10.0 * math.sin(2 * math.pi * 0.5 * t)
                data_source = "Simulated"

            # 使用增强波峰检测器处理数据
            if roi_configured:
                # ROI配置时使用增强检测
                peak_result = self._enhanced_detector.process_frame(signal_value, self._frame_count)
                peak_signal = peak_result['peak_signal']

                # 存储增强波峰信息到DataStore
                data_store.add_enhanced_peak(
                    peak_signal=peak_signal,
                    peak_color=peak_result.get('peak_color'),
                    peak_confidence=peak_result.get('peak_confidence', 0.0),
                    threshold=peak_result.get('threshold', 0.0),
                    in_peak_region=peak_result.get('in_peak_region', False),
                    frame_count=self._frame_count
                )

                if peak_signal == 1:
                    peak_color = peak_result.get('peak_color', 'unknown')
                    self._logger.info(
                        f"🎯 ENHANCED PEAK DETECTED! source={data_source} "
                        f"value={signal_value:.1f} color={peak_color} "
                        f"frame={self._frame_count}"
                    )
            else:
                # ROI未配置时使用简单检测（向后兼容）
                _, _, _, _, _, baseline = data_store.get_status_snapshot()
                threshold = 8.0
                peak_signal: Optional[int] = None
                if signal_value - baseline > threshold:
                    peak_signal = 1

                # 清除增强波峰信息
                data_store.add_enhanced_peak(
                    peak_signal=peak_signal,
                    peak_color=None,
                    peak_confidence=0.0,
                    threshold=0.0,
                    in_peak_region=False,
                    frame_count=self._frame_count
                )

            now = datetime.utcnow()
            data_store.add_frame(value=signal_value, timestamp=now, peak_signal=peak_signal)

            # 高频信号生成日志改为DEBUG级别
            self._logger.debug(
                f"📊 Signal Generated: source={data_source} value={signal_value:.1f} "
                f"frame={self._frame_count} peak_signal={peak_signal}"
            )

            t += interval
            elapsed = time.perf_counter() - start_time
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
        self._logger.info("DataProcessor thread loop exited")

    def reload_peak_detection_config(self) -> bool:
        """
        从JSON配置文件重新加载波峰检测配置

        Returns:
            bool: 重新加载是否成功
        """
        try:
            # 重新加载settings对象（这会从JSON文件读取最新配置）
            from ..config import AppConfig
            new_settings = AppConfig.reload_from_json()

            if new_settings:
                # 创建新的波峰检测配置
                new_peak_config = PeakDetectionConfig(
                    threshold=new_settings.peak_threshold,
                    margin_frames=new_settings.peak_margin_frames,
                    difference_threshold=new_settings.peak_difference_threshold,
                    min_region_length=new_settings.peak_min_region_length
                )

                # 更新增强波峰检测器的配置
                old_config = self._enhanced_detector._config
                self._enhanced_detector.update_config(new_peak_config)

                self._logger.info(
                    "Peak detection config reloaded from JSON: "
                    "threshold %.1f->%.1f, margin_frames %d->%d, "
                    "difference_threshold %.1f->%.1f, min_region_length %d->%d",
                    old_config.threshold, new_peak_config.threshold,
                    old_config.margin_frames, new_peak_config.margin_frames,
                    old_config.difference_threshold, new_peak_config.difference_threshold,
                    old_config.min_region_length, new_peak_config.min_region_length
                )
                return True
            else:
                self._logger.error("Failed to reload peak detection config from JSON")
                return False

        except Exception as e:
            self._logger.error("Error reloading peak detection config: %s", str(e))
            return False


processor = DataProcessor()
