"""
数据广播服务 - 将实时数据推送给所有Socket客户端
与DataProcessor集成，提供高性能的数据分发
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from threading import Thread, Lock

from .socket_server import socket_server, SocketMessage


logger = logging.getLogger(__name__)


class DataBroadcaster:
    """数据广播服务"""

    def __init__(self):
        self.running = False
        self.thread: Optional[Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.lock = Lock()

        # 广播配置
        self.broadcast_interval = 1.0 / 60  # 60 FPS
        self.last_broadcast_time = 0
        self.message_sequence = 0

        # 数据缓存
        self._latest_data: Optional[Dict[str, Any]] = None
        self._system_status: Optional[Dict[str, Any]] = None

        logger.info("DataBroadcaster initialized")

    def update_realtime_data(self, data: Dict[str, Any]):
        """更新实时数据"""
        with self.lock:
            self._latest_data = data

    def update_system_status(self, status: Dict[str, Any]):
        """更新系统状态"""
        with self.lock:
            self._system_status = status

    async def _broadcast_loop(self):
        """广播循环"""
        while self.running:
            try:
                current_time = time.time()

                # 检查是否需要广播
                if current_time - self.last_broadcast_time >= self.broadcast_interval:
                    await self._process_broadcasts()
                    self.last_broadcast_time = current_time

                await asyncio.sleep(0.001)  # 1ms resolution

            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")
                await asyncio.sleep(0.1)  # Error recovery delay

    async def _process_broadcasts(self):
        """处理所有广播"""
        try:
            # 广播实时数据
            latest_data = None
            system_status = None

            with self.lock:
                if self._latest_data:
                    latest_data = self._latest_data.copy()
                if self._system_status:
                    system_status = self._system_status.copy()

            # 广播实时数据
            if latest_data:
                await self._broadcast_realtime_data(latest_data)

            # 广播系统状态（频率较低）
            if system_status and int(self.message_sequence) % 60 == 0:  # 每秒一次
                await self._broadcast_system_status(system_status)

        except Exception as e:
            logger.error(f"Error processing broadcasts: {e}")

    async def _broadcast_realtime_data(self, data: Dict[str, Any]):
        """广播实时数据"""
        try:
            # 添加广播时间戳和序列号
            broadcast_data = {
                **data,
                "broadcast_timestamp": time.time(),
                "sequence": self.message_sequence
            }

            message = SocketMessage(
                message_type="realtime_data",
                data=broadcast_data,
                sequence=self.message_sequence
            )

            self.message_sequence += 1

            # 只发送给订阅了realtime_data的客户端
            await socket_server.broadcast_message(
                message,
                lambda c: c.is_authenticated and "realtime_data" in c.subscriptions
            )

        except Exception as e:
            logger.error(f"Error broadcasting realtime data: {e}")

    async def _broadcast_system_status(self, status: Dict[str, Any]):
        """广播系统状态"""
        try:
            message = SocketMessage(
                message_type="system_status",
                data=status
            )

            await socket_server.broadcast_message(
                message,
                lambda c: c.is_authenticated and "system_status" in c.subscriptions
            )

        except Exception as e:
            logger.error(f"Error broadcasting system status: {e}")

    async def broadcast_peak_detection(self, peak_data: Dict[str, Any]):
        """广播波峰检测结果"""
        try:
            message = SocketMessage(
                message_type="peak_detected",
                data=peak_data
            )

            await socket_server.broadcast_message(
                message,
                lambda c: c.is_authenticated and "peak_detected" in c.subscriptions
            )

        except Exception as e:
            logger.error(f"Error broadcasting peak detection: {e}")

    async def broadcast_roi_capture(self, roi_data: Dict[str, Any]):
        """广播ROI截图数据"""
        try:
            message = SocketMessage(
                message_type="roi_captured",
                data=roi_data
            )

            await socket_server.broadcast_message(
                message,
                lambda c: c.is_authenticated and "roi_captured" in c.subscriptions
            )

        except Exception as e:
            logger.error(f"Error broadcasting ROI capture: {e}")

    async def send_control_response(self, client_id: str, response: Dict[str, Any]):
        """发送控制命令响应"""
        try:
            message = SocketMessage(
                message_type="control_response",
                data=response
            )

            # 发送给指定客户端
            if client_id in socket_server.clients:
                client = socket_server.clients[client_id]
                await client.send_message(message)
            else:
                logger.warning(f"Client {client_id} not found for control response")

        except Exception as e:
            logger.error(f"Error sending control response: {e}")

    def _run_broadcaster(self):
        """运行广播器（在线程中）"""
        try:
            # 创建新的事件循环
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            self.running = True
            logger.info("DataBroadcaster started")

            # 运行广播循环
            self.loop.run_until_complete(self._broadcast_loop())

        except Exception as e:
            logger.error(f"Error running data broadcaster: {e}")
        finally:
            self.running = False
            logger.info("DataBroadcaster stopped")

    def start(self):
        """启动数据广播服务"""
        if self.running:
            logger.warning("DataBroadcaster is already running")
            return

        self.thread = Thread(target=self._run_broadcaster, daemon=True)
        self.thread.start()

        # 等待启动
        time.sleep(0.5)
        if self.running:
            logger.info("DataBroadcaster started successfully")
        else:
            logger.error("Failed to start DataBroadcaster")

    def stop(self):
        """停止数据广播服务"""
        if not self.running:
            logger.warning("DataBroadcaster is not running")
            return

        logger.info("Stopping DataBroadcaster...")
        self.running = False

        # 停止事件循环
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)

        # 等待线程结束
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

        logger.info("DataBroadcaster stopped")

    def get_status(self) -> Dict[str, Any]:
        """获取广播器状态"""
        with self.lock:
            return {
                "running": self.running,
                "broadcast_interval": self.broadcast_interval,
                "message_sequence": self.message_sequence,
                "last_broadcast_time": self.last_broadcast_time,
                "has_latest_data": self._latest_data is not None,
                "has_system_status": self._system_status is not None
            }


# 全局数据广播器实例
data_broadcaster = DataBroadcaster()