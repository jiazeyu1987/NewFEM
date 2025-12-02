# NewFEM 数据规范文档

## 1. 概述

本文档定义了 NewFEM 系统中所有数据的格式、结构、存储和处理规范。数据规范确保前后端数据交换的一致性和系统集成的可靠性，涵盖实时数据、分析结果、系统状态等所有数据类型。

## 2. 数据类型体系

### 2.1 基础数据类型

#### 2.1.1 时间戳类型
```json
{
    "timestamp": "2025-01-15T10:30:25.123456Z"
}
```

- **格式**: ISO 8601 (YYYY-MM-DDTHH:mm:ss.ssssssZ)
- **时区**: UTC
- **精度**: 微秒级精度
- **用途**: 统一时间基准，支持跨时区数据处理

#### 2.1.2 数值类型定义

**Float 类型**:
- **范围**: 64位浮点数 (IEEE 754)
- **精度**: 双精度浮点数
- **示例**: `120.5`, `0.001`, `1.23456789e-10`

**Integer 类型**:
- **范围**: 32位有符号整数
- **最小值**: -2,147,483,648
- **最大值**: 2,147,483,647
- **示例**: `1234`, `0`, `-1`

**Boolean 类型**:
- **值域**: `true`, `false`
- **用途**: 状态标志、开关控制
- **默认值**: `false`

**String 类型**:
- **编码**: UTF-8
- **长度**: 最大 1024 字符
- **用途**: 文本描述、标识符

### 2.2 复杂数据类型

#### 2.2.1 时间序列数据点
```json
{
    "t": 0.0,
    "value": 120.5
}
```

**字段说明**:
- `t`: 相对时间戳 (秒，浮点数)
- `value`: 数值 (灰度值、测量值等)

**约束条件**:
- `t`: ≥ 0, 单调递增
- `value`: 0-255 (灰度值范围)

#### 2.2.2 时间序列数组
```json
"series": [
    {"t": 0.0, "value": 120.5},
    {"t": 0.016, "value": 121.2},
    {"t": 0.032, "value": 122.8}
]
```

**约束条件**:
- 最大长度: 1000 个数据点
- 时间间隔: 均匀分布 (推荐 60 FPS)
- 数值类型: 浮点数

## 3. 实时数据规范

### 3.1 实时数据响应格式

#### 3.1.1 完整数据结构
```json
{
    "type": "realtime_data",
    "timestamp": "2025-01-15T10:30:25.123456Z",
    "frame_count": 1234,
    "series": [
        {"t": 0.0, "value": 120.5},
        {"t": 0.016, "value": 121.2},
        {"t": 0.032, "value": 122.8}
    ],
    "roi_data": {
        "width": 200,
        "height": 150,
        "pixels": "simulated_roi_120.5",
        "gray_value": 120.5,
        "format": "text"
    },
    "peak_signal": 1,
    "baseline": 120.5
}
```

#### 3.1.2 字段详细说明

**元数据字段**:
- `type`: 数据类型标识符，固定值 "realtime_data"
- `timestamp`: ISO 8601 时间戳，数据生成时间
- `frame_count`: 累计帧数计数器，单调递增

**时间序列字段**:
- `series`: 时间序列数据数组
- `series[i].t`: 相对时间戳，从序列开始计算
- `series[i].value`: ROI 平均灰度值 (0-255)

**ROI 数据字段**:
- `roi_data`: 感兴趣区域数据对象
- `roi_data.width`: ROI 宽度 (像素)
- `roi_data.height`: ROI 高度 (像素)
- `roi_data.pixels`: ROI 像素数据内容
- `roi_data.gray_value`: ROI 平均灰度值
- `roi_data.format`: 数据格式 ("text" 或 "base64")

**分析结果字段**:
- `peak_signal`: 波峰检测结果 (1/0/null)
- `baseline`: 基线计算值 (浮点数)

### 3.2 数据更新频率规范

#### 3.2.1 更新频率定义
- **实时数据**: 20 FPS (50ms 间隔)
- **系统状态**: 0.2 FPS (5000ms 间隔)
- **心跳检查**: 0.1 FPS (10000ms 间隔)

#### 3.2.2 数据新鲜度要求
- **实时数据**: 延迟 < 100ms
- **状态数据**: 延迟 < 5 秒
- **历史数据**: 容忍延迟 < 30 秒

### 3.3 数据质量约束

#### 3.3.1 数值范围约束
```json
{
    "constraints": {
        "gray_value": {"min": 0, "max": 255, "type": "uint8"},
        "baseline": {"min": 50, "max": 200, "type": "float"},
        "peak_signal": {"values": [0, 1, null], "type": "enum"},
        "frame_count": {"min": 0, "max": 4294967295, "type": "uint32"}
    }
}
```

#### 3.3.2 时间戳约束
- **单调性**: 时间戳必须单调递增
- **精度**: 毫秒级精度要求
- **连续性**: 相邻数据点时间间隔一致

## 4. ROI 数据规范

### 4.1 ROI 坐标规范

#### 4.1.1 归一化坐标系统
```json
{
    "roi_x": 0.5,
    "roi_y": 0.5,
    "roi_w": 0.2,
    "roi_h": 0.2
}
```

**坐标系统定义**:
- 原点: 图像左上角 (0, 0)
- X 轴: 水平向右 (0.0 - 1.0)
- Y 轴: 垂直向下 (0.0 - 1.0)
- 单位: 归一化比例 (相对于图像尺寸)

#### 4.1.2 ROI 约束条件
```json
{
    "constraints": {
        "roi_x": {"min": 0.0, "max": 1.0, "type": "float"},
        "roi_y": {"min": 0.0, "max": 1.0, "type": "float"},
        "roi_w": {"min": 0.01, "max": 1.0, "type": "float"},
        "roi_h": {"min": 0.01, "max": 1.0, "type": "float"},
        "boundary": "roi_x + roi_w <= 1.0 && roi_y + roi_h <= 1.0"
    }
}
```

### 4.2 ROI 数据格式规范

#### 4.2.1 文本格式
```json
{
    "format": "text",
    "pixels": "simulated_roi_120.5"
}
```

**特点**:
- 轻量级数据传输
- 适用于模拟数据
- 人类可读格式

#### 4.2.2 Base64 图像格式
```json
{
    "format": "base64",
    "pixels": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**特点**:
- 完整图像数据传输
- 支持任意图像格式
- Base64 编码，文本友好

### 4.3 ROI 数据尺寸规范

#### 4.3.1 标准尺寸定义
```json
{
    "standard_sizes": {
        "small": {"width": 100, "height": 75},
        "medium": {"width": 200, "height": 150},
        "large": {"width": 400, "height": 300}
    },
    "default": {"width": 200, "height": 150}
}
```

#### 4.3.2 尺寸约束
- **最小尺寸**: 50x50 像素
- **最大尺寸**: 1000x1000 像素
- **推荐比例**: 4:3 或 16:9
- **内存限制**: < 1MB 单幅图像

## 5. 分析结果数据规范

### 5.1 分析响应格式

#### 5.1.1 完整分析结果
```json
{
    "has_hem": true,
    "events": [
        {
            "t": 10.5,
            "type": "peak_detected",
            "score": 1.0
        },
        {
            "t": 15.2,
            "type": "threshold_exceeded",
            "score": 2.3
        }
    ],
    "baseline": 120.5,
    "series": [
        {
            "t": 0.0,
            "value": 120.5,
            "ref": 122.1,
            "std": 2.3,
            "high": 15.2,
            "orange": 8.7
        },
        {
            "t": 0.125,
            "value": 125.8,
            "ref": 124.2,
            "std": 3.1,
            "high": 18.7,
            "orange": 10.2
        }
    ],
    "realtime": true,
    "peak_signal": 1,
    "frame_count": 1234
}
```

#### 5.1.2 结果字段说明

**检测结果**:
- `has_hem`: HEM 事件检测结果 (布尔值)
- `events`: 检测到的事件列表
- `baseline`: 计算基线值 (浮点数)

**事件数据**:
- `events[i].t`: 事件时间戳 (秒)
- `events[i].type`: 事件类型标识符
- `events[i].score`: 事件置信度/评分

**详细时间序列**:
- `series[i].t`: 时间戳 (秒)
- `series[i].value`: ROI 平均灰度值
- `series[i].ref`: 参考区域灰度值
- `series[i].std`: 灰度值标准差
- `series[i].high`: 高灰度像素比例 (>130)
- `series[i].orange`: 条件高灰度像素比例 (>160 当平均 >120)

### 5.2 事件类型定义

#### 5.2.1 事件类型枚举
```json
{
    "event_types": {
        "peak_detected": {
            "description": "波峰检测事件",
            "severity": "high",
            "score_range": [0.0, 1.0]
        },
        "threshold_exceeded": {
            "description": "阈值超限事件",
            "severity": "medium",
            "score_range": [0.0, 5.0]
        },
        "sudden_change": {
            "description": "突增变化事件",
            "severity": "medium",
            "score_range": [0.0, 3.0]
        },
        "relative_change": {
            "description": "相对变化事件",
            "severity": "low",
            "score_range": [0.0, 2.0]
        }
    }
}
```

#### 5.2.2 事件严重程度
- **high**: 强 HEM 事件，需要立即关注
- **medium**: 中等强度事件，需要观察
- **low**: 弱 HEM 事件，正常范围

### 5.3 分析参数规范

#### 5.3.1 检测方法参数
```json
{
    "detection_parameters": {
        "smooth_k": {"default": 3, "min": 1, "max": 20, "type": "integer"},
        "baseline_n": {"default": 60, "min": 10, "max": 300, "type": "integer"},
        "sudden_k": {"default": 5.0, "min": 1.0, "max": 20.0, "type": "float"},
        "sudden_min": {"default": 10.0, "min": 1.0, "max": 50.0, "type": "float"},
        "threshold_delta": {"default": 5.0, "min": 1.0, "max": 20.0, "type": "float"},
        "threshold_hold": {"default": 5, "min": 1, "max": 30, "type": "integer"},
        "relative_delta": {"default": 10.0, "min": 1.0, "max": 30.0, "type": "float"}
    }
}
```

#### 5.3.2 算法配置
```json
{
    "algorithm_config": {
        "methods": "sudden,threshold,relative",
        "sample_fps": 8.0,
        "frame_buffer_size": 1000,
        "peak_detection_window": 5,
        "baseline_calculation_window": 60
    }
}
```

## 6. 系统状态数据规范

### 6.1 状态响应格式

#### 6.1.1 系统状态结构
```json
{
    "status": "running",
    "frame_count": 1234,
    "current_value": 125.67,
    "peak_signal": 1,
    "buffer_size": 100,
    "baseline": 120.5,
    "timestamp": "2025-01-15T10:30:25.123456"
}
```

#### 6.1.2 状态类型定义
```json
{
    "status_types": {
        "running": {
            "description": "系统正常运行",
            "code": 0
        },
        "stopped": {
            "description": "系统已停止",
            "code": 1
        },
        "error": {
            "description": "系统错误状态",
            "code": 2
        },
        "paused": {
            "description": "系统暂停状态",
            "code": 3
        }
    }
}
```

### 6.2 性能指标规范

#### 6.2.1 性能数据结构
```json
{
    "performance_metrics": {
        "cpu_usage": 15.2,
        "memory_usage": 256.7,
        "fps_actual": 59.8,
        "processing_latency": 12.5,
        "queue_size": 15,
        "error_rate": 0.01
    }
}
```

#### 6.2.2 性能阈值定义
```json
{
    "performance_thresholds": {
        "cpu_usage": {"warning": 70.0, "critical": 90.0},
        "memory_usage": {"warning": 1000.0, "critical": 2000.0},
        "fps_actual": {"warning": 55.0, "critical": 30.0},
        "processing_latency": {"warning": 20.0, "critical": 50.0},
        "error_rate": {"warning": 0.05, "critical": 0.10}
    }
}
```

## 7. 控制命令数据规范

### 7.1 命令请求格式

#### 7.1.1 HTTP 表单格式
```
Content-Type: application/x-www-form-urlencoded

command=PEAK_SIGNAL&password=31415
```

#### 7.1.2 命令类型枚举
```json
{
    "command_types": {
        "PEAK_SIGNAL": {
            "description": "获取波峰信号",
            "parameters": [],
            "response_type": "peak_signal"
        },
        "STATUS": {
            "description": "获取系统状态",
            "parameters": [],
            "response_type": "status"
        },
        "start_detection": {
            "description": "开始检测",
            "parameters": [],
            "response_type": "control_response"
        },
        "stop_detection": {
            "description": "停止检测",
            "parameters": [],
            "response_type": "control_response"
        },
        "pause_detection": {
            "description": "暂停检测",
            "parameters": [],
            "response_type": "control_response"
        },
        "resume_detection": {
            "description": "恢复检测",
            "parameters": [],
            "response_type": "control_response"
        }
    }
}
```

### 7.2 命令响应格式

#### 7.2.1 通用响应结构
```json
{
    "type": "response_type",
    "timestamp": "2025-01-15T10:30:25.123456",
    "success": true,
    "data": {}
}
```

#### 7.2.2 错误响应结构
```json
{
    "type": "error",
    "timestamp": "2025-01-15T10:30:25.123456",
    "error_code": "ERROR_CODE",
    "error_message": "Human readable error description",
    "details": {
        "parameter": "parameter_name",
        "value": "invalid_value",
        "constraint": "validation_constraint"
    }
}
```

## 8. 数据存储规范

### 8.1 内存数据结构

#### 8.1.1 循环缓冲区设计
```python
class CircularBuffer:
    def __init__(self, max_size=100):
        self.buffer = [None] * max_size
        self.head = 0
        self.tail = 0
        self.size = 0
        self.max_size = max_size

    def append(self, item):
        self.buffer[self.tail] = item
        self.tail = (self.tail + 1) % self.max_size
        if self.size < self.max_size:
            self.size += 1
        else:
            self.head = (self.head + 1) % self.max_size
```

#### 8.1.2 线程安全访问
```python
import threading

class ThreadSafeDataStore:
    def __init__(self):
        self.values = []
        self.timestamps = []
        self.lock = threading.Lock()
        self.max_buffer_size = 100

    def add_frame(self, value):
        with self.lock:
            self.values.append(value)
            self.timestamps.append(time.time())
            if len(self.values) > self.max_buffer_size:
                self.values.pop(0)
                self.timestamps.pop(0)
```

### 8.2 数据持久化规范

#### 8.2.1 数据导出格式
```json
{
    "export_format": {
        "version": "1.0",
        "created_at": "2025-01-15T10:30:25.123456Z",
        "session_id": "session_12345",
        "metadata": {
            "total_frames": 1234,
            "duration_seconds": 20.57,
            "fps": 60.0
        },
        "series": [
            {"t": 0.0, "value": 120.5},
            {"t": 0.016, "value": 121.2}
        ],
        "events": [
            {"t": 10.5, "type": "peak_detected", "score": 1.0}
        ]
    }
}
```

#### 8.2.2 CSV 导出格式
```csv
timestamp,relative_time,value,baseline,peak_signal,events
2025-01-15T10:30:25.123456Z,0.0,120.5,120.0,null,
2025-01-15T10:30:25.139456Z,0.016,121.2,120.1,null,
2025-01-15T10:30:35.123456Z,10.0,135.8,120.5,peak_detected,score:1.0
```

## 9. 数据验证规范

### 9.1 输入验证规则

#### 9.1.1 参数验证
```python
def validate_realtime_data_request(count):
    """验证实时数据请求参数"""
    if not isinstance(count, int):
        raise ValueError("Count must be integer")

    if count < 1 or count > 1000:
        raise ValueError("Count must be between 1 and 1000")

    return True
```

#### 9.1.2 ROI 坐标验证
```python
def validate_roi_coordinates(roi_x, roi_y, roi_w, roi_h):
    """验证 ROI 坐标参数"""
    if not all(0.0 <= val <= 1.0 for val in [roi_x, roi_y, roi_w, roi_h]):
        raise ValueError("ROI coordinates must be between 0.0 and 1.0")

    if roi_x + roi_w > 1.0 or roi_y + roi_h > 1.0:
        raise ValueError("ROI region exceeds image boundaries")

    return True
```

### 9.2 输出验证规则

#### 9.2.1 数据完整性检查
```python
def validate_series_data(series):
    """验证时间序列数据完整性"""
    if not series:
        return True

    # 检查时间戳单调性
    for i in range(1, len(series)):
        if series[i]['t'] <= series[i-1]['t']:
            raise ValueError("Timestamps must be monotonically increasing")

    # 检查灰度值范围
    for point in series:
        if not (0 <= point['value'] <= 255):
            raise ValueError("Gray values must be between 0 and 255")

    return True
```

#### 9.2.2 JSON Schema 验证
```json
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["realtime_data"]},
        "timestamp": {"type": "string", "format": "date-time"},
        "frame_count": {"type": "integer", "minimum": 0},
        "series": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "t": {"type": "number", "minimum": 0},
                    "value": {"type": "number", "minimum": 0, "maximum": 255}
                },
                "required": ["t", "value"]
            }
        },
        "peak_signal": {"type": ["integer", "null"], "enum": [0, 1, null]},
        "baseline": {"type": "number", "minimum": 0, "maximum": 255}
    },
    "required": ["type", "timestamp", "frame_count", "series", "peak_signal", "baseline"]
}
```

## 10. 数据传输优化

### 10.1 数据压缩策略

#### 10.1.1 HTTP 压缩
```http
Accept-Encoding: gzip, deflate
Content-Encoding: gzip
```

#### 10.1.2 数据精简策略
```json
{
    "optimization": {
        "remove_null_fields": true,
        "round_floats": 2,
        "compress_timestamps": true,
        "delta_encoding": true
    }
}
```

### 10.2 缓存策略

#### 10.2.1 客户端缓存
```http
Cache-Control: max-age=50
ETag: "1234567890"
Last-Modified: Mon, 15 Jan 2025 10:30:25 GMT
```

#### 10.2.2 服务端缓存
```python
from functools import lru_cache
import time

@lru_cache(maxsize=128)
def get_cached_realtime_data(count, cache_time):
    """缓存实时数据响应"""
    current_time = int(time.time() / 0.05)  # 50ms 粒度
    return generate_realtime_data_response(count)
```

## 11. 数据安全规范

### 11.1 数据加密

#### 11.1.1 传输加密
```http
# 生产环境强制 HTTPS
Location: https://api.newfem.com/data/realtime
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

#### 11.1.2 敏感数据处理
```python
def sanitize_output_data(data):
    """清理输出数据中的敏感信息"""
    sensitive_fields = ['internal_id', 'debug_info']
    for field in sensitive_fields:
        data.pop(field, None)
    return data
```

### 11.2 访问控制

#### 11.2.1 认证数据
```json
{
    "authentication": {
        "method": "password",
        "password": "31415",
        "required_endpoints": ["/control"]
    }
}
```

#### 11.2.2 速率限制
```json
{
    "rate_limiting": {
        "realtime_data": {"requests_per_second": 20},
        "control_commands": {"requests_per_second": 5},
        "analysis_requests": {"requests_per_minute": 10}
    }
}
```

---

此数据规范文档定义了 NewFEM 系统的完整数据体系，为系统开发、测试和集成提供详细的数据格式和约束规范。