from typing import List, Union

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """
    全局应用配置，支持从环境变量覆盖默认值。
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


settings = AppConfig()

