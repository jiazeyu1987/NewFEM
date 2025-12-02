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

    # 安全配置
    password: str = "31415"
    enable_cors: bool = True
    allowed_origins: Union[List[AnyHttpUrl], List[str]] = ["*"]

    class Config:
        env_prefix = "NEWFEM_"
        case_sensitive = False


settings = AppConfig()

