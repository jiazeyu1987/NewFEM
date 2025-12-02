import uvicorn

from app.api.routes import app
from app.config import settings
from app.core.processor import processor
from app.logging_config import init_logging


def run_fastapi() -> None:
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.api_port,
        log_level="info",
    )


def main() -> None:
    # 初始化日志
    init_logging()

    import logging

    logger = logging.getLogger("newfem.run")
    logger.info("Starting NewFEM backend with settings: %s", settings.model_dump())

    # 数据处理系统将在前端点击【开始分析】时启动
    # processor.start()  # 移除自动启动，改为手动控制

    # 启动 FastAPI 服务（阻塞）
    run_fastapi()


if __name__ == "__main__":
    main()
