#!/usr/bin/env python3
"""
完整的测试服务器 - 支持所有HTTP客户端需要的API接口
在端口8422上运行以避免端口冲突
"""

import json
import base64
import io
import os
import numpy as np
from datetime import datetime
from PIL import Image
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title='NewFEM Complete Test Server', version='1.0.0')

class ControlRequest(BaseModel):
    command: str = 'start_detection'
    password: str = '31415'

# 存储一些状态
detection_active = False

@app.get('/health')
async def health():
    return {
        'status': 'healthy',
        'system': 'NewFEM API Server',
        'version': '3.0.0',
        'timestamp': datetime.now().isoformat()
    }

@app.get('/status')
async def status():
    return {
        'status': 'running' if detection_active else 'stopped',
        'timestamp': datetime.now().isoformat(),
        'data_points': np.random.randint(50, 150),
        'fps': 20,
        'detection_active': detection_active
    }

@app.get('/data/realtime')
async def get_realtime_data(count: int = 1):
    # 生成更真实的模拟数据
    t = datetime.now().timestamp()
    signal_value = 30 + 5 * np.sin(t * 0.5) + np.random.normal(0, 1.5)
    signal_value = max(20, min(60, signal_value))  # 限制在合理范围内

    # 生成简单干净的ROI截图（回到原始的正确逻辑）
    # 创建基础图像
    img = Image.new('RGB', (200, 150), color=(135, 206, 250))  # 天蓝色背景
    pixels = np.array(img)

    # 添加一些柔和的渐变，避免随机噪声
    for y in range(150):
        for x in range(200):
            # 创建轻微的径向渐变
            dx = x - 100
            dy = y - 75
            distance = np.sqrt(dx**2 + dy**2)
            gradient_factor = 1.0 - (distance / 150) * 0.1

            # 确保颜色值在有效范围内 (0-255)
            r_value = max(0, min(255, int(135 * gradient_factor + 120)))
            g_value = max(0, min(255, int(206 * gradient_factor + 190)))
            b_value = max(0, min(255, int(250 * gradient_factor + 240)))

            pixels[y, x] = [r_value, g_value, b_value]

    # 添加一些固定的柔和圆形区域
    fixed_regions = [
        {'x': 50, 'y': 40, 'radius': 20, 'color': [150, 160, 180]},
        {'x': 150, 'y': 60, 'radius': 25, 'color': [160, 170, 190]},
        {'x': 100, 'y': 100, 'radius': 18, 'color': [140, 150, 170]}
    ]

    for region in fixed_regions:
        y_grid, x_grid = np.ogrid[:150, :200]
        mask = (x_grid - region['x'])**2 + (y_grid - region['y'])**2 <= region['radius']**2

        for i in range(3):
            pixels[mask, i] = region['color'][i]

    # 添加几个固定的高亮点
    fixed_points = [
        {'x': 30, 'y': 30, 'radius': 3, 'color': [255, 250, 240]},
        {'x': 170, 'y': 50, 'radius': 4, 'color': [250, 245, 235]},
        {'x': 80, 'y': 110, 'radius': 3, 'color': [255, 248, 238]},
        {'x': 120, 'y': 40, 'radius': 2, 'color': [252, 246, 236]}
    ]

    for point in fixed_points:
        y_grid, x_grid = np.ogrid[:150, :200]
        mask = (x_grid - point['x'])**2 + (y_grid - point['y'])**2 <= point['radius']**2

        for i in range(3):
            pixels[mask, i] = point['color'][i]

    img = Image.fromarray(pixels.astype(np.uint8))

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()

    return {
        'type': 'realtime_data',
        'timestamp': datetime.now().isoformat(),
        'frame_count': np.random.randint(100000, 200000),
        'series': [{'t': 0.0, 'value': float(signal_value)}],
        'roi_data': {
            'width': 200,
            'height': 150,
            'pixels': f'data:image/png;base64,{img_str}'
        }
    }

@app.post('/control')
async def control(command: str = 'start_detection', password: str = '31415'):
    if password != '31415':
        raise HTTPException(status_code=401, detail="Invalid password")

    global detection_active

    if command == 'start_detection':
        detection_active = True
        return {'status': 'success', 'message': 'Detection started'}
    elif command == 'stop_detection':
        detection_active = False
        return {'status': 'success', 'message': 'Detection stopped'}
    elif command == 'pause_detection':
        detection_active = False
        return {'status': 'success', 'message': 'Detection paused'}
    elif command == 'resume_detection':
        detection_active = True
        return {'status': 'success', 'message': 'Detection resumed'}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown command: {command}")

@app.get('/data/roi-window-capture-with-peaks')
async def get_roi_capture_with_peaks(count: int = 100):
    if count < 50:
        raise HTTPException(status_code=400, detail="Count must be at least 50")

    # 生成模拟ROI窗口数据
    times = [i * 0.05 for i in range(count)]  # 50ms间隔

    # 生成更真实的信号 - 包含基线、正弦波和噪声
    baseline = 30
    signal = []
    for i, t in enumerate(times):
        # 基础正弦波
        sine_wave = 3 * np.sin(t * 2)
        # 添加一些慢变化趋势
        trend = 2 * np.sin(t * 0.1)
        # 添加噪声
        noise = np.random.normal(0, 0.8)
        # 偶尔添加一些脉冲
        if np.random.random() < 0.05:  # 5%概率
            pulse = np.random.uniform(5, 10)
        else:
            pulse = 0

        value = baseline + sine_wave + trend + noise + pulse
        value = max(20, min(50, value))  # 限制范围
        signal.append(value)

    # 波峰检测
    peaks = []
    for i in range(1, len(signal)-1):
        if signal[i] > signal[i-1] and signal[i] > signal[i+1] and signal[i] > baseline + 3:
            # 确定波峰颜色
            if signal[i] > baseline + 7:
                color = 'red'  # 高峰
            else:
                color = 'green'  # 普通峰

            peaks.append({
                't': times[i],
                'value': signal[i],
                'peak_color': color,
                'peak_confidence': min(1.0, (signal[i] - baseline) / 10)
            })

    return {
        'success': True,
        'data': [{'t': t, 'value': v} for t, v in zip(times, signal)],
        'peaks': peaks,
        'baseline': baseline,
        'statistics': {
            'data_points': len(signal),
            'peaks_found': len(peaks),
            'signal_range': {
                'min': min(signal),
                'max': max(signal),
                'mean': np.mean(signal)
            }
        }
    }

# 配置管理API端点
CONFIG_FILE = "fem_config.json"

# 默认配置
DEFAULT_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "api_port": 8421,
        "socket_port": 30415,
        "max_clients": 10,
        "enable_cors": True,
        "allowed_origins": ["*"]
    },
    "data_processing": {
        "fps": 45,
        "buffer_size": 100,
        "max_frame_count": 10000
    },
    "roi_capture": {
        "frame_rate": 2,
        "update_interval": 0.5,
        "default_config": {
            "x1": 0,
            "y1": 0,
            "x2": 200,
            "y2": 150
        }
    },
    "peak_detection": {
        "threshold": 102.7,
        "margin_frames": 6,
        "difference_threshold": 2.3,
        "min_region_length": 4
    },
    "security": {
        "password": "31415"
    },
    "logging": {
        "level": "INFO"
    }
}

def load_config():
    """加载配置文件"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return DEFAULT_CONFIG.copy()
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(config):
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

@app.get('/config')
async def get_config(password: str = '31415'):
    """获取配置"""
    if password != '31415':
        raise HTTPException(status_code=401, detail="密码错误")

    config = load_config()
    return {"config": config}

@app.post('/config')
async def update_config(
    config_data: Optional[str] = None,
    password: str = '31415'
):
    """更新配置"""
    if password != '31415':
        raise HTTPException(status_code=401, detail="密码错误")

    try:
        if config_data:
            # 解析配置数据
            updates = json.loads(config_data)
            config = load_config()

            # 更新配置
            for section, values in updates.items():
                if section in config and isinstance(values, dict):
                    config[section].update(values)
                else:
                    config[section] = values

            # 保存配置
            if save_config(config):
                return {"success": True, "message": "配置更新成功"}
            else:
                return {"success": False, "error": "配置保存失败"}
        else:
            return {"success": False, "error": "没有提供配置数据"}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="配置数据JSON格式错误")
    except Exception as e:
        return {"success": False, "error": f"更新配置失败: {str(e)}"}

if __name__ == '__main__':
    print('Starting NewFEM Complete Test Server on http://localhost:8422')
    print('Available endpoints:')
    print('   GET  /health')
    print('   GET  /status')
    print('   GET  /data/realtime')
    print('   POST /control')
    print('   GET  /data/roi-window-capture-with-peaks')
    print('   GET  /config')
    print('   POST /config')
    print('Server ready for HTTP client testing!')
    uvicorn.run(app, host='0.0.0.0', port=8422)