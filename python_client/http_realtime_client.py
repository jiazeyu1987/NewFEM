"""
基于HTTP的Python客户端实时绘图
使用HTTP轮询获取实时数据，实现与Web前端相同的实时曲线绘制
"""

import json
import logging
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext, StringVar
import requests
from typing import Dict, Any, Optional
from PIL import Image, ImageTk
import base64
import io
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from local_config_loader import LocalConfigLoader

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

        # 参数设置面板
        config_frame = ttk.LabelFrame(info_frame, text="参数设置")
        config_frame.pack(fill="x", padx=8, pady=4)

        # ROI设置子面板
        roi_config_frame = ttk.LabelFrame(config_frame, text="ROI配置")
        roi_config_frame.pack(fill="x", padx=8, pady=4)

        # ROI坐标设置
        roi_coords = ttk.Frame(roi_config_frame)
        roi_coords.pack(fill="x", padx=8, pady=2)

        ttk.Label(roi_coords, text="X1:").grid(row=0, column=0, sticky="w")
        self.roi_x1_var = tk.StringVar(value="0")
        ttk.Entry(roi_coords, textvariable=self.roi_x1_var, width=8).grid(row=0, column=1, padx=2)

        ttk.Label(roi_coords, text="Y1:").grid(row=0, column=2, sticky="w", padx=(10,0))
        self.roi_y1_var = tk.StringVar(value="0")
        ttk.Entry(roi_coords, textvariable=self.roi_y1_var, width=8).grid(row=0, column=3, padx=2)

        ttk.Label(roi_coords, text="X2:").grid(row=1, column=0, sticky="w")
        self.roi_x2_var = tk.StringVar(value="200")
        ttk.Entry(roi_coords, textvariable=self.roi_x2_var, width=8).grid(row=1, column=1, padx=2)

        ttk.Label(roi_coords, text="Y2:").grid(row=1, column=2, sticky="w", padx=(10,0))
        self.roi_y2_var = tk.StringVar(value="150")
        ttk.Entry(roi_coords, textvariable=self.roi_y2_var, width=8).grid(row=1, column=3, padx=2)

        # ROI帧率设置
        roi_fps_frame = ttk.Frame(roi_config_frame)
        roi_fps_frame.pack(fill="x", padx=8, pady=2)

        ttk.Label(roi_fps_frame, text="ROI帧率:").pack(side="left")
        self.roi_fps_var = tk.StringVar(value="2")
        fps_spinbox = ttk.Spinbox(roi_fps_frame, from_=1, to=60, textvariable=self.roi_fps_var, width=8)
        fps_spinbox.pack(side="left", padx=(8, 4))
        ttk.Label(roi_fps_frame, text="FPS").pack(side="left")

        # 波峰检测设置子面板
        peak_config_frame = ttk.LabelFrame(config_frame, text="波峰检测设置")
        peak_config_frame.pack(fill="x", padx=8, pady=4)

        # 绝对阈值
        threshold_frame = ttk.Frame(peak_config_frame)
        threshold_frame.pack(fill="x", padx=8, pady=2)

        ttk.Label(threshold_frame, text="绝对阈值:").pack(side="left")
        self.peak_threshold_var = tk.StringVar(value="105.0")
        ttk.Entry(threshold_frame, textvariable=self.peak_threshold_var, width=10).pack(side="left", padx=(8, 4))
        ttk.Label(threshold_frame, text="灰度值").pack(side="left")

        # 边界帧数
        margin_frame = ttk.Frame(peak_config_frame)
        margin_frame.pack(fill="x", padx=8, pady=2)

        ttk.Label(margin_frame, text="边界帧数:").pack(side="left")
        self.peak_margin_var = tk.StringVar(value="5")
        ttk.Spinbox(margin_frame, from_=1, to=20, textvariable=self.peak_margin_var, width=8).pack(side="left", padx=(8, 4))
        ttk.Label(margin_frame, text="帧").pack(side="left")

        # 差值阈值
        diff_frame = ttk.Frame(peak_config_frame)
        diff_frame.pack(fill="x", padx=8, pady=2)

        ttk.Label(diff_frame, text="差值阈值:").pack(side="left")
        self.peak_diff_var = tk.StringVar(value="2.1")
        ttk.Entry(diff_frame, textvariable=self.peak_diff_var, width=10).pack(side="left", padx=(8, 4))

        # 应用配置按钮
        config_buttons = ttk.Frame(config_frame)
        config_buttons.pack(fill="x", padx=8, pady=4)

        ttk.Button(config_buttons, text="应用ROI配置", command=self._apply_roi_config).pack(side="left", padx=4)
        ttk.Button(config_buttons, text="应用波峰配置", command=self._apply_peak_config).pack(side="left", padx=4)
        ttk.Button(config_buttons, text="保存配置", command=self._save_config).pack(side="left", padx=4)
        ttk.Button(config_buttons, text="加载配置", command=self._load_config).pack(side="left", padx=4)

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

            # 首先加载本地配置（无需服务器连接）
            self._log("🔄 自动加载本地配置文件...")
            local_config_loaded = self._load_local_config()

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

                # 如果本地配置加载失败，尝试从服务器加载配置
                if not local_config_loaded:
                    self._log("🔄 本地配置加载失败，尝试从服务器加载配置...")
                    config_loaded = self._auto_load_config()
                    if config_loaded:
                        self._log("✅ 服务器配置加载成功，将应用配置参数")
                    else:
                        self._log("⚠️ 服务器配置加载失败，使用默认值")
                else:
                    self._log("✅ 本地配置加载成功，已应用到UI界面")

                # 配置ROI（使用当前UI中的值或默认值）
                self._log("Configuring ROI...")
                session = self.http_client.session

                # 从UI获取ROI参数
                try:
                    roi_x1 = int(self.roi_x1_var.get())
                    roi_y1 = int(self.roi_y1_var.get())
                    roi_x2 = int(self.roi_x2_var.get())
                    roi_y2 = int(self.roi_y2_var.get())
                except ValueError:
                    # 如果UI值无效，使用默认值
                    roi_x1, roi_y1 = 0, 0
                    roi_x2, roi_y2 = 200, 150

                roi_data = {
                    "x1": roi_x1,
                    "y1": roi_y1,
                    "x2": roi_x2,
                    "y2": roi_y2,
                    "password": password
                }
                response = session.post(f"{self.http_client.base_url}/roi/config", data=roi_data, timeout=5)

                if response.status_code == 200:
                    self._log(f"ROI configuration successful: ({roi_x1}, {roi_y1}) → ({roi_x2}, {roi_y2})")
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

            # 使用ROI窗口截取API获取带波峰检测的数据，强制刷新缓存
            response = self.http_client.session.get(
                f"{self.http_client.base_url}/data/roi-window-capture-with-peaks?count=100&force_refresh=true",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    # 获取截取的数据 - 适配服务器返回的数据结构
                    captured_data = data.get("series", [])
                    peak_results = data.get("peak_detection_results", {})

                    # 将波峰数据转换为客户端期望的格式
                    peaks = []
                    green_peaks = peak_results.get("green_peaks", [])
                    red_peaks = peak_results.get("red_peaks", [])

                    # 转换波峰数据格式
                    for peak_info in green_peaks:
                        if len(peak_info) >= 2 and peak_info[0] < len(captured_data):
                            peaks.append({
                                't': captured_data[peak_info[0]]['t'],
                                'value': captured_data[peak_info[0]]['gray_value'],
                                'peak_color': 'green'
                            })

                    for peak_info in red_peaks:
                        if len(peak_info) >= 2 and peak_info[0] < len(captured_data):
                            peaks.append({
                                't': captured_data[peak_info[0]]['t'],
                                'value': captured_data[peak_info[0]]['gray_value'],
                                'peak_color': 'red'
                            })

                    if captured_data:
                        # 添加调试信息验证修复效果
                        times = [point.get("t", 0) for point in captured_data]
                        values = [point.get("gray_value", point.get("value", 0)) for point in captured_data]

                        if times and values:
                            time_range = max(times) - min(times) if len(times) > 1 else 0
                            value_range = max(values) - min(values) if len(values) > 1 else 0
                            self._log(f"DEBUG: Time range: {time_range:.3f}s, Value range: {value_range:.2f}")
                            self._log(f"DEBUG: Time span: [{min(times):.3f}, {max(times):.3f}], Value span: [{min(values):.2f}, {max(values):.2f}]")

                        self._log(f"Curve capture successful! Got {len(captured_data)} data points with {len(peaks)} peaks")
                        self._display_captured_curve(captured_data, peaks)

                        # 更新截取信息
                        self.captured_count_label.config(text=str(len(captured_data)))
                        self.captured_source_label.config(text="ROI数据")

                        # 启用清除按钮
                        self.btn_clear_capture.config(state="normal")

                        # 成功日志记录（不显示弹框）
                        self._log(f"✅ 曲线截取成功！数据点数: {len(captured_data)}, 波峰数: {len(peaks)}")
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

            # 首先清理之前的画布 - 修复第二次截取无法显示的关键问题
            self._clear_capture()

            # 创建新图表
            fig, ax = plt.subplots(figsize=(10, 4), dpi=100)
            fig.patch.set_facecolor('white')

            # 提取时间和数值 - 适配服务器返回的数据格式
            times = [point.get("t", 0) for point in data_points]
            values = [point.get("gray_value", point.get("value", 0)) for point in data_points]

            self._log(f"DEBUG: Preparing to display curve with {len(times)} points")
            self._log(f"DEBUG: Data validation - times count: {len(times)}, values count: {len(values)}")

            # 验证数据完整性
            if len(times) != len(values):
                raise ValueError(f"Data length mismatch: {len(times)} times vs {len(values)} values")

            if not times or not values:
                raise ValueError("No valid data points to display")

            # 验证数据范围
            if len(times) > 0 and len(values) > 0:
                # 绘制曲线
                ax.plot(times, values, 'b-', linewidth=2, label='Captured Signal')

                # 强制设置Y轴范围，确保小的灰度变化能够清晰显示
                min_val = min(values)
                max_val = max(values)
                value_range = max_val - min_val

                if value_range < 10:  # 如果数据范围太小，强制扩展显示范围
                    center = (min_val + max_val) / 2
                    expanded_range = 5  # 至少显示5的范围
                    ax.set_ylim(center - expanded_range/2, center + expanded_range/2)
                else:
                    # 否则使用正常范围并稍微扩展
                    padding = value_range * 0.1
                    ax.set_ylim(min_val - padding, max_val + padding)

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

                # 清理标签内容并嵌入新的canvas
                self.captured_label.config(text="")

                # 创建并嵌入canvas - 添加验证
                self._log("DEBUG: Creating FigureCanvasTkAgg...")
                canvas = FigureCanvasTkAgg(fig, master=self.captured_label)

                # 验证canvas创建是否成功
                if canvas is None:
                    raise RuntimeError("Failed to create matplotlib canvas")

                # 绘制图表
                self._log("DEBUG: Drawing canvas...")
                canvas.draw()

                # 获取widget并验证
                widget = canvas.get_tk_widget()
                if widget is None:
                    raise RuntimeError("Failed to get tkinter widget from canvas")

                # 嵌入widget
                self._log("DEBUG: Packing canvas widget...")
                widget.pack(fill='both', expand=True)

                # 验证widget是否正确嵌入
                self.after(100, lambda: self._verify_canvas_display(canvas, fig))

                # 保存引用
                self.captured_canvas = canvas
                self.captured_fig = fig

                self._log(f"DEBUG: Canvas created and embedded successfully")

        except Exception as e:
            self._log(f"Error displaying captured curve: {str(e)}", "ERROR")
            self.captured_label.config(text=f"显示错误: {str(e)}", image="")

    def _verify_canvas_display(self, canvas, fig):
        """验证canvas是否正确显示"""
        try:
            if canvas is None:
                self._log("ERROR: Canvas is None after creation", "ERROR")
                return

            widget = canvas.get_tk_widget()
            if widget is None:
                self._log("ERROR: Widget is None after canvas creation", "ERROR")
                return

            # 检查widget是否可见
            try:
                if widget.winfo_viewable():
                    self._log("DEBUG: Canvas widget is visible and properly displayed")
                else:
                    self._log("WARNING: Canvas widget is not visible", "WARNING")
            except Exception as e:
                self._log(f"DEBUG: Could not verify widget visibility: {e}")

            # 检查widget尺寸
            try:
                width = widget.winfo_width()
                height = widget.winfo_height()
                self._log(f"DEBUG: Canvas widget size: {width}x{height}")
            except Exception as e:
                self._log(f"DEBUG: Could not get widget size: {e}")

        except Exception as e:
            self._log(f"Error in canvas verification: {str(e)}", "ERROR")

    def _clear_capture(self):
        """清除截取的曲线"""
        try:
            import matplotlib.pyplot as plt

            self._log("DEBUG: Clearing previous captured curve...")

            # 清除canvas - 修复关键：确保彻底清理
            if hasattr(self, 'captured_canvas') and self.captured_canvas is not None:
                try:
                    # 获取canvas的tkinter widget并销毁
                    widget = self.captured_canvas.get_tk_widget()
                    if widget.winfo_exists():
                        widget.destroy()
                except Exception as e:
                    self._log(f"DEBUG: Error destroying canvas widget: {e}")
                finally:
                    self.captured_canvas = None

            # 清除matplotlib图形对象
            if hasattr(self, 'captured_fig') and self.captured_fig is not None:
                try:
                    plt.close(self.captured_fig)
                except Exception as e:
                    self._log(f"DEBUG: Error closing figure: {e}")
                finally:
                    self.captured_fig = None

            # 清除标签的所有子组件 - 确保彻底清理
            for widget in self.captured_label.winfo_children():
                try:
                    widget.destroy()
                except Exception as e:
                    self._log(f"DEBUG: Error destroying child widget: {e}")

            # 重置标签状态
            self.captured_label.config(text="No captured curve yet. Click '截取曲线' to capture data.", image="")
            self.captured_label.image = None

            # 重置信息标签
            self.captured_count_label.config(text="N/A")
            self.captured_source_label.config(text="N/A")

            self._log("DEBUG: Capture cleared successfully")

        except Exception as e:
            self._log(f"Error in _clear_capture: {str(e)}", "ERROR")

        # 禁用清除按钮
        self.btn_clear_capture.config(state="disabled")
        self._log("Captured curve cleared")

    def _log(self, message: str, level: str = "INFO"):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}\n"

        self.log_text.insert("end", log_entry)
        self.log_text.see("end")  # 自动滚动到底部

    def _apply_roi_config(self):
        """应用ROI配置"""
        if not self.connected or not self.http_client:
            messagebox.showerror("错误", "请先连接到服务器")
            return

        try:
            self._log("应用ROI配置...")

            # 获取配置值
            x1 = int(self.roi_x1_var.get())
            y1 = int(self.roi_y1_var.get())
            x2 = int(self.roi_x2_var.get())
            y2 = int(self.roi_y2_var.get())

            # 验证ROI坐标
            if x2 <= x1 or y2 <= y1:
                messagebox.showerror("错误", "ROI坐标无效：X2必须大于X1，Y2必须大于Y1")
                return

            # 发送ROI配置请求
            roi_data = {
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "password": self.http_client.password
            }

            response = self.http_client.session.post(
                f"{self.http_client.base_url}/roi/config",
                data=roi_data,
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    self._log(f"✅ ROI配置应用成功: X={x1},{x2}, Y={y1},{y2}")
                else:
                    messagebox.showerror("配置失败", f"ROI配置失败: {result.get('error', '未知错误')}")
            else:
                messagebox.showerror("配置失败", f"服务器错误: {response.status_code}")

        except ValueError as e:
            messagebox.showerror("输入错误", f"参数格式错误: {str(e)}")
        except Exception as e:
            self._log(f"ROI配置应用失败: {str(e)}", "ERROR")
            messagebox.showerror("配置失败", f"ROI配置应用失败: {str(e)}")

    def _apply_peak_config(self):
        """应用波峰检测配置"""
        if not self.connected or not self.http_client:
            messagebox.showerror("错误", "请先连接到服务器")
            return

        try:
            self._log("应用波峰检测配置...")

            # 获取配置值
            threshold = float(self.peak_threshold_var.get())
            margin_frames = int(self.peak_margin_var.get())
            diff_threshold = float(self.peak_diff_var.get())

            # 验证参数范围
            if not (50 <= threshold <= 255):
                messagebox.showerror("错误", "绝对阈值必须在50-255之间")
                return
            if not (1 <= margin_frames <= 20):
                messagebox.showerror("错误", "边界帧数必须在1-20之间")
                return
            if not (0.1 <= diff_threshold <= 10.0):
                messagebox.showerror("错误", "差值阈值必须在0.1-10.0之间")
                return

            # 发送波峰检测配置请求
            peak_data = {
                "threshold": threshold,
                "margin_frames": margin_frames,
                "difference_threshold": diff_threshold,
                "password": self.http_client.password
            }

            response = self.http_client.session.post(
                f"{self.http_client.base_url}/peak-detection/config",
                data=peak_data,
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    self._log(f"✅ 波峰检测配置应用成功: 阈值={threshold}, 边界={margin_frames}, 差值={diff_threshold}")
                else:
                    messagebox.showerror("配置失败", f"波峰检测配置失败: {result.get('error', '未知错误')}")
            else:
                messagebox.showerror("配置失败", f"服务器错误: {response.status_code}")

        except ValueError as e:
            messagebox.showerror("输入错误", f"参数格式错误: {str(e)}")
        except Exception as e:
            self._log(f"波峰检测配置应用失败: {str(e)}", "ERROR")
            messagebox.showerror("配置失败", f"波峰检测配置应用失败: {str(e)}")

    def _save_config(self):
        """保存配置到后端fem_config.json"""
        try:
            config_updates = {
                "roi_capture": {
                    "default_config": {
                        "x1": int(self.roi_x1_var.get()),
                        "y1": int(self.roi_y1_var.get()),
                        "x2": int(self.roi_x2_var.get()),
                        "y2": int(self.roi_y2_var.get())
                    },
                    "frame_rate": float(self.roi_fps_var.get())
                },
                "peak_detection": {
                    "threshold": float(self.peak_threshold_var.get()),
                    "margin_frames": int(self.peak_margin_var.get()),
                    "difference_threshold": float(self.peak_diff_var.get())
                }
            }

            # 使用后端API保存配置
            config_data = json.dumps(config_updates, ensure_ascii=False)

            response = self.http_client.session.post(
                f"{self.http_client.base_url}/config",
                params={
                    "config_data": config_data,
                    "password": self.http_client.password
                },
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success", True):
                    self._log("✅ 配置已保存到服务器 fem_config.json")
                    messagebox.showinfo("保存成功", "配置已保存到服务器 fem_config.json")
                else:
                    error_msg = result.get("error", "保存失败")
                    self._log(f"配置保存失败: {error_msg}", "ERROR")
                    messagebox.showerror("保存失败", f"配置保存失败: {error_msg}")
            else:
                error_text = response.text
                self._log(f"配置保存失败: HTTP {response.status_code} - {error_text}", "ERROR")
                messagebox.showerror("保存失败", f"配置保存失败: {response.status_code}")

        except Exception as e:
            self._log(f"配置保存失败: {str(e)}", "ERROR")
            messagebox.showerror("保存失败", f"配置保存失败: {str(e)}")

    def _load_config(self):
        """从后端fem_config.json加载配置"""
        try:
            if not self.connected or not self.http_client:
                messagebox.showerror("错误", "请先连接到服务器")
                return

            # 使用后端API获取配置
            response = self.http_client.session.get(
                f"{self.http_client.base_url}/config",
                params={
                    "password": self.http_client.password
                },
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                if "config" in result:
                    config = result["config"]

                    # 加载ROI配置
                    if "roi_capture" in config:
                        roi_config = config["roi_capture"]
                        default_config = roi_config.get("default_config", {})
                        self.roi_x1_var.set(str(default_config.get("x1", 0)))
                        self.roi_y1_var.set(str(default_config.get("y1", 0)))
                        self.roi_x2_var.set(str(default_config.get("x2", 200)))
                        self.roi_y2_var.set(str(default_config.get("y2", 150)))
                        self.roi_fps_var.set(str(roi_config.get("frame_rate", 2)))

                    # 加载波峰检测配置
                    if "peak_detection" in config:
                        peak_config = config["peak_detection"]
                        self.peak_threshold_var.set(str(peak_config.get("threshold", 105.0)))
                        self.peak_margin_var.set(str(peak_config.get("margin_frames", 5)))
                        self.peak_diff_var.set(str(peak_config.get("difference_threshold", 2.1)))

                    self._log("✅ 配置已从服务器 fem_config.json 加载")
                    messagebox.showinfo("加载成功", "配置已从服务器 fem_config.json 加载")
                else:
                    error_msg = result.get("error", "获取配置失败")
                    self._log(f"加载配置失败: {error_msg}", "ERROR")
                    messagebox.showerror("加载失败", f"加载配置失败: {error_msg}")
            else:
                error_text = response.text
                self._log(f"加载配置失败: HTTP {response.status_code} - {error_text}", "ERROR")
                messagebox.showerror("加载失败", f"加载配置失败: {response.status_code}")

        except Exception as e:
            self._log(f"配置加载失败: {str(e)}", "ERROR")
            messagebox.showerror("加载失败", f"配置加载失败: {str(e)}")

        # 限制日志行数
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 1000:
            self.log_text.delete("1.0", "100.0")

    def _apply_server_config(self, config_dict):
        """应用从服务器加载的配置到UI字段"""
        try:
            if not config_dict:
                self._log("服务器配置为空，使用默认值")
                return False

            config_applied = False
            missing_fields = []

            # 应用ROI配置
            if "roi_capture" in config_dict:
                roi_config = config_dict["roi_capture"]

                # 应用ROI坐标
                if "default_config" in roi_config:
                    default_config = roi_config["default_config"]
                    self.roi_x1_var.set(str(default_config.get("x1", 0)))
                    self.roi_y1_var.set(str(default_config.get("y1", 0)))
                    self.roi_x2_var.set(str(default_config.get("x2", 200)))
                    self.roi_y2_var.set(str(default_config.get("y2", 150)))
                    config_applied = True

                # 应用ROI帧率
                if "frame_rate" in roi_config:
                    self.roi_fps_var.set(str(roi_config["frame_rate"]))
                    config_applied = True
            else:
                missing_fields.append("roi_capture")

            # 应用波峰检测配置
            if "peak_detection" in config_dict:
                peak_config = config_dict["peak_detection"]

                self.peak_threshold_var.set(str(peak_config.get("threshold", 105.0)))
                self.peak_margin_var.set(str(peak_config.get("margin_frames", 5)))
                self.peak_diff_var.set(str(peak_config.get("difference_threshold", 2.1)))
                config_applied = True
            else:
                missing_fields.append("peak_detection")

            if config_applied:
                self._log("✅ 成功应用服务器配置到UI")
                if missing_fields:
                    self._log(f"⚠️ 缺少配置字段: {', '.join(missing_fields)}")
                return True
            else:
                self._log("⚠️ 配置格式不符合预期，使用默认值")
                return False

        except Exception as e:
            self._log(f"❌ 应用服务器配置失败: {str(e)}", "ERROR")
            return False

    def _load_local_config(self):
        """从本地配置文件加载配置"""
        try:
            self._log("🔄 正在加载本地配置文件...")

            # 创建本地配置加载器
            config_loader = LocalConfigLoader()

            # 加载配置
            success, message, config_data = config_loader.load_config()

            if success:
                self._log(f"✅ {message}")

                # 应用配置到UI字段
                if self._apply_server_config(config_data):
                    self._log("🎯 本地配置已成功应用到UI界面")
                    return True
                else:
                    self._log("⚠️ 本地配置应用失败，使用默认值")
                    return False
            else:
                self._log(f"❌ 本地配置加载失败: {message}")
                return False

        except Exception as e:
            self._log(f"❌ 本地配置加载异常: {str(e)}", "ERROR")
            return False

    def _auto_load_config(self):
        """自动从服务器加载配置"""
        try:
            if not self.connected or not self.http_client:
                self._log("⚠️ 服务器未连接，跳过自动配置加载")
                return False

            self._log("🔄 自动加载服务器配置...")

            # 向服务器请求配置
            response = self.http_client.session.get(
                f"{self.http_client.base_url}/config",
                params={"password": self.http_client.password},
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                if "config" in result:
                    config = result["config"]
                    success = self._apply_server_config(config)
                    if success:
                        self._log("🎯 自动配置加载完成")
                        return True
                    else:
                        self._log("⚠️ 自动配置加载失败，使用默认值")
                        return False
                else:
                    error_msg = result.get("error", "获取配置失败")
                    self._log(f"❌ 自动配置加载失败: {error_msg}", "ERROR")
                    return False
            else:
                self._log(f"❌ 获取配置失败: HTTP {response.status_code}", "ERROR")
                return False

        except Exception as e:
            self._log(f"❌ 自动配置加载异常: {str(e)}", "ERROR")
            return False

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