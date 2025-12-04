"""
Socket服务器 - 为Python客户端提供实时数据推送和控制接口
支持多客户端连接，与FastAPI并行运行
"""

import asyncio
import json
import logging
import threading
import time
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime

import websockets
from websockets.server import WebSocketServerProtocol

from ..config import settings


logger = logging.getLogger(__name__)


class SocketMessage:
    """Socket消息格式定义"""

    def __init__(self, message_type: str, data: Dict[str, Any],
                 timestamp: Optional[float] = None, sequence: int = 0):
        self.message_type = message_type
        self.data = data
        self.timestamp = timestamp or time.time()
        self.sequence = sequence

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps({
            "type": self.message_type,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "data": self.data
        })

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SocketMessage':
        """从字典创建消息"""
        return cls(
            message_type=data.get("type", "unknown"),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", time.time()),
            sequence=data.get("sequence", 0)
        )


class SocketClient:
    """Socket客户端连接管理"""

    def __init__(self, websocket: WebSocketServerProtocol, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self.connected_at = time.time()
        self.last_ping = time.time()
        self.last_pong = time.time()
        self.is_authenticated = False
        self.subscriptions = set()  # 订阅的消息类型

    async def send_message(self, message: SocketMessage):
        """发送消息给客户端"""
        try:
            await self.websocket.send(message.to_json())
            return True
        except Exception as e:
            logger.error(f"Failed to send message to client {self.client_id}: {e}")
            return False

    async def ping(self):
        """发送心跳"""
        try:
            await self.websocket.send(json.dumps({"type": "ping", "timestamp": time.time()}))
            self.last_ping = time.time()
            return True
        except Exception as e:
            logger.error(f"Failed to ping client {self.client_id}: {e}")
            return False

    def update_pong(self):
        """更新pong时间"""
        self.last_pong = time.time()

    def is_alive(self, timeout: float = 30.0) -> bool:
        """检查客户端是否存活"""
        return (time.time() - self.last_pong) < timeout


class SocketServer:
    """Socket服务器主类"""

    def __init__(self):
        self.host = settings.host
        self.port = settings.socket_port  # 使用配置中的socket_port
        self.max_clients = settings.max_clients
        self.clients: Dict[str, SocketClient] = {}
        self.running = False
        self.server: Optional[Any] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None

        # 消息处理器
        self.message_handlers: Dict[str, Callable] = {}

        # 数据广播回调
        self.data_callbacks: List[Callable] = []

        logger.info(f"SocketServer initialized for {self.host}:{self.port}")

    def register_message_handler(self, message_type: str, handler: Callable):
        """注册消息处理器"""
        self.message_handlers[message_type] = handler
        logger.info(f"Registered message handler for type: {message_type}")

    def register_data_callback(self, callback: Callable):
        """注册数据回调（用于实时数据推送）"""
        self.data_callbacks.append(callback)
        logger.info("Registered data callback")

    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """处理新客户端连接"""
        client_id = f"client_{len(self.clients)}_{int(time.time() * 1000)}"

        # 检查客户端数量限制
        if len(self.clients) >= self.max_clients:
            logger.warning(f"Rejecting client {client_id}: max clients ({self.max_clients}) reached")
            await websocket.close(1013, "Server overloaded")
            return

        # 创建客户端对象
        client = SocketClient(websocket, client_id)
        self.clients[client_id] = client

        logger.info(f"Client connected: {client_id} from {websocket.remote_address}")

        try:
            # 发送连接确认消息
            await client.send_message(SocketMessage(
                message_type="connection_established",
                data={
                    "client_id": client_id,
                    "server_time": time.time(),
                    "max_clients": self.max_clients,
                    "connected_clients": len(self.clients)
                }
            ))

            # 处理客户端消息
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(client, data)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from client {client_id}: {message}")
                    await client.send_message(SocketMessage(
                        message_type="error",
                        data={"message": "Invalid JSON format"}
                    ))
                except Exception as e:
                    logger.error(f"Error handling message from {client_id}: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Error in client handler for {client_id}: {e}")
        finally:
            # 清理客户端
            if client_id in self.clients:
                del self.clients[client_id]
            logger.info(f"Client removed: {client_id}, remaining: {len(self.clients)}")

    async def handle_message(self, client: SocketClient, data: Dict[str, Any]):
        """处理客户端消息"""
        message_type = data.get("type", "unknown")

        # 处理ping/pong
        if message_type == "pong":
            client.update_pong()
            return

        # 处理认证
        if message_type == "auth":
            password = data.get("password", "")
            if password == settings.password:
                client.is_authenticated = True
                await client.send_message(SocketMessage(
                    message_type="auth_success",
                    data={"message": "Authentication successful"}
                ))
                logger.info(f"Client {client.client_id} authenticated successfully")
            else:
                await client.send_message(SocketMessage(
                    message_type="auth_error",
                    data={"message": "Invalid password"}
                ))
                logger.warning(f"Client {client.client_id} authentication failed")
            return

        # 检查认证状态（除了ping/pong/auth）
        if not client.is_authenticated and message_type not in ["ping", "auth"]:
            await client.send_message(SocketMessage(
                message_type="error",
                data={"message": "Authentication required"}
            ))
            return

        # 调用注册的消息处理器
        if message_type in self.message_handlers:
            try:
                await self.message_handlers[message_type](client, data.get("data", {}))
            except Exception as e:
                logger.error(f"Error in message handler for {message_type}: {e}")
                await client.send_message(SocketMessage(
                    message_type="error",
                    data={"message": f"Handler error: {str(e)}"}
                ))
        else:
            logger.warning(f"Unknown message type: {message_type}")
            await client.send_message(SocketMessage(
                message_type="error",
                data={"message": f"Unknown message type: {message_type}"}
            ))

    async def broadcast_message(self, message: SocketMessage,
                                message_filter: Optional[Callable[[SocketClient], bool]] = None):
        """广播消息给所有客户端"""
        if not self.clients:
            return

        disconnected_clients = []

        for client_id, client in self.clients.items():
            try:
                # 应用过滤器
                if message_filter and not message_filter(client):
                    continue

                # 发送消息
                success = await client.send_message(message)
                if not success:
                    disconnected_clients.append(client_id)

            except Exception as e:
                logger.error(f"Error broadcasting to client {client_id}: {e}")
                disconnected_clients.append(client_id)

        # 清理断开的客户端
        for client_id in disconnected_clients:
            if client_id in self.clients:
                del self.clients[client_id]
                logger.info(f"Removed disconnected client during broadcast: {client_id}")

    async def send_realtime_data(self, data: Dict[str, Any]):
        """发送实时数据给所有订阅的客户端"""
        message = SocketMessage(
            message_type="realtime_data",
            data=data,
            sequence=getattr(self, '_message_sequence', 0) + 1
        )
        self._message_sequence = message.sequence

        # 只发送给订阅了realtime_data的客户端
        await self.broadcast_message(message,
                                   lambda c: "realtime_data" in c.subscriptions)

    async def send_system_status(self, status: Dict[str, Any]):
        """发送系统状态给所有客户端"""
        message = SocketMessage(
            message_type="system_status",
            data=status
        )

        await self.broadcast_message(message)

    async def heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            try:
                # 检查客户端存活状态
                dead_clients = []
                for client_id, client in self.clients.items():
                    if not client.is_alive():
                        dead_clients.append(client_id)
                    else:
                        # 发送心跳
                        await client.ping()

                # 清理死客户端
                for client_id in dead_clients:
                    if client_id in self.clients:
                        del self.clients[client_id]
                        logger.info(f"Removed dead client: {client_id}")

                await asyncio.sleep(10)  # 每10秒心跳一次

            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(5)

    def _run_server(self):
        """运行服务器（在线程中）"""
        try:
            # 创建新的事件循环
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            # 运行服务器
            self.running = True
            server = websockets.serve(
                self.handle_client,
                self.host,
                self.port,
                ping_interval=None,  # 禁用自动ping，我们手动处理
                ping_timeout=None
            )

            self.server = self.loop.run_until_complete(server)

            # 启动心跳循环
            self.loop.create_task(self.heartbeat_loop())

            logger.info(f"Socket server started on {self.host}:{self.port}")

            # 运行事件循环
            self.loop.run_forever()

        except Exception as e:
            logger.error(f"Error running socket server: {e}")
        finally:
            self.running = False
            logger.info("Socket server stopped")

    def start(self):
        """启动Socket服务器"""
        if self.running:
            logger.warning("Socket server is already running")
            return

        try:
            self.thread = threading.Thread(target=self._run_server, daemon=True)
            self.thread.start()

            # 等待服务器启动
            time.sleep(2)  # 给更多时间启动
            if self.running:
                logger.info("Socket server started successfully")
            else:
                logger.error("Failed to start socket server")
        except Exception as e:
            logger.error(f"Exception starting socket server: {e}")

    def stop(self):
        """停止Socket服务器"""
        if not self.running:
            logger.warning("Socket server is not running")
            return

        logger.info("Stopping socket server...")
        self.running = False

        # 关闭所有客户端连接
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self._close_all_clients(),
                self.loop
            )

        # 停止事件循环
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)

        # 等待线程结束
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

        logger.info("Socket server stopped")

    async def _close_all_clients(self):
        """关闭所有客户端连接"""
        close_tasks = []
        for client in self.clients.values():
            try:
                close_tasks.append(client.websocket.close())
            except Exception:
                pass

        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)

        self.clients.clear()

    def get_status(self) -> Dict[str, Any]:
        """获取服务器状态"""
        return {
            "running": self.running,
            "host": self.host,
            "port": self.port,
            "connected_clients": len(self.clients),
            "max_clients": self.max_clients,
            "clients": [
                {
                    "id": client.client_id,
                    "connected_at": client.connected_at,
                    "authenticated": client.is_authenticated,
                    "subscriptions": list(client.subscriptions)
                }
                for client in self.clients.values()
            ]
        }


# 全局Socket服务器实例
socket_server = SocketServer()