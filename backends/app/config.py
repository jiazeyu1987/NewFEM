from typing import List, Union, Optional
import logging
from pathlib import Path

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class AppConfig(BaseSettings):
    """
    全局应用配置，支持从JSON文件和环境变量覆盖默认值。
    优先级：环境变量 > JSON配置文件 > 默认值
    """

    # 服务器配置
    host: str = "0.0.0.0"
    api_port: int = 8421
    socket_port: int = 30415
    max_clients: int = 10

    # 数据配置
    fps: int = 60
    buffer_size: int = 100
    max_frame_count: int = 10000

    # ROI配置
    roi_frame_rate: int = 2  # ROI截图和识别的频率 (FPS)
    roi_update_interval: float = 0.5  # ROI更新间隔 (秒)

    # 波峰检测配置
    peak_threshold: float = 105.0          # 绝对阈值：ROI灰度值超过此值进入波峰区域
    peak_margin_frames: int = 5           # 边界扩展帧数：波峰区域前后扩展的帧数
    peak_difference_threshold: float = 2.1 # 颜色分类阈值：用于绿色/红色波峰分类
    peak_min_region_length: int = 3       # 最小波峰区域长度：小于此值的区域被忽略

    # 安全配置
    password: str = "31415"
    enable_cors: bool = True
    allowed_origins: Union[List[AnyHttpUrl], List[str]] = ["*"]

    # 日志配置
    log_level: str = "INFO"  # 日志级别: DEBUG, INFO, WARNING, ERROR

    class Config:
        env_prefix = "NEWFEM_"
        case_sensitive = False

    def __init__(self, **kwargs):
        """
        初始化配置，从JSON文件加载基础配置，然后应用环境变量覆盖
        """
        # 先尝试从JSON文件加载配置
        json_config = self._load_json_config()

        # 将JSON配置转换为kwargs，用于BaseSettings初始化
        if json_config:
            json_kwargs = self._convert_json_to_kwargs(json_config)
            # 环境变量具有最高优先级，所以JSON配置在前面，kwargs在后面
            merged_kwargs = {**json_kwargs, **kwargs}
        else:
            merged_kwargs = kwargs

        # 调用父类初始化
        super().__init__(**merged_kwargs)

        logger.info("配置初始化完成")
        logger.debug(f"服务器配置 - host: {self.host}, api_port: {self.api_port}")
        logger.debug(f"数据配置 - fps: {self.fps}, buffer_size: {self.buffer_size}")
        logger.debug(f"ROI配置 - frame_rate: {self.roi_frame_rate}, update_interval: {self.roi_update_interval}")
        logger.debug(f"波峰检测配置 - threshold: {self.peak_threshold}, margin_frames: {self.peak_margin_frames}")

    def _load_json_config(self) -> Optional[dict]:
        """
        从JSON文件加载配置

        Returns:
            配置字典，如果加载失败返回None
        """
        try:
            from .core.config_manager import get_config_manager
            config_manager = get_config_manager()
            return config_manager.get_full_config()
        except Exception as e:
            logger.warning(f"无法从JSON文件加载配置: {e}")
            return None

    def _convert_json_to_kwargs(self, json_config: dict) -> dict:
        """
        将JSON配置转换为BaseSettings可接受的kwargs格式

        Args:
            json_config: JSON配置字典

        Returns:
            转换后的kwargs字典
        """
        kwargs = {}

        # 服务器配置
        if "server" in json_config:
            server_config = json_config["server"]
            if "host" in server_config:
                kwargs["host"] = server_config["host"]
            if "api_port" in server_config:
                kwargs["api_port"] = server_config["api_port"]
            if "socket_port" in server_config:
                kwargs["socket_port"] = server_config["socket_port"]
            if "max_clients" in server_config:
                kwargs["max_clients"] = server_config["max_clients"]
            if "enable_cors" in server_config:
                kwargs["enable_cors"] = server_config["enable_cors"]
            if "allowed_origins" in server_config:
                kwargs["allowed_origins"] = server_config["allowed_origins"]

        # 数据处理配置
        if "data_processing" in json_config:
            data_config = json_config["data_processing"]
            if "fps" in data_config:
                kwargs["fps"] = data_config["fps"]
            if "buffer_size" in data_config:
                kwargs["buffer_size"] = data_config["buffer_size"]
            if "max_frame_count" in data_config:
                kwargs["max_frame_count"] = data_config["max_frame_count"]

        # ROI配置
        if "roi_capture" in json_config:
            roi_config = json_config["roi_capture"]
            if "frame_rate" in roi_config:
                kwargs["roi_frame_rate"] = roi_config["frame_rate"]
            if "update_interval" in roi_config:
                kwargs["roi_update_interval"] = roi_config["update_interval"]

        # 波峰检测配置
        if "peak_detection" in json_config:
            peak_config = json_config["peak_detection"]
            if "threshold" in peak_config:
                kwargs["peak_threshold"] = peak_config["threshold"]
            if "margin_frames" in peak_config:
                kwargs["peak_margin_frames"] = peak_config["margin_frames"]
            if "difference_threshold" in peak_config:
                kwargs["peak_difference_threshold"] = peak_config["difference_threshold"]
            if "min_region_length" in peak_config:
                kwargs["peak_min_region_length"] = peak_config["min_region_length"]

        # 安全配置
        if "security" in json_config:
            security_config = json_config["security"]
            if "password" in security_config:
                kwargs["password"] = security_config["password"]

        # 日志配置
        if "logging" in json_config:
            logging_config = json_config["logging"]
            if "level" in logging_config:
                kwargs["log_level"] = logging_config["level"]

        return kwargs

    @classmethod
    def reload_from_json(cls) -> 'AppConfig':
        """
        从JSON文件重新加载配置并返回新的AppConfig实例

        Returns:
            新的AppConfig实例
        """
        try:
            from .core.config_manager import get_config_manager
            config_manager = get_config_manager()
            config_manager.reload_config()

            # 创建新的配置实例
            new_config = cls()
            logger.info("配置已从JSON文件重新加载")
            return new_config

        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")
            # 返回当前配置实例
            return settings


# 全局配置实例
settings = AppConfig()

