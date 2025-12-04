"""
基于HTTP的Python客户端实时绘图
使用HTTP轮询获取实时数据，实现与Web前端相同的实时曲线绘制
"""

import json
import logging
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext
import requests
from typing import Dict, Any, Optional
from PIL import Image, ImageTk
import base64
import io
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

from realtime_plotter import RealtimePlotter

# 设置logger
logger = logging.getLogger(__name__)


class HTTPRealtimeClient:
    """基于HTTP的实时客户端"""

    def __init__(self, base_url: str = "http://localhost:8421", password: str = "31415"):
        self.base_url = base_url
        self.password = password
        self.session = requests.Session()

        # 状态变量
        self.connected = False
        self.detection_running = False
        self.polling_running = False
        self.polling_thread: Optional[threading.Thread] = None

        # 数据更新控制
        self.polling_interval = 0.05  # 50ms (20 FPS)
        self.data_count = 0
        self.last_update_time = 0

        # 绘图器
        self.plotter: Optional[RealtimePlotter] = None

        logger.info(f"HTTPRealtimeClient initialized for {base_url}")

    def test_connection(self) -> bool:
        """测试服务器连接"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info("Server connection successful")
                return True
            else:
                logger.error(f"Server returned status code: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def get_system_status(self) -> Optional[Dict[str, Any]]:
        """获取系统状态"""
        try:
            response = self.session.get(f"{self.base_url}/status", timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return None

    def get_realtime_data(self) -> Optional[Dict[str, Any]]:
        """获取实时数据"""
        try:
            response = self.session.get(f"{self.base_url}/data/realtime?count=1", timeout=3)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Failed to get realtime data: {e}")
            return None

    def send_control_command(self, command: str) -> Optional[Dict[str, Any]]:
        """发送控制命令"""
        try:
            data = {
                "command": command,
                "password": self.password
            }
            response = self.session.post(f"{self.base_url}/control", data=data, timeout=5)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Control command failed: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Failed to send control command: {e}")
            return None

    def start_polling(self):
        """开始数据轮询"""
        if self.polling_running:
            logger.warning("Polling is already running")
            return

        self.polling_running = True
        self.polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.polling_thread.start()
        logger.info("Started data polling")

    def stop_polling(self):
        """停止数据轮询"""
        if not self.polling_running:
            return

        self.polling_running = False
        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=2)

        logger.info("Stopped data polling")

    def _polling_loop(self):
        """轮询循环"""
        while self.polling_running:
            try:
                # 获取实时数据
                data = self.get_realtime_data()
                if data and data.get("type") == "realtime_data":
                    # 更新绘图器
                    if self.plotter:
                        self.plotter.update_data(data)

                    self.data_count += 1
                    self.last_update_time = time.time()

                # 等待下一次轮询
                time.sleep(self.polling_interval)

            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                time.sleep(1)  # 出错时等待1秒后重试

    def start_detection(self) -> bool:
        """开始检测"""
        response = self.send_control_command("start_detection")
        if response and response.get("status") == "success":
            self.detection_running = True
            logger.info("Detection started successfully")
            return True
        else:
            logger.error("Failed to start detection")
            return False

    def stop_detection(self) -> bool:
        """停止检测"""
        response = self.send_control_command("stop_detection")
        if response and response.get("status") == "success":
            self.detection_running = False
            logger.info("Detection stopped successfully")
            return True
        else:
            logger.error("Failed to stop detection")
            return False

    def get_status(self) -> Dict[str, Any]:
        """获取客户端状态"""
        return {
            "connected": self.connected,
            "detection_running": self.detection_running,
            "polling_running": self.polling_running,
            "data_count": self.data_count,
            "base_url": self.base_url,
            "polling_interval": self.polling_interval
        }


class HTTPRealtimeClientUI(tk.Tk):
    """基于HTTP的Python客户端UI"""

    def __init__(self):
        super().__init__()
        self.title("NewFEM Python Client - HTTP + Real-time Plotting")
        self.geometry("1200x800")

        # HTTP客户端
        self.http_client: HTTPRealtimeClient = None

        # 状态变量
        self.connected = False

        # 构建UI
        self._build_widgets()
        self._setup_plotter()

        # 绑定关闭事件
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # 启动状态更新循环
        self._start_status_update()

    def _build_widgets(self):
        """构建UI组件"""
        # 顶部连接配置
        conn_frame = ttk.LabelFrame(self, text="HTTP连接配置")
        conn_frame.pack(fill="x", padx=8, pady=4)

        ttk.Label(conn_frame, text="后端URL:").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        self.entry_base_url = ttk.Entry(conn_frame, width=40)
        self.entry_base_url.grid(row=0, column=1, sticky="w", padx=4, pady=2)
        self.entry_base_url.insert(0, "http://localhost:8421")

        ttk.Label(conn_frame, text="密码:").grid(row=0, column=2, sticky="e", padx=4, pady=2)
        self.entry_password = ttk.Entry(conn_frame, width=12, show="*")
        self.entry_password.grid(row=0, column=3, sticky="w", padx=4, pady=2)
        self.entry_password.insert(0, "31415")

        # 连接按钮
        self.btn_connect = ttk.Button(conn_frame, text="连接", command=self._toggle_connection)
        self.btn_connect.grid(row=0, column=4, padx=8, pady=2)

        # 连接状态指示器
        self.status_var = tk.StringVar(value="未连接")
        self.status_label = ttk.Label(conn_frame, textvariable=self.status_var, foreground="red")
        self.status_label.grid(row=0, column=5, padx=4, pady=2)

        # 控制面板
        control_frame = ttk.LabelFrame(self, text="控制面板")
        control_frame.pack(fill="x", padx=8, pady=4)

        self.btn_start = ttk.Button(control_frame, text="开始检测", command=self._start_detection, state="disabled")
        self.btn_start.pack(side="left", padx=8, pady=4)

        self.btn_stop = ttk.Button(control_frame, text="停止检测", command=self._stop_detection, state="disabled")
        self.btn_stop.pack(side="left", padx=8, pady=4)

        self.btn_clear = ttk.Button(control_frame, text="清除数据", command=self._clear_data, state="disabled")
        self.btn_clear.pack(side="left", padx=8, pady=4)

        self.btn_save = ttk.Button(control_frame, text="保存截图", command=self._save_screenshot, state="disabled")
        self.btn_save.pack(side="left", padx=8, pady=4)

        self.btn_capture = ttk.Button(control_frame, text="截取曲线", command=self._capture_curve, state="disabled")
        self.btn_capture.pack(side="left", padx=8, pady=4)

        # 主框架 - 左侧信息，右侧图表
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=8, pady=4)

        # 左侧信息面板
        info_frame = ttk.LabelFrame(main_frame, text="实时信息")
        info_frame.pack(side="left", fill="y", padx=(0, 8))

        # 状态信息
        status_info = ttk.Frame(info_frame)
        status_info.pack(fill="x", padx=8, pady=4)

        ttk.Label(status_info, text="数据点数:").grid(row=0, column=0, sticky="w", pady=2)
        self.data_count_label = ttk.Label(status_info, text="0")
        self.data_count_label.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=2)

        ttk.Label(status_info, text="更新FPS:").grid(row=1, column=0, sticky="w", pady=2)
        self.fps_label = ttk.Label(status_info, text="0")
        self.fps_label.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=2)

        ttk.Label(status_info, text="检测状态:").grid(row=2, column=0, sticky="w", pady=2)
        self.detection_status_label = ttk.Label(status_info, text="未运行")
        self.detection_status_label.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=2)

        ttk.Label(status_info, text="连接状态:").grid(row=3, column=0, sticky="w", pady=2)
        self.connection_status_label = ttk.Label(status_info, text="未连接")
        self.connection_status_label.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=2)

        ttk.Label(status_info, text="轮询状态:").grid(row=4, column=0, sticky="w", pady=2)
        self.polling_status_label = ttk.Label(status_info, text="未轮询")
        self.polling_status_label.grid(row=4, column=1, sticky="w", padx=(8, 0), pady=2)

        # 分隔线
        ttk.Separator(info_frame, orient="horizontal").pack(fill="x", pady=8)

        # ROI截图显示面板
        roi_frame = ttk.LabelFrame(info_frame, text="ROI Screenshot")
        roi_frame.pack(fill="x", padx=8, pady=4)

        # 创建ROI截图标签
        self.roi_label = ttk.Label(roi_frame, text="Waiting for ROI data...",
                                   relief="sunken", background="white")
        self.roi_label.pack(fill="x", pady=4)

        # ROI信息
        roi_info = ttk.Frame(roi_frame)
        roi_info.pack(fill="x", padx=4, pady=2)

        ttk.Label(roi_info, text="分辨率:").pack(side="left")
        self.roi_resolution_label = ttk.Label(roi_info, text="N/A")
        self.roi_resolution_label.pack(side="left", padx=(8, 16))

        ttk.Label(roi_info, text="灰度值:").pack(side="left")
        self.roi_gray_value_label = ttk.Label(roi_info, text="N/A")
        self.roi_gray_value_label.pack(side="left", padx=(8, 16))

        # 日志面板
        log_frame = ttk.LabelFrame(info_frame, text="日志")
        log_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=40)
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

        # 右侧图表区域
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True)

        # 上方图表框架
        plot_frame = ttk.LabelFrame(right_frame, text="Real-time Charts")
        plot_frame.pack(fill="both", expand=True, pady=(0, 4))

        self.plot_frame = plot_frame

        # 下方截取曲线显示框架
        captured_frame = ttk.LabelFrame(right_frame, text="Captured Curve")
        captured_frame.pack(fill="both", expand=False, pady=(4, 0))

        # 创建截取曲线显示区域
        self.captured_label = ttk.Label(captured_frame, text="No captured curve yet. Click '截取曲线' to capture data.",
                                      relief="sunken", background="white")
        self.captured_label.pack(fill="x", padx=4, pady=4)

        # 截取信息
        capture_info = ttk.Frame(captured_frame)
        capture_info.pack(fill="x", padx=4, pady=2)

        ttk.Label(capture_info, text="数据点数:").pack(side="left")
        self.captured_count_label = ttk.Label(capture_info, text="N/A")
        self.captured_count_label.pack(side="left", padx=(8, 16))

        ttk.Label(capture_info, text="数据源:").pack(side="left")
        self.captured_source_label = ttk.Label(capture_info, text="N/A")
        self.captured_source_label.pack(side="left", padx=(8, 16))

        # 清除截取按钮
        self.btn_clear_capture = ttk.Button(capture_info, text="清除截取", command=self._clear_capture, state="disabled")
        self.btn_clear_capture.pack(side="right", padx=4)

    def _setup_plotter(self):
        """设置绘图器"""
        try:
            import matplotlib.pyplot as plt
            self.plotter = RealtimePlotter(master=self.plot_frame, figsize=(10, 6))
            self.plotter.setup_plot()
            self.plotter.setup_canvas()

            # 启动动画
            self.plotter.start_animation(interval=50)  # 20 FPS

            # 自动启动连接和数据收集
            self.after(1000, self.auto_connect_and_start)

        except ImportError:
            no_mpl_label = ttk.Label(self.plot_frame, text="matplotlib未安装，无法显示图表")
            no_mpl_label.pack(expand=True)
            self.plotter = None

    def auto_connect_and_start(self):
        """自动连接并启动数据收集"""
        try:
            # 更新状态显示
            self.status_var.set("Connecting...")
            self.status_label.config(foreground="blue")
            self._log("Auto-connecting to server...")

            # 使用输入框中的URL和密码
            base_url = self.entry_base_url.get()
            password = self.entry_password.get()

            # 创建HTTP客户端
            self.http_client = HTTPRealtimeClient(base_url=base_url, password=password)

            # 测试连接
            if self.http_client.test_connection():
                self.connected = True
                self._update_connection_status()
                self._log("Auto-connection successful!")

                # 配置ROI
                self._log("Configuring ROI...")
                session = self.http_client.session
                roi_data = {"x1": 0, "y1": 0, "x2": 200, "y2": 150, "password": password}
                response = session.post(f"{self.http_client.base_url}/roi/config", data=roi_data, timeout=5)

                if response.status_code == 200:
                    self._log("ROI configured successfully!")
                else:
                    self._log(f"ROI configuration failed: {response.status_code}")

                # 启动检测
                self._log("Starting detection...")
                if self.http_client.start_detection():
                    self._log("Detection started successfully!")

                    # 启动数据轮询
                    self.http_client.start_polling()

                    # 设置绘图器到HTTP客户端
                    self.http_client.plotter = self.plotter

                    # 启动ROI截图更新
                    self.after(2000, self.start_roi_updates)  # 2秒后开始更新ROI截图

                    # 更新按钮状态
                    self.btn_connect.config(text="Disconnect")
                    self._update_detection_status()

                    self._log("Auto-setup complete! Data collection started.")
                    self._log("ROI screenshot updates started (2 FPS).")

                else:
                    self._log("Failed to start detection")

            else:
                raise Exception("Server connection failed")

        except Exception as e:
            self._log(f"Auto-connection failed: {str(e)}", "ERROR")
            self.status_var.set("Auto-connect failed")
            self.status_label.config(foreground="red")

    def _toggle_connection(self):
        """切换连接状态"""
        if not self.connected:
            self._connect()
        else:
            self._disconnect()

    def _connect(self):
        """连接到服务器"""
        try:
            base_url = self.entry_base_url.get()
            password = self.entry_password.get()

            # 创建HTTP客户端
            self.http_client = HTTPRealtimeClient(base_url=base_url, password=password)

            # 测试连接
            if self.http_client.test_connection():
                self.connected = True
                self._update_connection_status()

                # 启动数据轮询
                self.http_client.start_polling()

                self._log("连接成功！")
                messagebox.showinfo("连接成功", "已连接到NewFEM服务器")
            else:
                raise Exception("服务器连接测试失败")

        except Exception as e:
            messagebox.showerror("连接错误", f"连接失败: {str(e)}")
            self._log(f"连接失败: {str(e)}", "ERROR")

    def _disconnect(self):
        """断开连接"""
        if self.http_client:
            self.http_client.stop_polling()
            self.http_client = None

        self.connected = False
        self._update_connection_status()

    def _update_connection_status(self):
        """更新连接状态显示"""
        if self.connected:
            self.status_var.set("已连接")
            self.status_label.config(foreground="green")
            self.connection_status_label.config(text="已连接", foreground="green")
            self.polling_status_label.config(text="轮询中", foreground="blue")
            self.btn_connect.config(text="断开连接", state="normal")
            self.btn_start.config(state="normal")
            self.btn_clear.config(state="normal")
            self.btn_save.config(state="normal" if self.plotter else "disabled")
            self.btn_capture.config(state="normal")
            self.btn_clear_capture.config(state="normal")
        else:
            self.status_var.set("未连接")
            self.status_label.config(foreground="red")
            self.connection_status_label.config(text="未连接", foreground="red")
            self.polling_status_label.config(text="未轮询", foreground="red")
            self.btn_connect.config(text="连接", state="normal")
            self.btn_start.config(state="disabled")
            self.btn_stop.config(state="disabled")
            self.btn_clear.config(state="disabled")
            self.btn_save.config(state="disabled")
            self.btn_capture.config(state="disabled")
            self.btn_clear_capture.config(state="disabled")

    def _start_detection(self):
        """开始检测"""
        if self.http_client:
            if self.http_client.start_detection():
                self._update_detection_status()
                self._log("开始检测命令发送成功")
            else:
                messagebox.showerror("错误", "开始检测失败")
                self._log("开始检测失败", "ERROR")

    def _stop_detection(self):
        """停止检测"""
        if self.http_client:
            if self.http_client.stop_detection():
                self._update_detection_status()
                self._log("停止检测命令发送成功")
            else:
                messagebox.showerror("错误", "停止检测失败")
                self._log("停止检测失败", "ERROR")

    def _update_detection_status(self):
        """更新检测状态"""
        if self.http_client and self.http_client.detection_running:
            self.detection_status_label.config(text="运行中", foreground="green")
            self.btn_start.config(state="disabled")
            self.btn_stop.config(state="normal")
        else:
            self.detection_status_label.config(text="未运行", foreground="red")
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")

    def _clear_data(self):
        """清除数据"""
        if self.plotter:
            self.plotter.clear_data()
            if self.http_client:
                self.http_client.data_count = 0
                self.data_count_label.config(text="0")
                self.fps_label.config(text="0")
            self._log("数据已清除")

    def _save_screenshot(self):
        """保存截图"""
        if self.plotter:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
            )
            if filename:
                self.plotter.save_screenshot(filename)
                self._log(f"截图已保存: {filename}")
                messagebox.showinfo("成功", f"截图已保存到: {filename}")

    def _start_status_update(self):
        """启动状态更新循环"""
        def update_status():
            try:
                if self.connected and self.http_client:
                    # 更新信息显示
                    self.data_count_label.config(text=str(self.http_client.data_count))

                    # 更新检测状态
                    self._update_detection_status()

                    # 更新FPS（如果有绘图器）
                    if self.plotter:
                        stats = self.plotter.get_statistics()
                        self.fps_label.config(text=f"{stats['fps']:.1f}")

                # 每秒更新一次
                self.after(1000, update_status)
            except Exception as e:
                self._log(f"状态更新错误: {str(e)}", "ERROR")
                self.after(5000, update_status)  # 出错时5秒后重试

        self.after(1000, update_status)

    def start_roi_updates(self):
        """开始ROI截图更新"""
        if self.connected and self.http_client:
            self.update_roi_screenshot()

    def update_roi_screenshot(self):
        """更新ROI截图显示"""
        if not self.connected or not self.http_client:
            return

        try:
            # 获取ROI数据
            response = self.http_client.session.get(f"{self.http_client.base_url}/data/realtime?count=1", timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get("type") == "realtime_data":
                    roi_data = data.get("roi_data", {})

                    if roi_data and "pixels" in roi_data:
                        # 更新ROI截图
                        base64_image = roi_data["pixels"]
                        if base64_image.startswith("data:image/png;base64,"):
                            # 提取base64数据
                            base64_data = base64_image.split("data:image/png;base64,")[1]

                            # 将base64转换为PhotoImage
                            image_data = base64.b64decode(base64_data)
                            image = Image.open(io.BytesIO(image_data))

                            # 调整图像大小以适应显示区域
                            image = image.resize((200, 150), Image.Resampling.LANCZOS)
                            photo = ImageTk.PhotoImage(image)

                            # 更新标签显示
                            self.roi_label.config(image=photo, text="")
                            self.roi_label.image = photo  # 保持引用避免垃圾回收

                            # 更新ROI信息
                            width = roi_data.get("width", 0)
                            height = roi_data.get("height", 0)
                            gray_value = roi_data.get("gray_value", 0)

                            self.roi_resolution_label.config(text=f"{width}x{height}")
                            self.roi_gray_value_label.config(text=f"{gray_value:.1f}")

                        else:
                            self.roi_label.config(text="Invalid ROI data format", image="")
                    else:
                        self.roi_label.config(text="No ROI data available", image="")
                        self.roi_resolution_label.config(text="N/A")
                        self.roi_gray_value_label.config(text="N/A")
                else:
                    self.roi_label.config(text="Invalid data type", image="")
            else:
                self.roi_label.config(text="Failed to get ROI data", image="")

        except Exception as e:
            self.roi_label.config(text=f"Error: {str(e)}", image="")
            print(f"ROI update error: {e}")

        # 每500ms更新一次 (2 FPS)
        if self.connected:
            self.after(500, self.update_roi_screenshot)

    def _capture_curve(self):
        """截取曲线数据"""
        if not self.connected or not self.http_client:
            messagebox.showerror("错误", "请先连接到服务器")
            return

        try:
            self._log("Starting curve capture...")
            self.btn_capture.config(state="disabled", text="截取中...")

            # 使用ROI窗口截取API获取带波峰检测的数据
            response = self.http_client.session.get(
                f"{self.http_client.base_url}/data/roi-window-capture-with-peaks?count=100",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    # 获取截取的数据
                    captured_data = data.get("data", [])
                    peaks = data.get("peaks", [])

                    if captured_data:
                        self._log(f"Curve capture successful! Got {len(captured_data)} data points with {len(peaks)} peaks")
                        self._display_captured_curve(captured_data, peaks)

                        # 更新截取信息
                        self.captured_count_label.config(text=str(len(captured_data)))
                        self.captured_source_label.config(text="ROI数据")

                        # 启用清除按钮
                        self.btn_clear_capture.config(state="normal")

                        # 成功提示
                        messagebox.showinfo("成功", f"曲线截取成功！\n数据点数: {len(captured_data)}\n波峰数: {len(peaks)}")
                    else:
                        raise Exception("No captured data received")
                else:
                    raise Exception(data.get("error", "Unknown error"))
            else:
                raise Exception(f"Server error: {response.status_code}")

        except Exception as e:
            self._log(f"Curve capture failed: {str(e)}", "ERROR")
            messagebox.showerror("截取失败", f"曲线截取失败: {str(e)}")
        finally:
            self.btn_capture.config(state="normal", text="截取曲线")

    def _display_captured_curve(self, data_points, peaks):
        """显示截取的曲线"""
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import numpy as np

            # 创建新图表
            fig, ax = plt.subplots(figsize=(10, 4), dpi=100)
            fig.patch.set_facecolor('white')

            # 提取时间和数值
            times = [point.get("t", 0) for point in data_points]
            values = [point.get("value", 0) for point in data_points]

            if times and values:
                # 绘制曲线
                ax.plot(times, values, 'b-', linewidth=2, label='Captured Signal')

                # 绘制基线
                if values:
                    baseline = np.mean(values)
                    baseline_line = [baseline] * len(times)
                    ax.plot(times, baseline_line, 'r--', linewidth=1, alpha=0.6, label=f'Baseline={baseline:.1f}')

                # 标记波峰
                if peaks:
                    peak_times = [peak.get("t", 0) for peak in peaks]
                    peak_values = [peak.get("value", 0) for peak in peaks]
                    peak_colors = []

                    # 根据波峰颜色分类
                    for peak in peaks:
                        if peak.get("peak_color") == "green":
                            peak_colors.append('green')
                        elif peak.get("peak_color") == "red":
                            peak_colors.append('red')
                        else:
                            peak_colors.append('orange')

                    # 绘制波峰点
                    for i, (t, v, color) in enumerate(zip(peak_times, peak_values, peak_colors)):
                        ax.scatter([t], [v], c=color, s=50, zorder=5)

                ax.set_title("Captured Curve with Peak Detection", fontsize=12, fontweight='bold')
                ax.set_xlabel("Time (seconds)")
                ax.set_ylabel("Signal Value")
                ax.grid(True, alpha=0.3)
                ax.legend()

                # 自动调整坐标轴
                ax.set_xlim(min(times) - 0.1, max(times) + 0.1)
                if values:
                    ax.set_ylim(min(values) - 2, max(values) + 2)

                plt.tight_layout()

                # 简化显示：直接嵌入canvas到标签中
                canvas = FigureCanvasTkAgg(fig, master=self.captured_label)
                canvas.draw()
                canvas.get_tk_widget().pack(fill='both', expand=True)

                # 保存引用
                self.captured_canvas = canvas
                self.captured_fig = fig

        except Exception as e:
            self._log(f"Error displaying captured curve: {str(e)}", "ERROR")
            self.captured_label.config(text=f"显示错误: {str(e)}", image="")

    def _clear_capture(self):
        """清除截取的曲线"""
        # 清除canvas
        if hasattr(self, 'captured_canvas'):
            self.captured_canvas.get_tk_widget().destroy()
            self.captured_canvas = None
        if hasattr(self, 'captured_fig'):
            plt.close(self.captured_fig)
            self.captured_fig = None

        self.captured_label.config(text="No captured curve yet. Click '截取曲线' to capture data.", image="")
        self.captured_label.image = None
        self.captured_count_label.config(text="N/A")
        self.captured_source_label.config(text="N/A")
        self.btn_clear_capture.config(state="disabled")
        self._log("Captured curve cleared")

    def _log(self, message: str, level: str = "INFO"):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}\n"

        self.log_text.insert("end", log_entry)
        self.log_text.see("end")  # 自动滚动到底部

        # 限制日志行数
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 1000:
            self.log_text.delete("1.0", "100.0")

    def _on_closing(self):
        """窗口关闭事件"""
        try:
            # 断开连接
            self._disconnect()

            # 停止绘图动画
            if self.plotter:
                self.plotter.stop_animation()

            # 销毁窗口
            self.destroy()

        except Exception as e:
            print(f"Error during cleanup: {e}")
            self.destroy()


def main():
    """主函数"""
    app = HTTPRealtimeClientUI()
    app.mainloop()


if __name__ == "__main__":
    main()