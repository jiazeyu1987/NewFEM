import json
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from . import client


class NewFEMClientUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("NewFEM Python 客户端")
        self.geometry("720x520")
        self._build_widgets()

    # --------------------------------------------------------------------- UI

    def _build_widgets(self) -> None:
        # 顶部连接配置
        conn_frame = ttk.LabelFrame(self, text="连接配置")
        conn_frame.pack(fill="x", padx=8, pady=4)

        ttk.Label(conn_frame, text="后端 URL:").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        self.entry_base_url = ttk.Entry(conn_frame, width=40)
        self.entry_base_url.grid(row=0, column=1, sticky="w", padx=4, pady=2)
        self.entry_base_url.insert(0, os.getenv("NEWFEM_BASE_URL", client.DEFAULT_BASE_URL))

        ttk.Label(conn_frame, text="密码:").grid(row=0, column=2, sticky="e", padx=4, pady=2)
        self.entry_password = ttk.Entry(conn_frame, width=12, show="*")
        self.entry_password.grid(row=0, column=3, sticky="w", padx=4, pady=2)
        self.entry_password.insert(0, os.getenv("NEWFEM_PASSWORD", client.DEFAULT_PASSWORD))

        # 参数设置区域（ROI + 帧率）
        param_frame = ttk.LabelFrame(self, text="参数设置（ROI + 帧率）")
        param_frame.pack(fill="x", padx=8, pady=4)

        ttk.Label(param_frame, text="x1:").grid(row=0, column=0, sticky="e", padx=2, pady=2)
        self.entry_x1 = ttk.Entry(param_frame, width=6)
        self.entry_x1.grid(row=0, column=1, sticky="w", padx=2, pady=2)
        self.entry_x1.insert(0, "0")

        ttk.Label(param_frame, text="y1:").grid(row=0, column=2, sticky="e", padx=2, pady=2)
        self.entry_y1 = ttk.Entry(param_frame, width=6)
        self.entry_y1.grid(row=0, column=3, sticky="w", padx=2, pady=2)
        self.entry_y1.insert(0, "0")

        ttk.Label(param_frame, text="x2:").grid(row=0, column=4, sticky="e", padx=2, pady=2)
        self.entry_x2 = ttk.Entry(param_frame, width=6)
        self.entry_x2.grid(row=0, column=5, sticky="w", padx=2, pady=2)
        self.entry_x2.insert(0, "200")

        ttk.Label(param_frame, text="y2:").grid(row=0, column=6, sticky="e", padx=2, pady=2)
        self.entry_y2 = ttk.Entry(param_frame, width=6)
        self.entry_y2.grid(row=0, column=7, sticky="w", padx=2, pady=2)
        self.entry_y2.insert(0, "150")

        ttk.Label(param_frame, text="ROI FPS:").grid(row=1, column=0, sticky="e", padx=2, pady=2)
        self.entry_roi_fps = ttk.Entry(param_frame, width=6)
        self.entry_roi_fps.grid(row=1, column=1, sticky="w", padx=2, pady=2)
        self.entry_roi_fps.insert(0, "2")

        ttk.Label(param_frame, text="截取帧数:").grid(row=1, column=2, sticky="e", padx=2, pady=2)
        self.entry_capture_count = ttk.Entry(param_frame, width=8)
        self.entry_capture_count.grid(row=1, column=3, sticky="w", padx=2, pady=2)
        self.entry_capture_count.insert(0, "100")

        ttk.Button(param_frame, text="应用参数", command=self.on_apply_params).grid(
            row=1, column=6, columnspan=2, sticky="ew", padx=4, pady=2
        )

        # 控制按钮区域
        ctrl_frame = ttk.LabelFrame(self, text="控制")
        ctrl_frame.pack(fill="x", padx=8, pady=4)

        ttk.Button(ctrl_frame, text="开始检测", command=self.on_start).grid(
            row=0, column=0, sticky="ew", padx=4, pady=4
        )
        ttk.Button(ctrl_frame, text="停止检测", command=self.on_stop).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4
        )
        ttk.Button(ctrl_frame, text="截取 ROI + 波峰检测", command=self.on_capture_roi).grid(
            row=0, column=2, sticky="ew", padx=4, pady=4
        )
        ttk.Button(ctrl_frame, text="系统状态", command=self.on_status).grid(
            row=0, column=3, sticky="ew", padx=4, pady=4
        )

        # 输出区域
        output_frame = ttk.LabelFrame(self, text="响应 / 日志")
        output_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.text_output = tk.Text(output_frame, wrap="word")
        self.text_output.pack(fill="both", expand=True, padx=4, pady=4)

    # ----------------------------------------------------------------- helpers

    def _update_env(self) -> None:
        os.environ["NEWFEM_BASE_URL"] = self.entry_base_url.get().strip()
        os.environ["NEWFEM_PASSWORD"] = self.entry_password.get().strip()

    def _log(self, obj) -> None:
        if isinstance(obj, (dict, list)):
            text = json.dumps(obj, ensure_ascii=False, indent=2)
        else:
            text = str(obj)
        self.text_output.insert("end", text + "\n\n")
        self.text_output.see("end")

    def _run_in_thread(self, func, *args, **kwargs) -> None:
        def wrapper():
            try:
                result = func(*args, **kwargs)
                if result is not None:
                    self.after(0, self._log, result)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("错误", str(e)))

        threading.Thread(target=wrapper, daemon=True).start()

    # --------------------------------------------------------------- callbacks

    def on_apply_params(self) -> None:
        self._update_env()
        try:
            x1 = int(self.entry_x1.get())
            y1 = int(self.entry_y1.get())
            x2 = int(self.entry_x2.get())
            y2 = int(self.entry_y2.get())
            fps = int(self.entry_roi_fps.get())
        except ValueError:
            messagebox.showwarning("输入错误", "ROI 坐标和 FPS 必须是整数")
            return

        def action():
            roi_resp = client.set_roi(x1, y1, x2, y2)
            fps_resp = client.set_roi_frame_rate(fps)
            return {"roi": roi_resp, "roi_frame_rate": fps_resp}

        self._run_in_thread(action)

    def on_start(self) -> None:
        self._update_env()
        self._run_in_thread(client.start_detection)

    def on_stop(self) -> None:
        self._update_env()
        self._run_in_thread(client.stop_detection)

    def on_capture_roi(self) -> None:
        self._update_env()
        try:
            count = int(self.entry_capture_count.get())
        except ValueError:
            messagebox.showwarning("输入错误", "截取帧数必须是整数")
            return

        def action():
            return client.capture_roi_window_with_peaks(count=count)

        self._run_in_thread(action)

    def on_status(self) -> None:
        self._update_env()

        def action():
            ctrl = client.get_control_status()
            sys_status = client.get_system_status()
            return {"control": ctrl, "system": sys_status}

        self._run_in_thread(action)


def main() -> None:
    app = NewFEMClientUI()
    app.mainloop()


if __name__ == "__main__":
    main()

