"""
Python客户端Socket通信模块
替代HTTP轮询，实现实时数据接收和控制命令发送
"""

import asyncio
import json
import logging
import threading
import time
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime

import websockets
from websockets.client import WebSocketClientProtocol


logger = logging.getLogger(__name__)


class SocketClient:
    """Socket客户端 - 连接到后端Socket服务器"""

    def __init__(self, host: str = "localhost", port: int = 30415):
        self.host = host
        self.port = port
        self.url = f"ws://{host}:{port}"
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.connected = False
        self.authenticated = False

        # 回调处理器
        self.message_handlers: Dict[str, Callable] = {}
        self.connection_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []

        # 心跳控制
        self.last_ping = 0
        self.last_pong = 0
        self.heartbeat_interval = 10.0
        self.heartbeat_timeout = 30.0

        # 数据缓冲
        self.data_buffer: List[Dict[str, Any]] = []
        self.max_buffer_size = 1000

        logger.info(f"SocketClient initialized for {self.url}")

    def register_message_handler(self, message_type: str, handler: Callable):
        """注册消息处理器"""
        self.message_handlers[message_type] = handler
        logger.info(f"Registered handler for message type: {message_type}")

    def register_connection_callback(self, callback: Callable):
        """注册连接状态回调"""
        self.connection_callbacks.append(callback)

    def register_error_callback(self, callback: Callable):
        """注册错误回调"""
        self.error_callbacks.append(callback)

    async def connect(self, password: str = "31415"):
        """连接到服务器"""
        try:
            if self.running:
                logger.warning("Socket client is already running")
                return

            self.running = True
            self.websocket = await websockets.connect(self.url)
            self.connected = True

            logger.info(f"Connected to WebSocket server at {self.url}")

            # 启动消息处理循环
            asyncio.create_task(self._message_loop())

            # 发送认证消息
            await self.authenticate(password)

            # 通知连接成功
            for callback in self.connection_callbacks:
                try:
                    callback(True)
                except Exception as e:
                    logger.error(f"Error in connection callback: {e}")

        except Exception as e:
            logger.error(f"Failed to connect to WebSocket server: {e}")
            self.running = False
            self.connected = False
            await self._handle_error(e)

    async def authenticate(self, password: str):
        """认证"""
        try:
            auth_message = {
                "type": "auth",
                "password": password
            }

            await self.websocket.send(json.dumps(auth_message))
            logger.info("Authentication message sent")

        except Exception as e:
            logger.error(f"Failed to send authentication: {e}")
            await self._handle_error(e)

    async def subscribe(self, message_types: List[str]):
        """订阅消息类型"""
        try:
            subscribe_message = {
                "type": "subscribe",
                "data": {
                    "subscriptions": message_types
                }
            }

            await self.websocket.send(json.dumps(subscribe_message))
            logger.info(f"Subscribed to message types: {message_types}")

        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
            await self._handle_error(e)

    async def send_command(self, command: str, data: Optional[Dict[str, Any]] = None):
        """发送控制命令"""
        try:
            if not self.connected or not self.authenticated:
                raise Exception("Not connected or not authenticated")

            command_message = {
                "type": command,
                "data": data or {}
            }

            await self.websocket.send(json.dumps(command_message))
            logger.info(f"Command sent: {command}")

        except Exception as e:
            logger.error(f"Failed to send command {command}: {e}")
            await self._handle_error(e)

    async def _message_loop(self):
        """消息处理循环"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {message}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
            self.connected = False
            self.authenticated = False
        except Exception as e:
            logger.error(f"Error in message loop: {e}")
            await self._handle_error(e)
        finally:
            self.running = False

    async def _handle_message(self, data: Dict[str, Any]):
        """处理接收到的消息"""
        message_type = data.get("type", "unknown")

        # 处理认证响应
        if message_type == "auth_success":
            self.authenticated = True
            logger.info("Authentication successful")
            return

        elif message_type == "auth_error":
            self.authenticated = False
            logger.error("Authentication failed")
            return

        # 处理心跳
        elif message_type == "ping":
            await self._send_pong()
            return

        elif message_type == "pong":
            self.last_pong = time.time()
            return

        # 调用注册的处理器
        if message_type in self.message_handlers:
            try:
                await self.message_handlers[message_type](data)
            except Exception as e:
                logger.error(f"Error in message handler for {message_type}: {e}")
        else:
            logger.debug(f"Unhandled message type: {message_type}")

    async def _send_pong(self):
        """发送pong响应"""
        try:
            pong_message = {
                "type": "pong",
                "timestamp": time.time()
            }
            await self.websocket.send(json.dumps(pong_message))
        except Exception as e:
            logger.error(f"Failed to send pong: {e}")

    async def _handle_error(self, error: Exception):
        """处理错误"""
        for callback in self.error_callbacks:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")

    async def _heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            try:
                current_time = time.time()

                # 检查连接超时
                if self.last_pong > 0 and (current_time - self.last_pong) > self.heartbeat_timeout:
                    logger.warning("Heartbeat timeout, reconnecting...")
                    await self.reconnect()
                    continue

                # 发送心跳
                if (current_time - self.last_ping) > self.heartbeat_interval:
                    await self._send_ping()
                    self.last_ping = current_time

                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(5)

    async def _send_ping(self):
        """发送心跳"""
        try:
            ping_message = {
                "type": "ping",
                "timestamp": time.time()
            }
            await self.websocket.send(json.dumps(ping_message))
        except Exception as e:
            logger.error(f"Failed to send ping: {e}")

    async def reconnect(self):
        """重新连接"""
        logger.info("Attempting to reconnect...")

        try:
            if self.websocket:
                await self.websocket.close()
        except Exception:
            pass

        self.connected = False
        self.authenticated = False
        self.last_ping = 0
        self.last_pong = 0

        # 等待一段时间后重连
        await asyncio.sleep(5)

        # 这里需要密码，实际使用时应该保存密码或通过回调获取
        await self.connect()

    def _run_client(self):
        """运行客户端（在线程中）"""
        try:
            # 创建新的事件循环
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            # 启动心跳循环
            self.loop.create_task(self._heartbeat_loop())

            # 运行事件循环
            self.loop.run_forever()

        except Exception as e:
            logger.error(f"Error running socket client: {e}")
        finally:
            self.running = False

    def start(self, password: str = "31415"):
        """启动客户端"""
        if self.running:
            logger.warning("Socket client is already running")
            return

        self.thread = threading.Thread(target=self._run_client, daemon=True)
        self.thread.start()

        # 等待事件循环启动
        time.sleep(0.5)

        # 在事件循环中执行连接
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.connect(password),
                self.loop
            )

        # 等待连接完成
        time.sleep(1)

    def stop(self):
        """停止客户端"""
        if not self.running:
            logger.warning("Socket client is not running")
            return

        logger.info("Stopping socket client...")
        self.running = False

        # 关闭WebSocket连接
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self._close_connection(),
                self.loop
            )

        # 停止事件循环
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)

        # 等待线程结束
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

        logger.info("Socket client stopped")

    async def _close_connection(self):
        """关闭连接"""
        try:
            if self.websocket:
                await self.websocket.close()
        except Exception:
            pass

        self.connected = False
        self.authenticated = False

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.connected and self.authenticated

    def get_status(self) -> Dict[str, Any]:
        """获取客户端状态"""
        return {
            "running": self.running,
            "connected": self.connected,
            "authenticated": self.authenticated,
            "url": self.url,
            "last_ping": self.last_ping,
            "last_pong": self.last_pong,
            "buffer_size": len(self.data_buffer),
            "handlers": list(self.message_handlers.keys())
        }


# 便捷函数
async def send_control_command(client: SocketClient, command: str, data: Optional[Dict[str, Any]] = None, timeout: float = 5.0) -> Dict[str, Any]:
    """发送控制命令并等待响应"""
    response_future = asyncio.Future()

    async def handle_response(response_data):
        if response_data.get("type") == "control_response" and response_data.get("data", {}).get("command") == command:
            response_future.set_result(response_data["data"])

    # 注册临时响应处理器
    original_handler = client.message_handlers.get("control_response")
    client.message_handlers["control_response"] = handle_response

    try:
        # 发送命令
        await client.send_command(command, data)

        # 等待响应
        response = await asyncio.wait_for(response_future, timeout=timeout)
        return response

    except asyncio.TimeoutError:
        logger.error(f"Timeout waiting for response to command: {command}")
        raise
    finally:
        # 恢复原始处理器
        if original_handler:
            client.message_handlers["control_response"] = original_handler
        else:
            client.message_handlers.pop("control_response", None)