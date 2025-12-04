"""
增强的Python客户端UI - 集成Socket通信和实时绘图
"""

import json
import os
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext

from .socket_client import SocketClient
from .realtime_plotter import RealtimePlotter

try:
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("Warning: matplotlib not available, plotting disabled")


class EnhancedNewFEMClientUI(tk.Tk):
    """增强的NewFEM Python客户端UI"""

    def __init__(self):
        super().__init__()
        self.title("NewFEM Enhanced Python Client - Socket + Real-time Plotting")
        self.geometry("1200x800")

        # Socket客户端
        self.socket_client: SocketClient = None
        self.connected = False

        # 实时绘图器
        self.plotter: RealtimePlotter = None

        # 状态变量
        self.detection_running = False
        self.data_count = 0
        self.last_data_time = 0

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
        conn_frame = ttk.LabelFrame(self, text="Socket连接配置")
        conn_frame.pack(fill="x", padx=8, pady=4)

        ttk.Label(conn_frame, text="服务器:").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        self.entry_host = ttk.Entry(conn_frame, width=20)
        self.entry_host.grid(row=0, column=1, sticky="w", padx=4, pady=2)
        self.entry_host.insert(0, "localhost")

        ttk.Label(conn_frame, text="端口:").grid(row=0, column=2, sticky="e", padx=4, pady=2)
        self.entry_port = ttk.Entry(conn_frame, width=8)
        self.entry_port.grid(row=0, column=3, sticky="w", padx=4, pady=2)
        self.entry_port.insert(0, "30415")

        ttk.Label(conn_frame, text="密码:").grid(row=0, column=4, sticky="e", padx=4, pady=2)
        self.entry_password = ttk.Entry(conn_frame, width=12, show="*")
        self.entry_password.grid(row=0, column=5, sticky="w", padx=4, pady=2)
        self.entry_password.insert(0, "31415")

        # 连接按钮
        self.btn_connect = ttk.Button(conn_frame, text="连接", command=self._toggle_connection)
        self.btn_connect.grid(row=0, column=6, padx=8, pady=2)

        # 连接状态指示器
        self.status_var = tk.StringVar(value="未连接")
        self.status_label = ttk.Label(conn_frame, textvariable=self.status_var, foreground="red")
        self.status_label.grid(row=0, column=7, padx=4, pady=2)

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

        ttk.Label(status_info, text="波峰数:").grid(row=3, column=0, sticky="w", pady=2)
        self.peak_count_label = ttk.Label(status_info, text="0")
        self.peak_count_label.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=2)

        ttk.Label(status_info, text="连接状态:").grid(row=4, column=0, sticky="w", pady=2)
        self.connection_status_label = ttk.Label(status_info, text="未连接")
        self.connection_status_label.grid(row=4, column=1, sticky="w", padx=(8, 0), pady=2)

        # 分隔线
        ttk.Separator(info_frame, orient="horizontal").pack(fill="x", pady=8)

        # 日志面板
        log_frame = ttk.LabelFrame(info_frame, text="日志")
        log_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, width=40)
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

        # 右侧图表框架
        plot_frame = ttk.LabelFrame(main_frame, text="实时图表")
        plot_frame.pack(side="right", fill="both", expand=True)

        self.plot_frame = plot_frame

    def _setup_plotter(self):
        """设置绘图器"""
        if HAS_MPL:
            self.plotter = RealtimePlotter(master=self.plot_frame, figsize=(10, 6))
            self.plotter.setup_plot()
            self.plotter.setup_canvas()
            self.plotter.start_animation(interval=50)  # 20 FPS

            # 注册消息处理器
            self._setup_message_handlers()
        else:
            # 如果没有matplotlib，显示提示
            no_mpl_label = ttk.Label(self.plot_frame, text="matplotlib未安装，无法显示图表")
            no_mpl_label.pack(expand=True)

    def _setup_message_handlers(self):
        """设置Socket消息处理器"""
        if self.socket_client:
            # 实时数据处理器
            self.socket_client.register_message_handler("realtime_data", self._handle_realtime_data)

            # 控制响应处理器
            self.socket_client.register_message_handler("control_response", self._handle_control_response)

            # 系统状态处理器
            self.socket_client.register_message_handler("system_status", self._handle_system_status)

            # 连接状态回调
            self.socket_client.register_connection_callback(self._on_connection_change)

            # 错误回调
            self.socket_client.register_error_callback(self._on_error)

    def _toggle_connection(self):
        """切换连接状态"""
        if not self.connected:
            self._connect()
        else:
            self._disconnect()

    def _connect(self):
        """连接到服务器"""
        try:
            host = self.entry_host.get()
            port = int(self.entry_port.get())
            password = self.entry_password.get()

            # 创建Socket客户端
            self.socket_client = SocketClient(host=host, port=port)

            # 设置消息处理器
            self._setup_message_handlers()

            # 启动客户端
            self.socket_client.start(password)

            # 更新UI状态
            self.status_var.set("连接中...")
            self.btn_connect.config(text="连接中...", state="disabled")

            self._log("正在连接到服务器...")

        except Exception as e:
            messagebox.showerror("连接错误", f"连接失败: {str(e)}")
            self._log(f"连接失败: {str(e)}", "ERROR")

    def _disconnect(self):
        """断开连接"""
        if self.socket_client:
            self.socket_client.stop()
            self.socket_client = None

        self.connected = False
        self._update_connection_status()

    def _on_connection_change(self, connected: bool):
        """连接状态变化回调"""
        self.connected = connected
        self.after(0, self._update_connection_status)

        if connected:
            # 订阅消息类型
            if self.socket_client:
                # 在事件循环中执行订阅
                import asyncio
                asyncio.run_coroutine_threadsafe(
                    self.socket_client.subscribe(["realtime_data", "system_status"]),
                    self.socket_client.loop
                )

            self._log("连接成功！")
            messagebox.showinfo("连接成功", "已连接到NewFEM服务器")
        else:
            self._log("连接断开")

    def _update_connection_status(self):
        """更新连接状态显示"""
        if self.connected:
            self.status_var.set("已连接")
            self.status_label.config(foreground="green")
            self.connection_status_label.config(text="已连接", foreground="green")
            self.btn_connect.config(text="断开连接", state="normal")
            self.btn_start.config(state="normal")
            self.btn_clear.config(state="normal")
            self.btn_save.config(state="normal")
        else:
            self.status_var.set("未连接")
            self.status_label.config(foreground="red")
            self.connection_status_label.config(text="未连接", foreground="red")
            self.btn_connect.config(text="连接", state="normal")
            self.btn_start.config(state="disabled")
            self.btn_clear.config(state="disabled")
            self.btn_save.config(state="disabled")

    def _start_detection(self):
        """开始检测"""
        if self.socket_client and self.connected:
            try:
                import asyncio
                asyncio.run_coroutine_threadsafe(
                    self.socket_client.send_command("start_detection"),
                    self.socket_client.loop
                )

                self.detection_running = True
                self._update_detection_status()
                self._log("发送开始检测命令")

            except Exception as e:
                messagebox.showerror("错误", f"开始检测失败: {str(e)}")
                self._log(f"开始检测失败: {str(e)}", "ERROR")

    def _stop_detection(self):
        """停止检测"""
        if self.socket_client and self.connected:
            try:
                import asyncio
                asyncio.run_coroutine_threadsafe(
                    self.socket_client.send_command("stop_detection"),
                    self.socket_client.loop
                )

                self.detection_running = False
                self._update_detection_status()
                self._log("发送停止检测命令")

            except Exception as e:
                messagebox.showerror("错误", f"停止检测失败: {str(e)}")
                self._log(f"停止检测失败: {str(e)}", "ERROR")

    def _update_detection_status(self):
        """更新检测状态"""
        if self.detection_running:
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
            self.data_count = 0
            self._update_info_display()
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

    def _handle_realtime_data(self, data):
        """处理实时数据"""
        if self.plotter:
            self.plotter.update_data(data)

        self.data_count += 1
        self.last_data_time = time.time()

        # 在主线程中更新UI
        self.after(0, self._update_info_display)

    def _handle_control_response(self, data):
        """处理控制响应"""
        command = data.get("command", "")
        success = data.get("success", False)
        message = data.get("message", "")

        self.after(0, lambda: self._log(f"控制响应 [{command}]: {message}" if success else f"控制失败 [{command}]: {message}"))

    def _handle_system_status(self, data):
        """处理系统状态"""
        # 这里可以更新系统状态显示
        pass

    def _on_error(self, error):
        """错误处理"""
        self.after(0, lambda: self._log(f"错误: {str(error)}", "ERROR"))

    def _update_info_display(self):
        """更新信息显示"""
        # 更新数据点数
        self.data_count_label.config(text=str(self.data_count))

        # 更新FPS（如果有绘图器）
        if self.plotter:
            stats = self.plotter.get_statistics()
            self.fps_label.config(text=f"{stats['fps']:.1f}")
            self.peak_count_label.config(text=str(stats['peaks_detected']))

    def _start_status_update(self):
        """启动状态更新循环"""
        def update_status():
            try:
                if self.connected and self.socket_client:
                    # 检查连接状态
                    if not self.socket_client.is_connected():
                        self.connected = False
                        self.after(0, self._update_connection_status)

                # 每秒更新一次
                self.after(1000, update_status)
            except Exception as e:
                self._log(f"状态更新错误: {str(e)}", "ERROR")
                self.after(5000, update_status)  # 出错时5秒后重试

        self.after(1000, update_status)

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
            # 断开Socket连接
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
    app = EnhancedNewFEMClientUI()
    app.mainloop()


if __name__ == "__main__":
    main()