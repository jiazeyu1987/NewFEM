# Python 客户端（HTTP）开发说明

## 1. 概览

本说明文档定义了使用 **Python 客户端通过 HTTP** 与 NewFEM 后端通信的开发规范，目标是在**不启动前端网页**的情况下，实现以下能力：

- 设置检测参数（ROI 区域、ROI 帧率等）
- 开始扫描 / 检测（启动数据处理与波峰检测）
- 停止扫描 / 检测
- 截取波形（窗口数据/ROI 窗口数据 + 波峰信息）

客户端通过标准 HTTP 协议调用现有 FastAPI 接口，无需修改后端，只需要在 Python 中使用 `requests` 等库即可完成集成。

---

## 2. 基本约定

### 2.1 服务器配置

- 基础 URL：`http://<host>:<port>`  
  - 默认：`http://localhost:8421`
- 默认密码：`31415`（可在 `backends/app/fem_config.json` 或环境变量中修改）

### 2.2 Python 环境

```bash
pip install requests
```

客户端脚本推荐的基础结构：

```python
import requests

BASE_URL = "http://localhost:8421"
PASSWORD = "31415"
```

---

## 3. 设置参数（配置接口）

Python 客户端主要需要完成两类参数设置：

1. ROI 区域坐标（用于确定感兴趣区域）
2. ROI 帧率（控制数据轮询与截取窗口的时间尺度）

### 3.1 设置 ROI 区域

- 方法：`POST`
- 路径：`/roi/config`
- Content-Type：`application/x-www-form-urlencoded`
- 主要字段：
  - `x1`, `y1`, `x2`, `y2`：ROI 左上角/右下角坐标（像素）
  - `password`：控制密码

示例代码：

```python
import requests

BASE_URL = "http://localhost:8421"
PASSWORD = "31415"

def set_roi(x1: int, y1: int, x2: int, y2: int) -> dict:
    url = f"{BASE_URL}/roi/config"
    data = {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "password": PASSWORD,
    }
    resp = requests.post(url, data=data, timeout=5)
    resp.raise_for_status()
    return resp.json()
```

调用示例：

```python
set_roi(0, 0, 200, 150)
```

> 注意：后端会验证坐标合法性，如果不合法会返回 400 错误。

### 3.2 设置 ROI 帧率

- 方法：`POST`
- 路径：`/roi/frame-rate`
- Content-Type：`application/x-www-form-urlencoded`
- 字段：
  - `frame_rate`：ROI 帧率（1–60，单位 FPS）
  - `password`：控制密码

示例代码：

```python
def set_roi_frame_rate(frame_rate: int) -> dict:
    url = f"{BASE_URL}/roi/frame-rate"
    data = {
        "frame_rate": frame_rate,
        "password": PASSWORD,
    }
    resp = requests.post(url, data=data, timeout=5)
    resp.raise_for_status()
    return resp.json()
```

调用示例：

```python
set_roi_frame_rate(2)
```

> ROI 帧率会影响前端轮询间隔和 ROI 窗口截取的时间范围。Python 客户端如果需要按照 ROI 节奏采样，可以使用相同的帧率配置作为参考。

### 3.3 （可选）批量更新配置

如果需要一次性修改多个配置（如波峰检测阈值等），可以调用统一配置接口：

- 方法：`POST`
- 路径：`/config/update`
- 查询参数（Query）：
  - `config_data`：完整或部分 JSON 配置字符串
  - `password`：密码

示例（修改波峰检测阈值）：

```python
import json

def update_peak_detection_config(threshold: float) -> dict:
    url = f"{BASE_URL}/config/update"
    payload = {
        "peak_detection": {
            "threshold": threshold
        }
    }
    params = {
        "config_data": json.dumps(payload, ensure_ascii=False),
        "password": PASSWORD,
    }
    resp = requests.post(url, params=params, timeout=5)
    resp.raise_for_status()
    return resp.json()
```

---

## 4. 开始 / 停止扫描（控制接口）

扫描/检测控制统一通过 `/control` 接口完成。

### 4.1 控制接口概览

- 方法：`POST`
- 路径：`/control`
- Content-Type：`application/x-www-form-urlencoded`
- 字段：
  - `command`：控制命令字符串
  - `password`：控制密码

支持的 `command`：

- `"start_detection"`：开始检测/扫描
- `"stop_detection"`：停止检测
- `"pause_detection"`：暂停（停止但保留状态）
- `"resume_detection"`：恢复检测
- `"PEAK_SIGNAL"`：获取当前波峰信号状态
- `"STATUS"`：获取系统状态摘要

### 4.2 开始扫描

```python
def start_detection() -> dict:
    url = f"{BASE_URL}/control"
    data = {
        "command": "start_detection",
        "password": PASSWORD,
    }
    resp = requests.post(url, data=data, timeout=5)
    resp.raise_for_status()
    return resp.json()
```

调用顺序建议：

1. 先调用 `set_roi(...)` 配置 ROI
2. 再调用 `set_roi_frame_rate(...)` 配置 ROI 帧率
3. 最后调用 `start_detection()` 开始检测

后端校验：

- 若 ROI 未配置，`start_detection` 会返回错误（`ROI_NOT_CONFIGURED`）。

### 4.3 停止扫描

```python
def stop_detection() -> dict:
    url = f"{BASE_URL}/control"
    data = {
        "command": "stop_detection",
        "password": PASSWORD,
    }
    resp = requests.post(url, data=data, timeout=5)
    resp.raise_for_status()
    return resp.json()
```

### 4.4 查询状态（可选）

```python
def get_status() -> dict:
    url = f"{BASE_URL}/control"
    data = {
        "command": "STATUS",
        "password": PASSWORD,
    }
    resp = requests.post(url, data=data, timeout=5)
    resp.raise_for_status()
    return resp.json()
```

或使用系统状态接口：

```python
def get_system_status() -> dict:
    url = f"{BASE_URL}/status"
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    return resp.json()
```

---

## 5. 截取波形（窗口/ROI + 波峰信息）

波形截取主要对应前端“【立即截取】”按钮逻辑。Python 客户端可以直接调用以下接口获取窗口数据或带波峰分析的 ROI 数据。

### 5.1 普通窗口波形截取

截取最近一段时间的主通道（非 ROI）波形数据：

- 方法：`GET`
- 路径：`/data/window-capture`
- 查询参数：
  - `count`：窗口内的帧数（50–200）

示例代码：

```python
def capture_window(count: int = 100) -> dict:
    url = f"{BASE_URL}/data/window-capture"
    params = {"count": count}
    resp = requests.get(url, params=params, timeout=5)
    resp.raise_for_status()
    return resp.json()
```

典型返回字段（简要）：

- `series`：时间序列数组，包含 `t`（秒）、`value`（灰度值）
- `frame_range`：开始/结束帧号
- `capture_metadata`：采集窗口的统计信息（持续时间、基线等）

### 5.2 ROI 窗口截取 + 波峰检测

如果希望直接获得 **ROI 灰度序列 + 波峰检测结果**，推荐使用：

- 方法：`GET`
- 路径：`/data/roi-window-capture-with-peaks`
- 查询参数：
  - `count`：ROI 窗口帧数（例如 100）
  - `threshold`（可选）：波峰检测阈值，留空则使用配置文件中的默认值
  - `margin_frames`（可选）：波峰区域前后扩展帧数
  - `difference_threshold`（可选）：绿色/红色波峰区分的差值阈值

示例代码：

```python
def capture_roi_window_with_peaks(
    count: int = 100,
    threshold: float | None = None,
    margin_frames: int | None = None,
    difference_threshold: float | None = None,
) -> dict:
    url = f"{BASE_URL}/data/roi-window-capture-with-peaks"
    params = {"count": count}
    if threshold is not None:
        params["threshold"] = threshold
    if margin_frames is not None:
        params["margin_frames"] = margin_frames
    if difference_threshold is not None:
        params["difference_threshold"] = difference_threshold

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()
```

返回内容（关键字段）：

- `series`：ROI 灰度时间序列（`t`, `gray_value`, `roi_index`）
- `roi_config`：本次截取所使用的 ROI 坐标与尺寸
- `capture_metadata`：窗口帧号范围、持续时间、ROI 实际帧率等
- `peak_detection_results`：
  - `green_peaks` / `red_peaks`：稳定/不稳定波峰索引
  - `total_peaks`：总波峰数量
- `peak_detection_params`：本次检测实际使用的阈值配置

### 5.3 获取波形图像（带波峰标注）

如果需要直接得到**带有波峰标注的波形图像（base64 PNG）**，可以调用：

- 方法：`GET`
- 路径：`/data/waveform-with-peaks`
- 查询参数：
  - `count`：数据点数量（10–500）
  - `threshold` / `margin_frames` / `difference_threshold`（可选）

示例代码：

```python
def get_waveform_image_with_peaks(count: int = 200) -> dict:
    url = f"{BASE_URL}/data/waveform-with-peaks"
    params = {"count": count}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    # data["image_data"] 为 base64 编码的 PNG 图像
    return data
```

如需保存为 PNG 文件：

```python
import base64

def save_waveform_image(data: dict, filename: str = "waveform.png") -> None:
    image_b64 = data["image_data"]
    with open(filename, "wb") as f:
        f.write(base64.b64decode(image_b64))
```

---

## 6. 典型 Python 客户端调用流程

一个典型的端到端流程可以按照以下顺序执行：

```python
def run_full_flow():
    # 1. 设置 ROI 参数
    print("设置 ROI ...")
    print(set_roi(0, 0, 200, 150))

    # 2. 设置 ROI 帧率
    print("设置 ROI 帧率 ...")
    print(set_roi_frame_rate(2))

    # 3. 开始检测 / 扫描
    print("开始检测 ...")
    print(start_detection())

    # （可选）等待一段时间，让数据缓冲区有足够数据
    import time
    time.sleep(5)

    # 4. 截取 ROI 窗口波形并进行波峰检测
    print("截取 ROI 波形窗口 ...")
    roi_capture = capture_roi_window_with_peaks(count=100)
    print("ROI 截取结果中的波峰统计:", roi_capture.get("peak_detection_results"))

    # 5. （可选）获取波形图像
    print("获取波形图像 ...")
    img_data = get_waveform_image_with_peaks(count=200)
    save_waveform_image(img_data, "waveform_with_peaks.png")

    # 6. 停止检测
    print("停止检测 ...")
    print(stop_detection())
```

---

## 7. 错误处理与调试建议

- 所有 `requests` 调用建议使用 `resp.raise_for_status()`，并在外层用 `try/except` 捕获：

```python
try:
    result = start_detection()
except requests.HTTPError as e:
    print("HTTP 错误:", e.response.status_code, e.response.text)
except requests.RequestException as e:
    print("网络错误:", e)
```

- 当接口返回 4xx/5xx 时，JSON 体通常为统一的错误结构（参考 `doc/api-interface-spec.md`），可以打印 `error_code` 与 `error_message` 辅助定位问题。
- 后端调试时，可将环境变量 `NEWFEM_LOG_LEVEL` 设置为 `DEBUG`，或在 `fem_config.json` 中调整 `logging.level`。

---

## 8. 后续扩展

在完成基础的“设置参数 + 开始/停止 + 截取波形”之后，可以基于同样的 HTTP 客户端模式进一步扩展：

- 封装为类 `NewFEMClient`，提供面向对象接口
- 加入命令行解析（`argparse` / `typer`），实现 `python client.py start/stop/capture`
- 加入简单 GUI（如 `tkinter` / `PyQt`），实现按钮式控制面板

本文件只定义最小可用的 HTTP 客户端约定，具体实现可以根据项目需要灵活裁剪。
