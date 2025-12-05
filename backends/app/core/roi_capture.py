"""
ROI截图服务模块
提供屏幕截图和ROI区域截取功能
"""

import base64
import io
import logging
import time
from typing import Optional, Tuple

# 启用PIL导入
from PIL import Image, ImageGrab

from ..models import RoiConfig, RoiData


class RoiCaptureService:
    """ROI截图服务类"""

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        # 从配置获取ROI帧率（配置现在会从JSON文件加载）
        from ..config import settings
        self._settings = settings
        self._frame_rate = settings.roi_frame_rate
        self._cache_interval = settings.roi_update_interval  # 缓存间隔

        # ROI截图缓存机制
        self._last_capture_time = 0.0
        self._cached_roi_data: Optional[RoiData] = None
        self._last_roi_config: Optional[RoiConfig] = None

        self._logger.info("ROI Capture Service initialized with JSON config: frame_rate=%d, update_interval=%.1f",
                         self._frame_rate, self._cache_interval)

    def clear_cache(self):
        """
        清除ROI截图缓存，强制下次截图时重新捕获
        """
        self._cached_roi_data = None
        self._last_roi_config = None
        self._last_capture_time = 0.0
        self._logger.debug("ROI cache cleared - next capture will be forced")

    def capture_screen(self) -> Optional[Image.Image]:
        """
        截取整个屏幕

        Returns:
            PIL.Image: 屏幕截图，失败返回None
        """
        try:
            screenshot = ImageGrab.grab()
            self._logger.debug("Screen captured successfully, size: %s", screenshot.size)
            return screenshot
        except Exception as e:
            self._logger.error("Failed to capture screen: %s", str(e))
            return None

    def capture_roi(self, roi_config: RoiConfig) -> Optional[RoiData]:
        """
        截取指定ROI区域（带缓存机制）

        Args:
            roi_config: ROI配置

        Returns:
            RoiData: ROI数据，失败返回None
        """
        try:
            # 验证ROI坐标
            if not roi_config.validate_coordinates():
                self._logger.error("Invalid ROI coordinates: %s", roi_config)
                return None

            current_time = time.time()

            # 简化的缓存机制：只基于时间间隔和配置变化
            time_valid = current_time - self._last_capture_time < self._cache_interval
            config_unchanged = (self._last_roi_config is not None and
                               self._roi_config_changed(roi_config, self._last_roi_config) == False)

            # 只有在缓存有效且配置未变化时才使用缓存
            if (self._cached_roi_data is not None and time_valid and config_unchanged):
                self._logger.debug(f"Using cached ROI data (age: {current_time - self._last_capture_time:.3f}s)")
                return self._cached_roi_data
            else:
                self._logger.debug(f"Forcing new ROI capture - time_valid: {time_valid}, config_unchanged: {config_unchanged}")

            # 执行真实的截图操作
            roi_data = self._capture_roi_internal(roi_config)

            # 更新缓存和状态
            if roi_data is not None:
                self._cached_roi_data = roi_data
                self._last_roi_config = roi_config
                self._last_capture_time = current_time
                self._logger.debug("ROI captured successfully (gray_value=%.2f)", roi_data.gray_value)

                # 集成历史存储 - 保存ROI帧到DataStore
                try:
                    from ..core.data_store import data_store
                    # 获取当前主信号帧数
                    _, main_frame_count, _, _, _, _ = data_store.get_status_snapshot()

                    # 添加ROI历史帧
                    roi_frame = data_store.add_roi_frame(
                        gray_value=roi_data.gray_value,
                        roi_config=roi_config,
                        frame_count=main_frame_count,
                        capture_duration=self._cache_interval
                    )

                    # 减少日志频率 - 每50帧记录一次，并改为debug级别
                    if roi_frame.index % 50 == 0:
                        self._logger.debug("ROI frame added to history: index=%d, gray_value=%.2f, main_frame=%d",
                                           roi_frame.index, roi_frame.gray_value, main_frame_count)

                except Exception as e:
                    self._logger.error("Failed to add ROI frame to history: %s", str(e))

            return roi_data

        except Exception as e:
            self._logger.error("Failed to capture ROI: %s", str(e))
            return None

    def _roi_config_changed(self, current: RoiConfig, cached: RoiConfig) -> bool:
        """检查ROI配置是否发生变化"""
        return (current.x1 != cached.x1 or current.y1 != cached.y1 or
                current.x2 != cached.x2 or current.y2 != cached.y2)

    def _capture_roi_internal(self, roi_config: RoiConfig) -> Optional[RoiData]:
        """执行实际的ROI截图操作"""
        # 首先截取整个屏幕
        screen = self.capture_screen()
        if screen is None:
            self._logger.error("Failed to capture screen for ROI")
            return None

        # 检查ROI是否在屏幕范围内
        screen_width, screen_height = screen.size
        if (roi_config.x2 > screen_width or roi_config.y2 > screen_height or
            roi_config.x1 < 0 or roi_config.y1 < 0):
            self._logger.warning(
                "ROI coordinates exceed screen bounds. Screen: %dx%d, ROI: (%d,%d)->(%d,%d)",
                screen_width, screen_height,
                roi_config.x1, roi_config.y1, roi_config.x2, roi_config.y2
            )
            # 自动调整到屏幕范围内
            x1 = max(0, min(roi_config.x1, screen_width - 1))
            y1 = max(0, min(roi_config.y1, screen_height - 1))
            x2 = max(x1 + 1, min(roi_config.x2, screen_width))
            y2 = max(y1 + 1, min(roi_config.y2, screen_height))
        else:
            x1, y1, x2, y2 = roi_config.x1, roi_config.y1, roi_config.x2, roi_config.y2

        # 截取ROI区域
        roi_image = screen.crop((x1, y1, x2, y2))

        # 计算ROI平均灰度值
        gray_roi = roi_image.convert('L')
        # 简化计算：使用PIL的直方图来计算平均值
        histogram = gray_roi.histogram()
        total_pixels = roi_config.width * roi_config.height
        total_sum = sum(i * count for i, count in enumerate(histogram))
        average_gray = float(total_sum / total_pixels) if total_pixels > 0 else 0.0

        # 调整ROI图像大小到标准尺寸（200x150）
        try:
            roi_resized = roi_image.resize((200, 150), Image.Resampling.LANCZOS)
        except AttributeError:
            # 兼容旧版本PIL
            roi_resized = roi_image.resize((200, 150), Image.LANCZOS)

        # 转换为base64
        buffer = io.BytesIO()
        roi_resized.save(buffer, format='PNG')
        roi_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        roi_data = RoiData(
            width=roi_config.width,
            height=roi_config.height,
            pixels=f"data:image/png;base64,{roi_base64}",
            gray_value=average_gray,
            format="base64"
        )

        self._logger.debug(
            "ROI captured successfully: size=%dx%d, gray_value=%.2f, base64_length=%d",
            roi_config.width, roi_config.height, average_gray, len(roi_base64)
        )

        return roi_data

    def get_roi_frame_rate(self) -> int:
        """获取当前ROI帧率设置"""
        return self._frame_rate

    def set_roi_frame_rate(self, frame_rate: int) -> bool:
        """
        动态设置ROI帧率

        Args:
            frame_rate: 新的帧率 (1-60 FPS)

        Returns:
            bool: 设置是否成功
        """
        if 1 <= frame_rate <= 60:
            self._frame_rate = frame_rate
            self._cache_interval = 1.0 / frame_rate
            self._logger.info("ROI frame rate updated to %d FPS, cache interval: %.3f seconds",
                              frame_rate, self._cache_interval)

            # 保存到JSON配置文件
            try:
                from .config_manager import get_config_manager
                config_manager = get_config_manager()

                # 更新ROI帧率配置
                updates = {"frame_rate": frame_rate}
                success = config_manager.update_config(updates, section="roi_capture")
                if success:
                    config_manager.save_config()
                    self._logger.info("ROI frame rate %d saved to JSON configuration file", frame_rate)
                else:
                    self._logger.warning("Failed to save ROI frame rate to JSON configuration file")

            except Exception as e:
                self._logger.error("Error saving ROI frame rate to JSON: %s", str(e))

            return True
        else:
            self._logger.error("Invalid frame rate: %d (must be 1-60)", frame_rate)
            return False

    def get_screen_resolution(self) -> Tuple[int, int]:
        """
        获取屏幕分辨率

        Returns:
            Tuple[int, int]: (宽度, 高度)
        """
        try:
            screen = self.capture_screen()
            if screen:
                return screen.size
            return (1920, 1080)  # 默认分辨率
        except Exception:
            return (1920, 1080)  # 默认分辨率

    def validate_roi_coordinates(self, roi_config: RoiConfig) -> Tuple[bool, str]:
        """
        验证ROI坐标是否有效

        Args:
            roi_config: ROI配置

        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        try:
            # 基本坐标验证
            if not roi_config.validate_coordinates():
                return False, "Invalid coordinates: x1 must be < x2 and y1 must be < y2"

            # 获取屏幕分辨率
            screen_width, screen_height = self.get_screen_resolution()

            # 检查坐标范围
            if roi_config.x1 < 0 or roi_config.y1 < 0:
                return False, "Coordinates cannot be negative"

            if roi_config.x2 > screen_width or roi_config.y2 > screen_height:
                return False, f"Coordinates exceed screen resolution ({screen_width}x{screen_height})"

            # 检查ROI大小
            if roi_config.width < 10 or roi_config.height < 10:
                return False, "ROI size too small (minimum 10x10)"

            if roi_config.width > 1000 or roi_config.height > 1000:
                return False, "ROI size too large (maximum 1000x1000)"

            return True, "Valid ROI coordinates"

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def reload_config(self) -> bool:
        """
        从JSON配置文件重新加载ROI配置

        Returns:
            bool: 重新加载是否成功
        """
        try:
            # 重新加载settings对象（这会从JSON文件读取最新配置）
            from ..config import AppConfig
            new_settings = AppConfig.reload_from_json()

            if new_settings:
                # 更新本地配置
                old_frame_rate = self._frame_rate
                old_interval = self._cache_interval

                self._settings = new_settings
                self._frame_rate = new_settings.roi_frame_rate
                self._cache_interval = new_settings.roi_update_interval

                self._logger.info(
                    "ROI config reloaded from JSON: frame_rate %d->%d, interval %.1f->%.1f",
                    old_frame_rate, self._frame_rate, old_interval, self._cache_interval
                )
                return True
            else:
                self._logger.error("Failed to reload ROI config from JSON")
                return False

        except Exception as e:
            self._logger.error("Error reloading ROI config: %s", str(e))
            return False


# 单例ROI截图服务
roi_capture_service = RoiCaptureService()