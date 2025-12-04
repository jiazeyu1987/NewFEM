#!/usr/bin/env python3
"""
Socket客户端测试脚本
用于验证Socket服务器和实时数据推送功能
"""

import asyncio
import json
import time
import logging
from python_client.socket_client import SocketClient

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestSocketClient:
    """测试Socket客户端"""

    def __init__(self):
        self.client = SocketClient(host="localhost", port=30415)
        self.data_count = 0
        self.last_data_time = 0

    async def handle_realtime_data(self, data):
        """处理实时数据"""
        self.data_count += 1
        self.last_data_time = time.time()

        # 每100个数据点打印一次统计
        if self.data_count % 100 == 0:
            signal_value = data.get("signal_value", 0)
            peak_signal = data.get("peak_signal", 0)
            frame_count = data.get("frame_count", 0)
            data_source = data.get("data_source", "unknown")

            print(f"数据点 #{self.data_count}: 信号={signal_value:.1f}, "
                  f"波峰={peak_signal}, 帧数={frame_count}, 来源={data_source}")

    async def handle_control_response(self, data):
        """处理控制响应"""
        command = data.get("command", "")
        success = data.get("success", False)
        message = data.get("message", "")

        print(f"控制响应 [{command}]: {'成功' if success else '失败'} - {message}")

    async def handle_system_status(self, data):
        """处理系统状态"""
        print(f"系统状态更新: {json.dumps(data, indent=2)}")

    def on_connection_change(self, connected: bool):
        """连接状态变化"""
        status = "已连接" if connected else "已断开"
        print(f"连接状态: {status}")

    def on_error(self, error):
        """错误处理"""
        print(f"错误: {error}")

    async def run_test(self):
        """运行测试"""
        print("=== NewFEM Socket客户端测试 ===")

        # 注册事件处理器
        self.client.register_message_handler("realtime_data", self.handle_realtime_data)
        self.client.register_message_handler("control_response", self.handle_control_response)
        self.client.register_message_handler("system_status", self.handle_system_status)
        self.client.register_connection_callback(self.on_connection_change)
        self.client.register_error_callback(self.on_error)

        # 连接到服务器
        print("正在连接到服务器...")
        try:
            await self.client.connect(password="31415")
        except Exception as e:
            print(f"连接失败: {e}")
            return

        # 等待连接建立
        await asyncio.sleep(2)

        if not self.client.is_connected():
            print("连接失败，退出测试")
            return

        print("连接成功！")

        # 订阅消息类型
        await self.client.subscribe(["realtime_data", "system_status"])
        print("已订阅实时数据和系统状态")

        # 等待2秒接收数据
        print("等待接收数据...")
        await asyncio.sleep(2)

        if self.data_count > 0:
            print(f"✅ 接收到 {self.data_count} 个数据点")
        else:
            print("⚠️ 未接收到数据，可能需要先启动检测")

        # 测试控制命令
        print("\n=== 测试控制命令 ===")
        print("发送开始检测命令...")
        await self.client.send_command("start_detection")
        await asyncio.sleep(3)

        print("发送停止检测命令...")
        await self.client.send_command("stop_detection")
        await asyncio.sleep(1)

        # 再接收一会儿数据
        print("继续接收数据5秒...")
        await asyncio.sleep(5)

        # 打印最终统计
        print(f"\n=== 测试结果 ===")
        print(f"总数据点数: {self.data_count}")
        if self.last_data_time > 0:
            time_span = time.time() - self.last_data_time
            print(f"数据接收时长: {time_span:.1f}秒")

        # 显示客户端状态
        status = self.client.get_status()
        print(f"客户端状态: {json.dumps(status, indent=2)}")

        # 断开连接
        print("\n断开连接...")
        await self.client.close()
        print("测试完成！")


async def main():
    """主函数"""
    tester = TestSocketClient()

    try:
        await tester.run_test()
    except KeyboardInterrupt:
        print("\n用户中断测试")
    except Exception as e:
        print(f"测试出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())