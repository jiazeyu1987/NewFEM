# NewFEM API 接口规范

## 1. 概述

本文档定义了 NewFEM 系统前后端通信的完整 API 接口规范，包括 RESTful API 协议、数据格式定义、错误处理机制和实时数据同步策略。该系统采用标准 HTTP 协议替代 WebSocket，提供高兼容性和易于集成的通信方式。

## 2. 基础信息

### 2.1 服务配置
- **基础 URL**: `http://localhost:8421`
- **协议版本**: HTTP/1.1
- **内容类型**: `application/json`
- **字符编码**: UTF-8
- **时区**: UTC (ISO 8601 格式)

### 2.2 认证机制
- **认证方式**: 固定密码认证
- **密码**: `31415`
- **传输方式**: 表单字段 (application/x-www-form-urlencoded)
- **适用范围**: 控制命令端点

### 2.3 CORS 配置
- **开发环境**: 允许所有来源 (`*`)
- **生产环境**: 指定域名白名单
- **支持方法**: GET, POST, PUT, DELETE, OPTIONS
- **支持头部**: 所有标准 HTTP 头部

### 2.4 通用响应格式

#### 2.4.1 成功响应格式
```json
{
    "type": "response_type",
    "timestamp": "2025-01-15T10:30:25.123456",
    "success": true,
    "data": {}
}
```

#### 2.4.2 错误响应格式
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

#### 2.4.3 时间戳格式
- **格式**: ISO 8601 (YYYY-MM-DDTHH:mm:ss.ssssssZ)
- **时区**: UTC
- **精度**: 毫秒级精度
- **示例**: "2025-01-15T10:30:25.123456Z"

## 3. 系统管理接口

### 3.1 健康检查

#### 3.1.1 接口定义
- **方法**: GET
- **路径**: `/health`
- **描述**: 检查服务器运行状态
- **用途**: 负载均衡器健康检查、系统监控

#### 3.1.2 请求参数
无参数

#### 3.1.3 响应格式
```json
{
    "status": "ok",
    "system": "NewFEM API Server",
    "version": "3.0.0"
}
```

#### 3.1.4 状态码
- **200 OK**: 服务正常
- **503 Service Unavailable**: 服务不可用

#### 3.1.5 性能要求
- **响应时间**: < 10ms
- **并发支持**: 100+ 并发请求
- **负载类型**: 轻量级健康检查

### 3.2 系统状态

#### 3.2.1 接口定义
- **方法**: GET
- **路径**: `/status`
- **描述**: 获取系统运行状态和性能指标
- **用途**: 前端状态监控、系统性能分析

#### 3.2.2 请求参数
无参数

#### 3.2.3 响应格式
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

#### 3.2.4 字段说明
- `status`: 系统运行状态
  - `running`: 正常运行
  - `stopped`: 已停止
  - `error`: 错误状态
- `frame_count`: 已处理的总帧数
- `current_value`: 当前 ROI 灰度值 (0-255)
- `peak_signal`: 当前波峰信号
  - `1`: 绿色波峰 (强 HEM 事件)
  - `0`: 红色波峰 (弱 HEM 事件)
  - `null`: 无波峰
- `buffer_size`: 当前缓冲区大小
- `baseline`: 60帧移动平均基线值

#### 3.2.5 状态码
- **200 OK**: 成功获取状态
- **500 Internal Server Error**: 服务器内部错误

#### 3.2.6 更新频率
- **推荐频率**: 每 5 秒
- **最大频率**: 每秒 1 次
- **数据新鲜度**: 实时数据

## 4. 实时数据接口

### 4.1 实时数据获取

#### 4.1.1 接口定义
- **方法**: GET
- **路径**: `/data/realtime`
- **描述**: 获取实时数据流用于前端可视化
- **用途**: 实时图表更新、数据分析监控

#### 4.1.2 请求参数
- **count** (可选): 数据点数量
  - 类型: Integer
  - 范围: 1-1000
  - 默认值: 100
  - 描述: 返回的数据点数量

#### 4.1.3 请求示例
```http
GET /data/realtime?count=50
GET /data/realtime
```

#### 4.1.4 响应格式
```json
{
    "type": "realtime_data",
    "timestamp": "2025-01-15T10:30:25.123456",
    "frame_count": 1234,
    "series": [
        {
            "t": 0.0,
            "value": 120.5
        },
        {
            "t": 0.016,
            "value": 121.2
        },
        {
            "t": 0.032,
            "value": 122.8
        }
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

#### 4.1.5 字段说明
- `type`: 固定值 "realtime_data"
- `series`: 时间序列数据数组
  - `t`: 相对时间戳 (秒)
  - `value`: 灰度值 (0-255)
- `roi_data`: ROI 区域数据
  - `width`: ROI 宽度 (像素)
  - `height`: ROI 高度 (像素)
  - `pixels`: ROI 数据内容
  - `gray_value`: 平均灰度值
  - `format`: 数据格式 ("text" 或 "base64")
- `peak_signal`: 波峰检测结果
- `baseline`: 计算基线值

#### 4.1.6 状态码
- **200 OK**: 成功获取数据
- **400 Bad Request**: 参数无效
- **500 Internal Server Error**: 服务器内部错误

#### 4.1.7 性能要求
- **响应时间**: < 100ms
- **数据新鲜度**: < 50ms
- **数据量**: 支持 1-1000 个数据点
- **并发支持**: 10+ 并发请求

#### 4.1.8 使用频率
- **推荐频率**: 每 50ms (20 FPS)
- **最大频率**: 每 10ms (100 FPS)
- **数据新鲜度**: 实时数据流

### 4.2 数据轮询策略

#### 4.2.1 轮询间隔
- **实时数据**: 50ms 间隔 (20 FPS)
- **系统状态**: 5000ms 间隔 (0.2 FPS)
- **连接检查**: 10000ms 间隔 (0.1 FPS)

#### 4.2.2 轮询实现
```javascript
// 实时数据轮询 (20 FPS)
setInterval(async () => {
    if (appState.connected) {
        const response = await fetch('/data/realtime?count=100');
        const data = await response.json();
        // 处理数据
    }
}, 50);
```

#### 4.2.3 错误处理
```javascript
try {
    const response = await fetch('/data/realtime?count=100');
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
} catch (error) {
    console.error('数据获取失败:', error);
    // 重试或错误处理
}
```

## 5. 控制命令接口

### 5.1 控制命令发送

#### 5.1.1 接口定义
- **方法**: POST
- **路径**: `/control`
- **描述**: 发送控制命令并执行相应操作
- **用途**: 系统控制、检测流程管理

#### 5.1.2 请求格式
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: 密码验证 (必需)

#### 5.1.3 请求参数
- **command** (必需): 控制命令类型
  - 类型: String
  - 枚举值见下方支持的命令
- **password** (必需): 认证密码
  - 类型: String
  - 固定值: `31415`

#### 5.1.4 请求示例
```http
POST /control
Content-Type: application/x-www-form-urlencoded

command=PEAK_SIGNAL&password=31415
```

#### 5.1.5 支持的命令类型

##### PEAK_SIGNAL - 获取波峰信号
- **功能**: 获取当前波峰检测结果
- **参数**: 无额外参数
- **响应**:

```json
{
    "type": "peak_signal",
    "timestamp": "2025-01-15T10:30:25.123456",
    "signal": 1,
    "has_peak": true,
    "current_value": 125.67,
    "frame_count": 1234
}
```

##### STATUS - 获取系统状态
- **功能**: 获取详细系统状态
- **参数**: 无额外参数
- **响应**:

```json
{
    "type": "status",
    "timestamp": "2025-01-15T10:30:25.123456",
    "server_status": "running",
    "connected_clients": 1,
    "last_peak_signal": 1
}
```

##### start_detection - 开始检测
- **功能**: 启动实时检测流程
- **参数**: 无额外参数
- **响应**:

```json
{
    "type": "control_response",
    "timestamp": "2025-01-15T10:30:25.123456",
    "command": "start_detection",
    "status": "success",
    "message": "Detection started"
}
```

##### stop_detection - 停止检测
- **功能**: 停止实时检测流程
- **参数**: 无额外参数
- **响应**:

```json
{
    "type": "control_response",
    "timestamp": "2025-01-15T10:30:25.123456",
    "command": "stop_detection",
    "status": "success",
    "message": "Detection stopped"
}
```

##### pause_detection - 暂停检测
- **功能**: 暂停实时检测流程
- **参数**: 无额外参数
- **响应**:

```json
{
    "type": "control_response",
    "timestamp": "2025-01-15T10:30:25.123456",
    "command": "pause_detection",
    "status": "success",
    "message": "Detection paused"
}
```

##### resume_detection - 恢复检测
- **功能**: 恢复实时检测流程
- **参数**: 无额外参数
- **响应**:

```json
{
    "type": "control_response",
    "timestamp": "2025-01-15T10:30:25.123456",
    "command": "resume_detection",
    "status": "success",
    "message": "Detection resumed"
}
```

#### 5.1.6 认证处理
```python
def handle_control(command: str = Form(...), password: str = Form(...)):
    """控制命令处理"""
    if password != "31415":
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid password"}
        )

    # 处理命令逻辑
    # ...
```

#### 5.1.7 状态码
- **200 OK**: 命令执行成功
- **400 Bad Request**: 无效参数或命令
- **401 Unauthorized**: 认证失败
- **500 Internal Server Error**: 服务器错误

## 6. 视频分析接口

### 6.1 视频分析处理

#### 6.1.1 接口定义
- **方法**: POST
- **路径**: `/analyze`
- **描述**: 分析视频文件或执行实时分析
- **用途**: 离线视频分析、实时数据分析

#### 6.1.2 请求格式
- **Content-Type**: `multipart/form-data`

#### 6.1.3 请求参数

##### 实时分析模式
- **realtime** (必需): 是否实时分析
  - 类型: Boolean
  - 枚举值: true/false
- **duration** (可选): 分析持续时间
  - 类型: Float
  - 单位: 秒
  - 默认值: 10.0

##### 视频文件分析模式
- **file** (必需): 视频文件
  - 类型: File
  - 格式: MP4, AVI, MOV
  - 大小: 最大 100MB
- **roi_x**, **roi_y**, **roi_w**, **roi_h** (可选): ROI 坐标
  - 类型: Float
  - 范围: 0.0-1.0 (归一化坐标)
- **sample_fps** (可选): 采样帧率
  - 类型: Float
  - 范围: 1.0-60.0
  - 默认值: 8.0

#### 6.1.4 请求示例

##### 实时分析请求
```http
POST /analyze
Content-Type: multipart/form-data

realtime=true&duration=10.0
```

##### 视频文件分析请求
```http
POST /analyze
Content-Type: multipart/form-data

file=@video.mp4&roi_x=0.5&roi_y=0.5&roi_w=0.2&roi_h=0.2&sample_fps=8.0
```

#### 6.1.5 响应格式
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

#### 6.1.6 字段说明
- `has_hem`: 是否检测到 HEM 事件
- `events`: 检测到的事件列表
  - `t`: 事件时间戳 (秒)
  - `type`: 事件类型
  - `score`: 事件评分/置信度
- `baseline`: 计算基线值
- `series`: 分析的时间序列数据
  - `t`: 时间戳
  - `value`: ROI 平均灰度值
  - `ref`: 参考区域灰度值
  - `std`: 标准差
  - `high`: 高灰度像素比例
  - `orange`: 条件高灰度像素比例
- `realtime`: 是否为实时分析模式
- `peak_signal`: 当前波峰信号
- `frame_count`: 处理的帧数

#### 6.1.7 状态码
- **200 OK**: 分析完成
- **400 Bad Request**: 参数错误
- **413 Request Entity Too Large**: 文件过大
- **422 Unprocessable Entity**: 文件格式不支持
- **500 Internal Server Error**: 分析错误

## 7. 数据格式规范

### 7.1 基础数据类型

#### 7.1.1 时间戳
```json
"timestamp": "2025-01-15T10:30:25.123456Z"
```

#### 7.1.2 数值类型
- **Float**: 浮点数 (Python float)
- **Integer**: 整数 (Python int)
- **Boolean**: 布尔值 (Python bool)
- **String**: 字符串 (Python str)

#### 7.1.3 数组类型
```json
"series": [
    {
        "t": 0.0,
        "value": 120.5
    },
    {
        "t": 0.016,
        "value": 121.2
    }
]
```

### 7.2 输入数据规范

#### 7.2.1 ROI 坐标
```json
{
    "roi_x": 0.5,    // 归一化 X 坐标 (0-1)
    "roi_y": 0.5,    // 归一化 Y 坐标 (0-1)
    "roi_w": 0.2,    // 归一化宽度 (0-1)
    "roi_h": 0.2     // 归一化高度 (0-1)
}
```

#### 7.2.2 检测参数
```json
{
    "sample_fps": 8.0,           // 采样帧率
    "methods": "sudden,threshold,relative",  // 检测方法
    "smooth_k": 3,                // 平滑窗口大小
    "baseline_n": 60,             // 基线计算帧数
    "sudden_k": 5.0,              // 突增检测阈值
    "sudden_min": 10.0,            // 最小突增量
    "threshold_delta": 5.0,         // 阈值检测偏移
    "threshold_hold": 5,            // 阈值保持帧数
    "relative_delta": 10.0          // 相对检测阈值
}
```

### 7.3 输出数据规范

#### 7.3.1 事件数据
```json
{
    "events": [
        {
            "t": 10.5,           // 事件时间 (秒)
            "type": "peak_detected",  // 事件类型
            "score": 1.0            // 事件评分
        }
    ]
}
```

#### 7.3.2 分析结果
```json
{
    "has_hem": true,              // 布尔检测标志
    "baseline": 120.5,           // 基线值
    "peak_signal": 1,            // 当前波峰信号
    "frame_count": 1234         // 处理帧数
}
```

## 8. 错误处理规范

### 8.1 HTTP 状态码

#### 8.1.1 客户端错误 (4xx)
- **400 Bad Request**: 请求参数错误
  - 无效的参数值
  - 缺少必需参数
  - 参数类型错误
- **401 Unauthorized**: 认证失败
  - 无效的密码
  - 缺少认证信息
- **403 Forbidden**: 权限不足
  - 操作不被允许
- **404 Not Found**: 资源不存在
  - 端点不存在
  - 文件未找到
- **409 Conflict**: 资源冲突
  - 请求冲突
  - 并发操作冲突
- **413 Request Entity Too Large**: 请求体过大
  - 文件过大
  - 数据量超限
- **422 Unprocessable Entity**: 无法处理的实体
  - 文件格式不支持
  - 数据格式错误

#### 8.1.2 服务器错误 (5xx)
- **500 Internal Server Error**: 服务器内部错误
  - 应用程序错误
  - 数据库错误
  - 第三方服务错误
- **502 Bad Gateway**: 网关错误
  - 上游服务错误
  - 网络配置错误
- **503 Service Unavailable**: 服务不可用
  - 服务过载
  - 维护模式
- **504 Gateway Timeout**: 网关超时
  - 处理超时
  - 上游超时

### 8.2 业务错误代码

#### 8.2.1 参数错误
- `INVALID_PARAMETER`: 参数值无效
- `MISSING_ARGUMENT`: 缺少必需参数
- `INVALID_ARGUMENT_TYPE`: 参数类型错误
- `OUT_OF_RANGE`: 参数超出范围

#### 8.2.2 系统错误
- `SYSTEM_ERROR`: 系统内部错误
- `DATABASE_ERROR`: 数据库错误
- `NETWORK_ERROR`: 网络连接错误
- `RESOURCE_EXHAUSTED`: 资源耗尽

#### 8.2.3 业务逻辑错误
- `DETECTION_FAILED`: 检测失败
- `ANALYSIS_ERROR`: 分析错误
- `VALIDATION_FAILED`: 验证失败

### 8.3 错误响应示例

#### 8.3.1 参数验证错误
```json
{
    "type": "error",
    "timestamp": "2025-01-15T10:30:25.123456",
    "error_code": "INVALID_PARAMETER",
    "error_message": "Parameter 'count' must be a positive integer",
    "details": {
        "parameter": "count",
        "provided": "-5",
        "constraint": "must be >= 1 and <= 1000"
    }
}
```

#### 8.3.2 系统错误
```json
{
    "type": "error",
    "timestamp": "2025-01-15T10:30:25.123456",
    "error_code": "SYSTEM_ERROR",
    "error_message": "Internal server error occurred",
    "details": {
        "exception": "ValueError",
        "message": "Invalid data format"
    }
}
```

### 8.4 错误处理策略

#### 8.4.1 客户端处理
```javascript
try {
    const response = await fetch(url, options);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error_message);
    }
    return await response.json();
} catch (error) {
    console.error('API调用失败:', error);
    // 重试或降级处理
}
```

#### 8.4.2 重试机制
```javascript
const retryConfig = {
    maxRetries: 3,
    retryDelay: 1000,
    retryCondition: (error) => error.status >= 500
};

async function fetchWithRetry(url, options) {
    let lastError;

    for (let i = 0; i < retryConfig.maxRetries; i++) {
        try {
            const response = await fetch(url, options);
            return response.json();
        } catch (error) {
            lastError = error;
            if (!retryConfig.retryCondition(error) || i === retryConfig.maxRetries - 1) {
                throw error;
            }
            await new Promise(resolve => setTimeout(resolve, retryConfig.retryDelay));
        }
    }

    throw lastError;
}
```

## 9. 实时数据同步

### 9.1 同步策略

#### 9.1.1 轮询模式
- **实时数据**: 50ms 间隔 (20 FPS)
- **系统状态**: 5000ms 间隔 (0.2 FPS)
- **连接检查**: 10000ms 间隔 (0.1 FPS)

#### 9.1.2 数据新鲜度
- **实时数据**: 要求 < 100ms 延迟
- **状态数据**: 要求 < 5 秒延迟
- **连接状态**: 要求 < 10 秒延迟

#### 9.1.3 自动重连
- **重连间隔**: 5 秒
- **最大重试**: 无限次
- **退避策略**: 指数退避

### 9.2 连接管理

#### 9.2.1 连接状态
```javascript
const ConnectionState = {
    DISCONNECTED: 'disconnected',
    CONNECTING: 'connecting',
    CONNECTED: 'connected',
    ERROR: 'error'
};
```

#### 9.2.2 自动重连实现
```javascript
class ConnectionManager {
    async connect() {
        this.state = ConnectionState.CONNECTING;

        try {
            const response = await fetch('/health');
            if (response.ok) {
                this.state = ConnectionState.CONNECTED;
                this.startDataPolling();
            }
        } catch (error) {
            this.state = ConnectionState.ERROR;
            this.scheduleReconnect();
        }
    }

    scheduleReconnect() {
        setTimeout(() => {
            if (this.state !== ConnectionState.CONNECTED) {
                this.connect();
            }
        }, 5000);
    }
}
```

### 9.3 数据一致性

#### 9.3.1 时间戳同步
- **时间戳格式**: ISO 8601 UTC
- **时钟同步**: NTP 时间同步
- **精度要求**: 毫秒级精度

#### 9.3.2 数据版本控制
- **版本号**: 数据结构版本标识
- **兼容性**: 向后兼容支持
- **迁移策略**: 平滑版本升级

## 10. 性能优化

### 10.1 请求优化

#### 10.1.1 请求合并
- **批量操作**: 合并多个小请求
- **数据缓存**: 缓存重复请求数据
- **请求压缩**: 启用响应压缩

#### 10.1.2 条件请求
- **条件查询**: 只在数据变化时请求
- **增量更新**: 只请求变化的部分数据
- **智能轮询**: 根据网络状况调整频率

### 10.2 响应优化

#### 10.2.1 数据压缩
- **HTTP 压缩**: 启用 gzip 压缩
- **数据精简**: 移除冗余字段
- **二进制编码**: 大数据二进制传输

#### 10.2.2 缓存策略
- **客户端缓存**: 浏览器缓存控制
- **服务器缓存**: 内存缓存热点数据
- **CDN 缓存**: CDN 边缘节点缓存

### 10.3 并发优化

#### 10.3.1 连接池
- **HTTP Keep-Alive**: 保持连接复用
- **连接复用**: 避免频繁建立连接
- **并发控制**: 限制并发请求数量

#### 10.3.2 负载均衡
- **多实例部署**: 支持多实例部署
- **负载分发**: 智权负载分发
- **健康检查**: 实例健康状态监控

## 11. 安全规范

### 11.1 认证安全

#### 11.1.1 密码策略
- **密码强度**: 长度 >= 8 字符
- **密码复杂度**: 包含数字、字母、特殊字符
- **密码轮换**: 定期更换密码

#### 11.1.2 密码传输
- **HTTPS**: 生产环境强制 HTTPS
- **加密传输**: 敏感数据加密传输
- **哈希存储**: 密码哈希存储

### 11.2 输入验证

#### 11.2.1 参数验证
- **类型检查**: 严格类型验证
- **范围检查**: 参数范围验证
- **格式检查**: 数据格式验证

#### 11.2.2 输入清理
- **XSS 防护**: 输入内容清理
- **SQL 注入防护**: 参数化查询
- **命令注入防护**: 命令参数清理

### 11.3 访问控制

#### 11.3.1 CORS 配置
- **开发环境**: 允许所有来源
- **生产环境**: 指定域名白名单
- **预检请求**: 支持 CORS 预检

#### 11.3.2 速率限制
- **请求频率**: 限制请求频率
- **并发限制**: 限制并发连接数
- **IP 限制**: IP 地址访问限制

## 12. 部署配置

### 12.1 环境配置

#### 12.1.1 开发环境
- **主机**: `localhost`
- **端口**: 8421
- **协议**: HTTP
- **CORS**: 全开放

#### 12.1.2 生产环境
- **主机**: 生产域名
- **端口**: 443 (HTTPS)
- **协议**: HTTPS
- **CORS**: 指定域名

#### 12.1.3 测试环境
- **主机**: 测试域名
- **端口**: 8421
- **协议**: HTTP
- **CORS**: 限制域名

### 12.2 部署变量

#### 12.2.1 服务器配置
```python
# 环境变量配置
NEWFEM_HOST=0.0.0.0
NEWFEM_PORT=8421
NEWFEM_LOG_LEVEL=INFO
NEWFEM_MAX_CLIENTS=10
```

#### 12.2.2 性能配置
```python
# 性能调优
NEWFEM_BUFFER_SIZE=100
NEWFEM_FRAME_RATE=60
NEWFEM_API_TIMEOUT=30
NEWFEM_MAX_REQUEST_SIZE=1048576
```

#### 12.2.3 安全配置
```python
# 安全配置
NEWFEM_PASSWORD=31415
NEWFEM_ENABLE_CORS=True
NEWFEM_ALLOWED_ORIGINS=*
NEWFEM_RATE_LIMIT=100
```

---

此 API 接口规范定义了 NewFEM 系统的完整通信协议，为前后端开发、系统集成和第三方集成提供详细的接口文档和使用指导。