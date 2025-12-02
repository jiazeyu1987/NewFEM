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

    # 启动数据处理系统
    processor.start()

    # 启动 FastAPI 服务（阻塞）
    run_fastapi()


if __name__ == "__main__":
    main()
