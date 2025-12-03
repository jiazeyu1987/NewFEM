from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

_LOGGING_INITIALIZED = False


class _SuppressRealtimeNoDataFilter(logging.Filter):
    """Filter out noisy realtime no-data log messages."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[name-defined]
        message = record.getMessage()
        return (
            "Realtime data requested but no frames available - returning empty response"
            not in message
        )


def init_logging() -> None:
    """
    初始化全局日志配置：
    - 日志目录: 项目根目录下 logs/
    - 日志文件: newfem_YYYYMMDD_HHMMSS.log
    - 级别: DEBUG (文件), INFO (控制台)
    """
    global _LOGGING_INITIALIZED
    if _LOGGING_INITIALIZED:
        return

    base_dir = Path(__file__).resolve().parent.parent
    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"newfem_{timestamp}.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    suppress_filter = _SuppressRealtimeNoDataFilter()
    file_handler.addFilter(suppress_filter)
    console_handler.addFilter(suppress_filter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    _LOGGING_INITIALIZED = True
