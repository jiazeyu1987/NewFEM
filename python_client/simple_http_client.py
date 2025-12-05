#!/usr/bin/env python3
"""
简化版HTTP客户端 - 直接启动，无需手动连接
自动完成所有初始化步骤
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import requests
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from datetime import datetime
from local_config_loader import LocalConfigLoader

# 设置matplotlib字体
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Liberation Sans']
plt.rcParams['axes.unicode_minus'] = False


class SimpleHTTPClient:
    """简化版HTTP客户端 - 自动连接和启动"""

    def __init__(self, base_url="http://localhost:8421", password="31415"):
        self.base_url = base_url
        self.password = password
        self.session = requests.Session()

        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("NewFEM Simple HTTP Client")
        self.root.geometry("1000x700")

        # UI模式状态
        self.compact_mode = False
        self.normal_geometry = "1000x700"
        self.compact_geometry = "800x400"

        # 状态
        self.running = False
        self.data_count = 0

        # 数据存储
        self.time_data = []
        self.signal_data = []

        # UI组件引用
        self.status_label = None
        self.data_label = None
        self.clear_button = None
        self.exit_button = None
        self.toggle_button = None

        # 构建UI
        self._build_ui()
        self._setup_matplotlib()

        # 自动启动
        self.root.after(1000, self.auto_start)

    def _build_ui(self):
        """构建简化UI"""
        # 顶部状态栏
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(fill="x", padx=5, pady=5)

        # 状态标签组
        self.status_label = ttk.Label(self.status_frame, text="Initializing...", font=("Arial", 12))
        self.status_label.pack(side="left", padx=10)

        self.data_label = ttk.Label(self.status_frame, text="Data: 0 points")
        self.data_label.pack(side="left", padx=20)

        # 控制按钮组 - 分为核心按钮和附加按钮
        # 核心按钮（始终显示）
        self.toggle_button = ttk.Button(self.status_frame, text="Start/Stop", command=self.toggle_detection)
        self.toggle_button.pack(side="right", padx=5)

        # UI模式切换按钮
        self.ui_mode_button = ttk.Button(self.status_frame, text="缩小", command=self.toggle_ui_mode)
        self.ui_mode_button.pack(side="right", padx=5)

        # 附加按钮（在紧凑模式下隐藏）
        self.clear_button = ttk.Button(self.status_frame, text="Clear", command=self.clear_data)
        self.clear_button.pack(side="right", padx=5)

        self.exit_button = ttk.Button(self.status_frame, text="Exit", command=self.root.quit)
        self.exit_button.pack(side="right", padx=5)

        # 图表区域
        self.plot_frame = ttk.Frame(self.root)
        self.plot_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def _setup_matplotlib(self):
        """设置matplotlib"""
        # 创建图表
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.fig.patch.set_facecolor('white')

        # 设置图表
        self.ax.set_title("Real-time Signal Data", fontsize=14, fontweight='bold')
        self.ax.set_xlabel("Time (seconds)")
        self.ax.set_ylabel("Signal Value")
        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlim(0, 10)
        self.ax.set_ylim(0, 200)

        # 创建线条
        self.signal_line, = self.ax.plot([], [], 'b-', linewidth=2, label='Signal', marker='o', markersize=2)
        self.baseline_line, = self.ax.plot([], [], 'r--', linewidth=1, label='Baseline', alpha=0.6)
        self.ax.legend(loc='upper right')

        plt.tight_layout()

        # 创建canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _load_local_config(self):
        """从本地配置文件加载配置"""
        try:
            self.log_message("正在加载本地配置文件...")

            # 创建本地配置加载器
            config_loader = LocalConfigLoader()

            # 加载配置
            success, message, config_data = config_loader.load_config()

            if success:
                self.log_message(f"✅ {message}")

                # 应用配置
                if self._apply_server_config(config_data):
                    self.log_message("🎯 本地配置已成功应用")
                    return True
                else:
                    self.log_message("⚠️ 本地配置应用失败，使用默认值")
                    return False
            else:
                self.log_message(f"❌ 本地配置加载失败: {message}")
                return False

        except Exception as e:
            self.log_message(f"❌ 本地配置加载异常: {str(e)}")
            return False

    def _auto_load_config(self):
        """自动加载服务器配置"""
        try:
            self.log_message("正在自动加载服务器配置...")

            # 请求配置
            response = self.session.get(
                f"{self.base_url}/config",
                params={"password": self.password},
                timeout=5
            )

            if response.status_code == 200:
                config_data = response.json()
                if "config" in config_data:
                    config = config_data["config"]

                    # 应用配置
                    if self._apply_server_config(config):
                        self.log_message("✅ 服务器配置自动加载成功")
                        return True
                    else:
                        self.log_message("⚠️ 服务器配置格式异常，使用默认值")
                        return False
                else:
                    self.log_message("⚠️ 服务器配置响应格式错误")
                    return False
            else:
                self.log_message(f"⚠️ 获取服务器配置失败: HTTP {response.status_code}")
                return False

        except Exception as e:
            self.log_message(f"⚠️ 自动加载配置失败: {str(e)}")
            return False

    def _apply_server_config(self, config_dict):
        """应用从服务器加载的配置"""
        try:
            if not config_dict:
                return False

            config_applied = False

            # 存储配置供ROI设置使用
            self.server_config = config_dict

            # 如果有ROI配置，标记为已应用
            if "roi_capture" in config_dict:
                roi_config = config_dict["roi_capture"]
                if "default_config" in roi_config:
                    self.roi_config = roi_config["default_config"]
                    config_applied = True

            return config_applied

        except Exception as e:
            self.log_message(f"应用服务器配置失败: {str(e)}")
            return False

    def auto_start(self):
        """自动启动 - 无需用户手动连接"""
        self.status_label.config(text="Loading configuration...")
        self.root.update()

        try:
            # 1. 首先加载本地配置（无需服务器连接）
            self.log_message("正在加载本地配置文件...")
            local_config_loaded = self._load_local_config()

            self.status_label.config(text="Connecting to server...")
            self.root.update()

            # 2. 测试连接
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            if response.status_code != 200:
                raise Exception("Server not responding")

            # 3. 如果本地配置加载失败，尝试从服务器加载配置
            if not local_config_loaded:
                self.log_message("本地配置加载失败，尝试从服务器加载配置...")
                self._auto_load_config()

            # 4. 自动配置ROI (使用加载的配置或默认值)
            if hasattr(self, 'roi_config'):
                roi_data = {
                    "x1": self.roi_config.get("x1", 0),
                    "y1": self.roi_config.get("y1", 0),
                    "x2": self.roi_config.get("x2", 200),
                    "y2": self.roi_config.get("y2", 150),
                    "password": self.password
                }
                if local_config_loaded:
                    self.log_message(f"使用本地配置ROI: {roi_data}")
                else:
                    self.log_message(f"使用服务器配置ROI: {roi_data}")
            else:
                roi_data = {"x1": 0, "y1": 0, "x2": 200, "y2": 150, "password": self.password}
                self.log_message("使用默认ROI配置")

            response = self.session.post(f"{self.base_url}/roi/config", data=roi_data, timeout=5)

            # 4. 自动启动检测
            control_data = {"command": "start_detection", "password": self.password}
            response = self.session.post(f"{self.base_url}/control", data=control_data, timeout=5)

            self.status_label.config(text="Connected - Ready", foreground="green")

            # 5. 自动开始数据收集
            self.root.after(1000, self.start_data_collection)

        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}", foreground="red")

    def start_data_collection(self):
        """开始数据收集"""
        self.running = True
        self.status_label.config(text="Collecting data...", foreground="blue")
        self.collect_data()

    def collect_data(self):
        """收集数据"""
        if not self.running:
            return

        try:
            response = self.session.get(f"{self.base_url}/data/realtime?count=1", timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get("type") == "realtime_data":
                    # 提取信号值
                    series = data.get("series", [])
                    if series:
                        signal_value = series[0].get("value", 0)
                    else:
                        signal_value = data.get("value", 0)

                    # 处理时间戳
                    timestamp = data.get("timestamp", "")
                    if timestamp:
                        dt = timestamp.replace('Z', '+00:00')
                        if not self.time_data:
                            self.start_time = datetime.fromisoformat(dt)
                        relative_time = (datetime.fromisoformat(dt) - self.start_time).total_seconds()
                    else:
                        if not self.time_data:
                            self.start_time = time.time()
                        relative_time = time.time() - self.start_time

                    # 添加数据
                    self.time_data.append(relative_time)
                    self.signal_data.append(signal_value)
                    self.data_count += 1

                    # 限制数据点
                    if len(self.time_data) > 200:
                        self.time_data = self.time_data[-200:]
                        self.signal_data = self.signal_data[-200:]

                    # 更新显示
                    self.update_chart()
                    self.data_label.config(text=f"Data: {self.data_count} points")

        except Exception as e:
            print(f"Data collection error: {e}")

        # 继续收集 (50ms间隔 = 20 FPS)
        self.root.after(50, self.collect_data)

    def update_chart(self):
        """更新图表"""
        if len(self.time_data) > 0:
            # 更新信号线
            self.signal_line.set_data(self.time_data, self.signal_data)

            # 更新基线
            if len(self.signal_data) > 20:
                baseline = np.mean(self.signal_data[-20:])
                baseline_data = [baseline] * len(self.time_data)
                self.baseline_line.set_data(self.time_data, baseline_data)

            # 自动调整坐标轴
            if self.time_data:
                if self.time_data[-1] > 10:
                    x_min = max(0, self.time_data[-1] - 10)
                    x_max = self.time_data[-1] + 0.5
                else:
                    x_min = 0
                    x_max = 10

                self.ax.set_xlim(x_min, x_max)

                # Y轴固定范围0-200，不进行自动缩放
                # if len(self.signal_data) > 10:
                #     y_min = min(self.signal_data[-50:]) - 5
                #     y_max = max(self.signal_data[-50:]) + 5
                #     self.ax.set_ylim(y_min, y_max)

            # 重绘canvas
            self.canvas.draw_idle()

    def toggle_detection(self):
        """切换检测状态"""
        self.running = not self.running
        if self.running:
            self.status_label.config(text="Collecting data...", foreground="blue")
            self.collect_data()
        else:
            self.status_label.config(text="Paused", foreground="orange")

    def clear_data(self):
        """清除数据"""
        self.time_data = []
        self.signal_data = []
        self.data_count = 0

        self.signal_line.set_data([], [])
        self.baseline_line.set_data([], [])

        self.ax.set_xlim(0, 10)
        self.ax.set_ylim(0, 200)

        self.canvas.draw()
        self.data_label.config(text="Data: 0 points")

    def toggle_ui_mode(self):
        """切换UI模式（紧凑/完整）"""
        self.compact_mode = not self.compact_mode

        if self.compact_mode:
            # 切换到紧凑模式
            self.root.geometry(self.compact_geometry)
            self.ui_mode_button.config(text="放大")

            # 隐藏非必要元素
            self.data_label.pack_forget()
            self.clear_button.pack_forget()
            self.exit_button.pack_forget()

            # 调整图表大小
            self.fig.set_size_inches(10, 5)

            # 简化状态文本
            if hasattr(self, 'status_label') and self.status_label:
                current_text = self.status_label.cget("text")
                if "Running" in current_text:
                    self.status_label.config(text="运行中")
                elif "Connected" in current_text:
                    self.status_label.config(text="已连接")
                else:
                    self.status_label.config(text="就绪")

        else:
            # 切换到完整模式
            self.root.geometry(self.normal_geometry)
            self.ui_mode_button.config(text="缩小")

            # 显示所有元素
            self.data_label.pack(side="left", padx=20, after=self.status_label)
            self.clear_button.pack(side="right", padx=5)
            self.exit_button.pack(side="right", padx=5)

            # 恢复图表大小
            self.fig.set_size_inches(12, 6)

            # 恢复详细状态文本
            if hasattr(self, 'status_label') and self.status_label:
                current_text = self.status_label.cget("text")
                if "运行中" in current_text:
                    self.status_label.config(text="✓ Connected - Running...")
                elif "已连接" in current_text:
                    self.status_label.config(text="✓ Connected - Ready")
                else:
                    self.status_label.config(text="Initializing...")

        # 重新绘制图表
        self.canvas.draw()

    def run(self):
        """运行应用"""
        print("Simple HTTP Client started - Auto-connecting to server...")
        self.root.mainloop()


def main():
    """主函数"""
    try:
        app = SimpleHTTPClient()
        app.run()
    except Exception as e:
        print(f"Application error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()