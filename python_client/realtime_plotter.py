"""
实时绘图组件 - 使用 matplotlib 实现平滑的实时曲线绘制，并与 HTTP 客户端集成。
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

logger = logging.getLogger(__name__)

# 使用英文字体，避免中文字体问题
plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
plt.rcParams["axes.unicode_minus"] = False


class RealtimePlotter:
    """实时绘图器"""

    def __init__(self, master=None, figsize=(12, 8), max_points: int = 100):
        self.master = master
        self.figsize = figsize
        # 只保留最近 max_points 帧，用于控制 X 轴窗口长度
        self.max_points = max_points

        # 数据存储
        self.time_data: List[float] = []
        self.signal_data: List[float] = []
        self.peak_data: List[int] = []
        self.enhanced_peak_data: List[Optional[Dict[str, Any]]] = []

        # 图表相关
        self.fig = None
        self.ax_main = None
        self.ax_peak = None
        self.canvas = None
        self.animation = None
        self.lines: Dict[str, Any] = {}

        # 显示选项
        self.show_grid = True
        self.show_peaks = True
        self.show_enhanced_peaks = True
        # auto_scale 用于控制 X 轴窗口（是否根据数据移动），Y 轴固定 50-150
        self.auto_scale = True

        # 性能统计
        self.update_count = 0
        self.fps = 0.0
        self.last_update_time = time.time()
        self.update_times: List[float] = []

        # 起始时间（用于将时间戳转换为相对时间）
        self.start_time: Optional[datetime] = None

        logger.info("RealtimePlotter initialized")

    def setup_plot(self):
        """设置图表"""
        # 创建主图和子图
        self.fig, (self.ax_main, self.ax_peak) = plt.subplots(
            2, 1, figsize=self.figsize, gridspec_kw={"height_ratios": [3, 1]}
        )

        # 主图 - 信号曲线
        self.ax_main.set_title("Real-time Signal", fontsize=14, fontweight="bold")
        self.ax_main.set_xlabel("Time (seconds)")
        self.ax_main.set_ylabel("Signal Value")
        self.ax_main.grid(True, alpha=0.3)
        self.ax_main.set_xlim(0, 10)
        # 固定 Y 轴范围为 50-150
        self.ax_main.set_ylim(50, 150)

        # 主曲线
        self.lines["signal"], = self.ax_main.plot(
            [], [], "b-", linewidth=1.5, label="Signal", alpha=0.8
        )

        # 基线
        self.lines["baseline"], = self.ax_main.plot(
            [], [], "r--", linewidth=1, label="Baseline", alpha=0.6
        )

        # 简单峰值点
        self.lines["peaks"], = self.ax_main.plot(
            [], [], "ro", markersize=6, label="Peaks", alpha=0.8
        )

        # 增强峰值点（绿 / 红）
        self.lines["enhanced_peaks_green"], = self.ax_main.plot(
            [], [], "go", markersize=8, label="Green Peaks", alpha=0.8
        )
        self.lines["enhanced_peaks_red"], = self.ax_main.plot(
            [], [], "ro", markersize=8, label="Red Peaks", alpha=0.8
        )

        self.ax_main.legend(loc="upper right")

        # 子图 - 峰值信号（0 / 1）
        self.ax_peak.set_title("Peak Signal", fontsize=12)
        self.ax_peak.set_xlabel("Time (seconds)")
        self.ax_peak.set_ylabel("Peak Signal")
        self.ax_peak.grid(True, alpha=0.3)
        self.ax_peak.set_ylim(-0.5, 1.5)
        self.ax_peak.set_yticks([0, 1])
        self.ax_peak.set_yticklabels(["No Peak", "Peak"])

        self.lines["peak_signal"], = self.ax_peak.plot(
            [], [], "g-", linewidth=2, label="Peak Signal"
        )
        self.ax_peak.legend(loc="upper right")

        # 布局与背景
        plt.tight_layout()
        self.fig.patch.set_facecolor("#f0f0f0")

    def setup_canvas(self):
        """设置 Tkinter Canvas"""
        if self.master:
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill="both", expand=True)
        else:
            # 无 Tkinter 容器时，直接使用 matplotlib 默认显示
            plt.show(block=False)

    def update_data(self, data: Dict[str, Any]):
        """更新数据（由 HTTP 客户端轮询时调用）"""
        try:
            # 更新性能统计
            current_time = time.time()
            self.update_count += 1
            update_time = current_time - self.last_update_time
            self.update_times.append(update_time)
            self.last_update_time = current_time

            # 只保留最近 100 次更新时间用于计算 FPS
            if len(self.update_times) > 100:
                self.update_times = self.update_times[-100:]

            # 解析信号值
            timestamp = data.get("timestamp")
            series = data.get("series", [])
            if series:
                signal_value = series[0].get("value", 0.0)
            else:
                signal_value = data.get("signal_value", 0.0)

            peak_signal = data.get("peak_signal")

            # 将时间戳转换为相对时间（秒）
            if timestamp:
                dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                if not self.time_data:
                    self.start_time = dt
                relative_time = (dt - self.start_time).total_seconds()
            else:
                # 没有时间戳时，使用本地时间累积
                if not self.time_data:
                    self.start_time = datetime.fromtimestamp(time.time())
                relative_time = time.time() - self.start_time.timestamp()

            # 追加数据
            self.time_data.append(relative_time)
            self.signal_data.append(float(signal_value))
            self.peak_data.append(int(peak_signal) if peak_signal is not None else 0)

            # 处理增强峰值信息（可选）
            enhanced_peak = data.get("enhanced_peak", {})
            if enhanced_peak:
                self.enhanced_peak_data.append(
                    {
                        "time": relative_time,
                        "value": float(signal_value),
                        "color": enhanced_peak.get("peak_color"),
                        "confidence": float(enhanced_peak.get("peak_confidence", 0.0)),
                    }
                )
            else:
                self.enhanced_peak_data.append(None)

            # 限制数据点数量到最近 max_points 帧
            if len(self.time_data) > self.max_points:
                self.time_data = self.time_data[-self.max_points:]
                self.signal_data = self.signal_data[-self.max_points:]
                self.peak_data = self.peak_data[-self.max_points:]
                self.enhanced_peak_data = self.enhanced_peak_data[-self.max_points:]

        except Exception as e:
            logger.error(f"Error updating plot data: {e}")

    def update_plot(self, frame=None):
        """更新图表（动画回调）"""
        try:
            if not self.time_data:
                return self.lines.values()

            # 主信号曲线
            self.lines["signal"].set_data(self.time_data, self.signal_data)

            # 基线：使用最近 20 个点的均值
            if len(self.signal_data) >= 20:
                baseline = float(np.mean(self.signal_data[-20:]))
                baseline_data = [baseline] * len(self.time_data)
                self.lines["baseline"].set_data(self.time_data, baseline_data)
            else:
                self.lines["baseline"].set_data([], [])

            # 简单峰值点
            if self.show_peaks:
                peak_times = [
                    t for t, p in zip(self.time_data, self.peak_data) if p == 1
                ]
                peak_values = [
                    v for v, p in zip(self.signal_data, self.peak_data) if p == 1
                ]
                self.lines["peaks"].set_data(peak_times, peak_values)
            else:
                self.lines["peaks"].set_data([], [])

            # 增强峰值点（绿 / 红）
            if self.show_enhanced_peaks:
                green_times, green_values = [], []
                red_times, red_values = [], []

                for info in self.enhanced_peak_data:
                    if not info:
                        continue
                    if info.get("color") == "green":
                        green_times.append(info["time"])
                        green_values.append(info["value"])
                    elif info.get("color") == "red":
                        red_times.append(info["time"])
                        red_values.append(info["value"])

                self.lines["enhanced_peaks_green"].set_data(green_times, green_values)
                self.lines["enhanced_peaks_red"].set_data(red_times, red_values)
            else:
                self.lines["enhanced_peaks_green"].set_data([], [])
                self.lines["enhanced_peaks_red"].set_data([], [])

            # 底部峰值信号图
            self.lines["peak_signal"].set_data(self.time_data, self.peak_data)

            # X 轴覆盖当前数据范围（最多 max_points 帧），避免空白
            if self.time_data:
                if len(self.time_data) >= self.max_points:
                    # 帧数 >= max_points 时，只显示最近 max_points 帧
                    x_min = self.time_data[-self.max_points]
                    x_max = self.time_data[-1]
                else:
                    # 帧数 < max_points 时，覆盖当前所有数据范围
                    x_min = self.time_data[0]
                    if len(self.time_data) > 1:
                        x_max = self.time_data[-1]
                    else:
                        # 只有一个点时给一点宽度，避免压成竖线
                        x_max = self.time_data[0] + 1.0
                self.ax_main.set_xlim(x_min, x_max)
                self.ax_peak.set_xlim(x_min, x_max)

            # Y 轴范围固定为 50-150，不根据数据自动缩放
            self.ax_main.set_ylim(50, 150)

            # 更新网格
            self.ax_main.grid(self.show_grid, alpha=0.3)
            self.ax_peak.grid(self.show_grid, alpha=0.3)

            # 计算 FPS
            if self.update_times:
                avg_update_time = np.mean(self.update_times[-10:])
                self.fps = float(1.0 / avg_update_time) if avg_update_time > 0 else 0.0

            return self.lines.values()

        except Exception as e:
            logger.error(f"Error updating plot: {e}")
            return self.lines.values()

    def start_animation(self, interval: int = 50):
        """启动动画（默认 20 FPS）"""
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

    def set_display_options(
        self,
        show_grid: bool = True,
        show_peaks: bool = True,
        show_enhanced_peaks: bool = True,
        auto_scale: bool = True,
    ):
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
            "peaks_detected": int(sum(self.peak_data)),
            "enhanced_peaks_green": len(
                [p for p in self.enhanced_peak_data if p and p.get("color") == "green"]
            ),
            "enhanced_peaks_red": len(
                [p for p in self.enhanced_peak_data if p and p.get("color") == "red"]
            ),
            "signal_range": {
                "min": float(min(self.signal_data)) if self.signal_data else 0.0,
                "max": float(max(self.signal_data)) if self.signal_data else 0.0,
                "avg": float(np.mean(self.signal_data)) if self.signal_data else 0.0,
            },
        }

    def save_screenshot(self, filename: str):
        """保存截图"""
        if self.fig:
            self.fig.savefig(filename, dpi=150, bbox_inches="tight")
            logger.info(f"Screenshot saved to {filename}")

