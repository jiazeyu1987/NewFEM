import argparse
import base64
import json
import os
import sys
import time
from typing import Any, Dict, Optional

import requests


DEFAULT_BASE_URL = "http://localhost:8421"
DEFAULT_PASSWORD = "31415"


def get_base_url() -> str:
    """
    获取后端基础 URL，可通过环境变量 NEWFEM_BASE_URL 覆盖。
    """
    return os.getenv("NEWFEM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def get_password() -> str:
    """
    获取控制密码，可通过环境变量 NEWFEM_PASSWORD 覆盖。
    """
    return os.getenv("NEWFEM_PASSWORD", DEFAULT_PASSWORD)


def _print_json(resp: Dict[str, Any]) -> None:
    print(json.dumps(resp, ensure_ascii=False, indent=2))


# =============================================================================
# 配置相关
# =============================================================================

def set_roi(x1: int, y1: int, x2: int, y2: int) -> Dict[str, Any]:
    """
    设置 ROI 区域并保存到后端配置。
    """
    url = f"{get_base_url()}/roi/config"
    data = {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "password": get_password(),
    }
    resp = requests.post(url, data=data, timeout=5)
    resp.raise_for_status()
    return resp.json()


def set_roi_frame_rate(frame_rate: int) -> Dict[str, Any]:
    """
    设置 ROI 帧率（1-60 FPS）。
    """
    url = f"{get_base_url()}/roi/frame-rate"
    data = {
        "frame_rate": frame_rate,
        "password": get_password(),
    }
    resp = requests.post(url, data=data, timeout=5)
    resp.raise_for_status()
    return resp.json()


def update_peak_detection_config(threshold: float) -> Dict[str, Any]:
    """
    通过统一配置接口更新波峰检测阈值。
    """
    url = f"{get_base_url()}/config/update"
    payload = {
        "peak_detection": {
            "threshold": threshold,
        }
    }
    params = {
        "config_data": json.dumps(payload, ensure_ascii=False),
        "password": get_password(),
    }
    resp = requests.post(url, params=params, timeout=5)
    resp.raise_for_status()
    return resp.json()


# =============================================================================
# 控制相关（开始 / 停止 / 状态）
# =============================================================================

def start_detection() -> Dict[str, Any]:
    """
    开始检测 / 扫描。
    """
    url = f"{get_base_url()}/control"
    data = {
        "command": "start_detection",
        "password": get_password(),
    }
    resp = requests.post(url, data=data, timeout=5)
    resp.raise_for_status()
    return resp.json()


def stop_detection() -> Dict[str, Any]:
    """
    停止检测 / 扫描。
    """
    url = f"{get_base_url()}/control"
    data = {
        "command": "stop_detection",
        "password": get_password(),
    }
    resp = requests.post(url, data=data, timeout=5)
    resp.raise_for_status()
    return resp.json()


def get_control_status() -> Dict[str, Any]:
    """
    通过 /control 获取控制层状态摘要。
    """
    url = f"{get_base_url()}/control"
    data = {
        "command": "STATUS",
        "password": get_password(),
    }
    resp = requests.post(url, data=data, timeout=5)
    resp.raise_for_status()
    return resp.json()


def get_system_status() -> Dict[str, Any]:
    """
    通过 /status 获取系统运行状态。
    """
    url = f"{get_base_url()}/status"
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    return resp.json()


# =============================================================================
# 截取波形相关
# =============================================================================

def capture_window(count: int = 100) -> Dict[str, Any]:
    """
    截取主通道最近 count 帧的数据窗口。
    """
    url = f"{get_base_url()}/data/window-capture"
    params = {"count": count}
    resp = requests.get(url, params=params, timeout=5)
    resp.raise_for_status()
    return resp.json()


def capture_roi_window_with_peaks(
    count: int = 100,
    threshold: Optional[float] = None,
    margin_frames: Optional[int] = None,
    difference_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """
    截取 ROI 窗口并执行波峰检测，返回 ROI 灰度序列和检测结果。
    """
    url = f"{get_base_url()}/data/roi-window-capture-with-peaks"
    params: Dict[str, Any] = {"count": count}
    if threshold is not None:
        params["threshold"] = threshold
    if margin_frames is not None:
        params["margin_frames"] = margin_frames
    if difference_threshold is not None:
        params["difference_threshold"] = difference_threshold

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_waveform_image_with_peaks(
    count: int = 200,
    threshold: Optional[float] = None,
    margin_frames: Optional[int] = None,
    difference_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """
    获取带波峰标注的波形图像（base64 PNG）。
    """
    url = f"{get_base_url()}/data/waveform-with-peaks"
    params: Dict[str, Any] = {"count": count}
    if threshold is not None:
        params["threshold"] = threshold
    if margin_frames is not None:
        params["margin_frames"] = margin_frames
    if difference_threshold is not None:
        params["difference_threshold"] = difference_threshold

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def save_waveform_image(data: Dict[str, Any], filename: str = "waveform_with_peaks.png") -> None:
    """
    将 waveform-with-peaks 接口返回的数据保存为 PNG 文件。
    """
    image_b64 = data.get("image_data")
    if not image_b64:
        raise ValueError("response does not contain 'image_data'")

    with open(filename, "wb") as f:
        f.write(base64.b64decode(image_b64))


# =============================================================================
# 一键流程示例
# =============================================================================

def run_full_flow(
    roi: tuple[int, int, int, int] = (0, 0, 200, 150),
    roi_frame_rate: int = 2,
    capture_count: int = 100,
    sleep_seconds: float = 5.0,
) -> None:
    """
    示例：设置 ROI -> 设置帧率 -> 开始检测 -> 等待 -> 截取 ROI 窗口 -> 获取波形图像 -> 停止检测。
    """
    x1, y1, x2, y2 = roi

    print("设置 ROI 配置 ...")
    _print_json(set_roi(x1, y1, x2, y2))

    print("设置 ROI 帧率 ...")
    _print_json(set_roi_frame_rate(roi_frame_rate))

    print("开始检测 ...")
    _print_json(start_detection())

    print(f"等待 {sleep_seconds} 秒以积累数据 ...")
    time.sleep(sleep_seconds)

    print("截取 ROI 波形窗口并进行波峰检测 ...")
    roi_capture = capture_roi_window_with_peaks(count=capture_count)
    _print_json(roi_capture.get("peak_detection_results", {}))

    print("获取带波峰标注的波形图像 ...")
    img_data = get_waveform_image_with_peaks(count=capture_count)
    save_waveform_image(img_data, "waveform_with_peaks.png")
    print("波形图已保存为 waveform_with_peaks.png")

    print("停止检测 ...")
    _print_json(stop_detection())


# =============================================================================
# 命令行接口
# =============================================================================

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NewFEM Python 客户端（通过 HTTP 控制后端）",
    )
    parser.add_argument(
        "--base-url",
        help=f"后端基础 URL（默认 {DEFAULT_BASE_URL}，可用 NEWFEM_BASE_URL 覆盖）",
    )
    parser.add_argument(
        "--password",
        help=f"控制密码（默认 {DEFAULT_PASSWORD}，可用 NEWFEM_PASSWORD 覆盖）",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # set-roi
    p_roi = subparsers.add_parser("set-roi", help="设置 ROI 区域")
    p_roi.add_argument("x1", type=int)
    p_roi.add_argument("y1", type=int)
    p_roi.add_argument("x2", type=int)
    p_roi.add_argument("y2", type=int)

    # set-roi-fps
    p_roifps = subparsers.add_parser("set-roi-fps", help="设置 ROI 帧率（1-60 FPS）")
    p_roifps.add_argument("fps", type=int)

    # update-peak-threshold
    p_peak = subparsers.add_parser("update-peak-threshold", help="更新波峰检测阈值")
    p_peak.add_argument("threshold", type=float)

    # start / stop
    subparsers.add_parser("start", help="开始检测")
    subparsers.add_parser("stop", help="停止检测")

    # status / sys-status
    subparsers.add_parser("status", help="获取控制层状态（/control STATUS）")
    subparsers.add_parser("sys-status", help="获取系统状态（/status）")

    # capture-window
    p_cw = subparsers.add_parser("capture-window", help="截取主通道窗口数据")
    p_cw.add_argument("--count", type=int, default=100)

    # capture-roi
    p_cr = subparsers.add_parser("capture-roi", help="截取 ROI 窗口并进行波峰检测")
    p_cr.add_argument("--count", type=int, default=100)
    p_cr.add_argument("--threshold", type=float)
    p_cr.add_argument("--margin-frames", type=int)
    p_cr.add_argument("--difference-threshold", type=float)

    # waveform-image
    p_img = subparsers.add_parser("waveform-image", help="获取带波峰标注的波形图像并保存为 PNG")
    p_img.add_argument("--count", type=int, default=200)
    p_img.add_argument("--output", type=str, default="waveform_with_peaks.png")
    p_img.add_argument("--threshold", type=float)
    p_img.add_argument("--margin-frames", type=int)
    p_img.add_argument("--difference-threshold", type=float)

    # demo-flow
    p_demo = subparsers.add_parser("demo-flow", help="执行完整示例流程")
    p_demo.add_argument("--sleep", type=float, default=5.0, help="开始检测后的等待时间（秒）")
    p_demo.add_argument("--count", type=int, default=100, help="截取窗口帧数")

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # 覆盖全局配置（通过环境变量或参数）
    if args.base_url:
        os.environ["NEWFEM_BASE_URL"] = args.base_url
    if args.password:
        os.environ["NEWFEM_PASSWORD"] = args.password

    try:
        if args.command == "set-roi":
            _print_json(set_roi(args.x1, args.y1, args.x2, args.y2))
        elif args.command == "set-roi-fps":
            _print_json(set_roi_frame_rate(args.fps))
        elif args.command == "update-peak-threshold":
            _print_json(update_peak_detection_config(args.threshold))
        elif args.command == "start":
            _print_json(start_detection())
        elif args.command == "stop":
            _print_json(stop_detection())
        elif args.command == "status":
            _print_json(get_control_status())
        elif args.command == "sys-status":
            _print_json(get_system_status())
        elif args.command == "capture-window":
            _print_json(capture_window(count=args.count))
        elif args.command == "capture-roi":
            _print_json(
                capture_roi_window_with_peaks(
                    count=args.count,
                    threshold=args.threshold,
                    margin_frames=args.margin_frames,
                    difference_threshold=args.difference_threshold,
                )
            )
        elif args.command == "waveform-image":
            data = get_waveform_image_with_peaks(
                count=args.count,
                threshold=args.threshold,
                margin_frames=args.margin_frames,
                difference_threshold=args.difference_threshold,
            )
            save_waveform_image(data, args.output)
            print(f"图像已保存到 {args.output}")
        elif args.command == "demo-flow":
            run_full_flow(capture_count=args.count, sleep_seconds=args.sleep)
        else:
            parser.error(f"未知命令: {args.command}")
    except requests.HTTPError as e:
        print("HTTP 错误:", e.response.status_code, file=sys.stderr)
        try:
            print(e.response.text, file=sys.stderr)
        except Exception:
            pass
        sys.exit(1)
    except requests.RequestException as e:
        print("网络错误:", str(e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print("执行出错:", str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

