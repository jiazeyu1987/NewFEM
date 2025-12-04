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

        # 状态
        self.running = False
        self.data_count = 0

        # 数据存储
        self.time_data = []
        self.signal_data = []

        # 构建UI
        self._build_ui()
        self._setup_matplotlib()

        # 自动启动
        self.root.after(1000, self.auto_start)

    def _build_ui(self):
        """构建简化UI"""
        # 顶部状态栏
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", padx=5, pady=5)

        self.status_label = ttk.Label(status_frame, text="Initializing...", font=("Arial", 12))
        self.status_label.pack(side="left", padx=10)

        self.data_label = ttk.Label(status_frame, text="Data: 0 points")
        self.data_label.pack(side="left", padx=20)

        # 控制按钮
        ttk.Button(status_frame, text="Start/Stop", command=self.toggle_detection).pack(side="right", padx=5)
        ttk.Button(status_frame, text="Clear", command=self.clear_data).pack(side="right", padx=5)
        ttk.Button(status_frame, text="Exit", command=self.root.quit).pack(side="right", padx=5)

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
        self.ax.set_ylim(20, 60)

        # 创建线条
        self.signal_line, = self.ax.plot([], [], 'b-', linewidth=2, label='Signal', marker='o', markersize=2)
        self.baseline_line, = self.ax.plot([], [], 'r--', linewidth=1, label='Baseline', alpha=0.6)
        self.ax.legend(loc='upper right')

        plt.tight_layout()

        # 创建canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def auto_start(self):
        """自动启动 - 无需用户手动连接"""
        self.status_label.config(text="Connecting to server...")
        self.root.update()

        try:
            # 1. 测试连接
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            if response.status_code != 200:
                raise Exception("Server not responding")

            # 2. 自动配置ROI
            roi_data = {"x1": 0, "y1": 0, "x2": 200, "y2": 150, "password": self.password}
            response = self.session.post(f"{self.base_url}/roi/config", data=roi_data, timeout=5)

            # 3. 自动启动检测
            control_data = {"command": "start_detection", "password": self.password}
            response = self.session.post(f"{self.base_url}/control", data=control_data, timeout=5)

            self.status_label.config(text="Connected - Ready", foreground="green")

            # 4. 自动开始数据收集
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

                if len(self.signal_data) > 10:
                    y_min = min(self.signal_data[-50:]) - 5
                    y_max = max(self.signal_data[-50:]) + 5
                    self.ax.set_ylim(y_min, y_max)

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
        self.ax.set_ylim(20, 60)

        self.canvas.draw()
        self.data_label.config(text="Data: 0 points")

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