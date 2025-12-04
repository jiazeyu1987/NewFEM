"""
实时绘图组件 - 使用matplotlib实现流畅的实时曲线绘制
与Socket客户端集成，支持多种数据类型显示
"""

import threading
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

# 设置logger
logger = logging.getLogger(__name__)

# 设置matplotlib使用英文标签避免字体问题
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Liberation Sans']
plt.rcParams['axes.unicode_minus'] = False


class RealtimePlotter:
    """实时绘图器"""

    def __init__(self, master=None, figsize=(12, 8), max_points=1000):
        self.master = master
        self.figsize = figsize
        self.max_points = max_points

        # 数据存储
        self.time_data = []
        self.signal_data = []
        self.peak_data = []
        self.enhanced_peak_data = []  # 增强波峰数据

        # 图表配置
        self.fig = None
        self.ax_main = None
        self.ax_peak = None
        self.canvas = None
        self.animation = None
        self.lines = {}

        # 显示选项
        self.show_grid = True
        self.show_peaks = True
        self.show_enhanced_peaks = True
        self.auto_scale = True

        # 性能统计
        self.update_count = 0
        self.fps = 0
        self.last_update_time = time.time()
        self.update_times = []

        logger.info("RealtimePlotter initialized")

    def setup_plot(self):
        """设置图表"""
        # 创建图表和子图
        self.fig, (self.ax_main, self.ax_peak) = plt.subplots(
            2, 1, figsize=self.figsize, gridspec_kw={'height_ratios': [3, 1]}
        )

        # 主图表 - 信号曲线
        self.ax_main.set_title("Real-time Signal", fontsize=14, fontweight='bold')
        self.ax_main.set_xlabel("Time (seconds)")
        self.ax_main.set_ylabel("Signal Value")
        self.ax_main.grid(True, alpha=0.3)
        self.ax_main.set_xlim(0, 10)  # 初始显示10秒数据
        self.ax_main.set_ylim(100, 140)  # 初始Y轴范围

        # 创建主线（信号曲线）
        self.lines['signal'], = self.ax_main.plot([], [], 'b-', linewidth=1.5, label='Signal', alpha=0.8)

        # 基线
        self.lines['baseline'], = self.ax_main.plot([], [], 'r--', linewidth=1, label='Baseline', alpha=0.6)

        # 波峰点
        self.lines['peaks'], = self.ax_main.plot([], [], 'ro', markersize=6, label='Peaks', alpha=0.8)

        # 增强波峰点（不同颜色）
        self.lines['enhanced_peaks_green'], = self.ax_main.plot([], [], 'go', markersize=8, label='Green Peaks', alpha=0.8)
        self.lines['enhanced_peaks_red'], = self.ax_main.plot([], [], 'ro', markersize=8, label='Red Peaks', alpha=0.8)

        self.ax_main.legend(loc='upper right')

        # 底部图表 - 波峰信号
        self.ax_peak.set_title("Peak Signal", fontsize=12)
        self.ax_peak.set_xlabel("Time (seconds)")
        self.ax_peak.set_ylabel("Peak Signal")
        self.ax_peak.grid(True, alpha=0.3)
        self.ax_peak.set_ylim(-0.5, 1.5)
        self.ax_peak.set_yticks([0, 1])
        self.ax_peak.set_yticklabels(['No Peak', 'Peak'])

        self.lines['peak_signal'], = self.ax_peak.plot([], [], 'g-', linewidth=2, label='Peak Signal')
        self.ax_peak.legend(loc='upper right')

        # 布局调整
        plt.tight_layout()

        # 设置背景颜色
        self.fig.patch.set_facecolor('#f0f0f0')

    def setup_canvas(self):
        """设置Tkinter Canvas"""
        if self.master:
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill='both', expand=True)
        else:
            # 如果没有master，使用matplotlib的默认显示
            plt.show(block=False)

    def update_data(self, data: Dict[str, Any]):
        """更新数据"""
        try:
            # 更新性能统计
            current_time = time.time()
            self.update_count += 1
            update_time = current_time - self.last_update_time
            self.update_times.append(update_time)
            self.last_update_time = current_time

            # 保持最近100次更新的时间用于计算FPS
            if len(self.update_times) > 100:
                self.update_times = self.update_times[-100:]

            # 提取时间戳和信号值 - 信号值在series数组中
            timestamp = data.get("timestamp")
            series = data.get("series", [])
            if series:
                signal_value = series[0].get("value", 0)
            else:
                signal_value = data.get("signal_value", 0)
            peak_signal = data.get("peak_signal")
            frame_count = data.get("frame_count", 0)

            # 转换时间戳为相对秒数（相对于第一个数据点）
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                if not self.time_data:
                    self.start_time = dt
                relative_time = (dt - self.start_time).total_seconds()
            else:
                # 如果没有时间戳，使用累积时间
                if not self.time_data:
                    self.start_time = time.time()
                relative_time = time.time() - self.start_time

            # 添加数据点
            self.time_data.append(relative_time)
            self.signal_data.append(signal_value)

            if peak_signal is not None:
                self.peak_data.append(peak_signal)
            else:
                self.peak_data.append(0)

            # 处理增强波峰数据
            enhanced_peak = data.get("enhanced_peak", {})
            if enhanced_peak:
                peak_color = enhanced_peak.get("peak_color")
                peak_confidence = enhanced_peak.get("peak_confidence", 0.0)
                self.enhanced_peak_data.append({
                    "time": relative_time,
                    "value": signal_value,
                    "color": peak_color,
                    "confidence": peak_confidence
                })
            else:
                self.enhanced_peak_data.append(None)

            # 限制数据点数量
            if len(self.time_data) > self.max_points:
                self.time_data = self.time_data[-self.max_points:]
                self.signal_data = self.signal_data[-self.max_points:]
                self.peak_data = self.peak_data[-self.max_points:]
                self.enhanced_peak_data = self.enhanced_peak_data[-self.max_points:]

        except Exception as e:
            logger.error(f"Error updating plot data: {e}")

    def update_plot(self, frame=None):
        """更新图表（动画函数）"""
        try:
            if not self.time_data:
                return self.lines.values()

            # 更新主线（信号曲线）
            self.lines['signal'].set_data(self.time_data, self.signal_data)

            # 更新基线（使用最近100个点的平均值）
            if len(self.signal_data) > 100:
                baseline = np.mean(self.signal_data[-100:])
                baseline_data = [baseline] * len(self.time_data)
                self.lines['baseline'].set_data(self.time_data, baseline_data)
            else:
                self.lines['baseline'].set_data([], [])

            # 更新波峰点
            if self.show_peaks:
                peak_times = []
                peak_values = []
                for i, peak_val in enumerate(self.peak_data):
                    if peak_val == 1:  # 有波峰
                        peak_times.append(self.time_data[i])
                        peak_values.append(self.signal_data[i])

                self.lines['peaks'].set_data(peak_times, peak_values)
            else:
                self.lines['peaks'].set_data([], [])

            # 更新增强波峰点
            if self.show_enhanced_peaks:
                green_times, green_values = [], []
                red_times, red_values = [], []

                for i, peak_info in enumerate(self.enhanced_peak_data):
                    if peak_info and i < len(self.time_data):
                        if peak_info["color"] == "green":
                            green_times.append(peak_info["time"])
                            green_values.append(peak_info["value"])
                        elif peak_info["color"] == "red":
                            red_times.append(peak_info["time"])
                            red_values.append(peak_info["value"])

                self.lines['enhanced_peaks_green'].set_data(green_times, green_values)
                self.lines['enhanced_peaks_red'].set_data(red_times, red_values)
            else:
                self.lines['enhanced_peaks_green'].set_data([], [])
                self.lines['enhanced_peaks_red'].set_data([], [])

            # 更新波峰信号图
            self.lines['peak_signal'].set_data(self.time_data, self.peak_data)

            # 自动调整X轴范围
            if self.auto_scale and self.time_data:
                if self.time_data[-1] > 10:
                    # 显示最近10秒的数据
                    x_min = max(0, self.time_data[-1] - 10)
                    x_max = self.time_data[-1] + 0.5
                    self.ax_main.set_xlim(x_min, x_max)
                    self.ax_peak.set_xlim(x_min, x_max)

            # 自动调整Y轴范围
            if self.auto_scale and self.signal_data:
                y_min = min(self.signal_data[-200:] if len(self.signal_data) > 200 else self.signal_data) - 5
                y_max = max(self.signal_data[-200:] if len(self.signal_data) > 200 else self.signal_data) + 5
                self.ax_main.set_ylim(y_min, y_max)

            # 更新网格
            self.ax_main.grid(self.show_grid, alpha=0.3)
            self.ax_peak.grid(self.show_grid, alpha=0.3)

            # 计算FPS
            if self.update_times:
                avg_update_time = np.mean(self.update_times[-10:])  # 最近10次的平均时间
                self.fps = 1.0 / avg_update_time if avg_update_time > 0 else 0

            return self.lines.values()

        except Exception as e:
            logger.error(f"Error updating plot: {e}")
            return self.lines.values()

    def start_animation(self, interval=50):  # 20 FPS
        """启动动画"""
        if self.animation:
            self.animation.event_source.stop()

        self.animation = animation.FuncAnimation(
            self.fig, self.update_plot, interval=interval, blit=False
        )

        if self.canvas:
            self.canvas.draw()

    def stop_animation(self):
        """停止动画"""
        if self.animation:
            self.animation.event_source.stop()
            self.animation = None

    def clear_data(self):
        """清空数据"""
        self.time_data.clear()
        self.signal_data.clear()
        self.peak_data.clear()
        self.enhanced_peak_data.clear()
        self.update_count = 0
        self.update_times.clear()

    def set_display_options(self, show_grid=True, show_peaks=True, show_enhanced_peaks=True, auto_scale=True):
        """设置显示选项"""
        self.show_grid = show_grid
        self.show_peaks = show_peaks
        self.show_enhanced_peaks = show_enhanced_peaks
        self.auto_scale = auto_scale

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "data_points": len(self.time_data),
            "update_count": self.update_count,
            "fps": self.fps,
            "peaks_detected": sum(self.peak_data),
            "enhanced_peaks_green": len([p for p in self.enhanced_peak_data if p and p.get("color") == "green"]),
            "enhanced_peaks_red": len([p for p in self.enhanced_peak_data if p and p.get("color") == "red"]),
            "signal_range": {
                "min": min(self.signal_data) if self.signal_data else 0,
                "max": max(self.signal_data) if self.signal_data else 0,
                "avg": np.mean(self.signal_data) if self.signal_data else 0
            }
        }

    def save_screenshot(self, filename: str):
        """保存截图"""
        if self.fig:
            self.fig.savefig(filename, dpi=150, bbox_inches='tight')
            logger.info(f"Screenshot saved to {filename}")