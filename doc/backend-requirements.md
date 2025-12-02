# NewFEM 后端技术需求规范

## 1. 概述

NewFEM 后端是基于 FastAPI 框架的高性能 Python Web 服务，提供 HEM (高回声事件) 实时检测、数据处理和 API 服务。采用双协议架构设计，同时支持现代 RESTful API 和传统 Socket 通信协议。

## 2. 技术栈

- **Web 框架**: FastAPI 0.115.0
- **ASGI 服务器**: Uvicorn 0.30.6
- **数据处理**: NumPy 2.1.1
- **文件处理**: python-multipart 0.0.9
- **CORS 支持**: Starlette 0.38.4
- **多线程**: threading 模块
- **实时处理**: 基于时间的数据处理

## 3. 系统架构

### 3.1 双协议架构设计
```
[Data Source] → [60 FPS Capture] → [5-Frame Analysis] → [Data Store] → [RESTful API] → [Frontend]
                    ↓                          ↓                  ↓                ↓
               [Peak Detection]              [Buffer Manager]    [Legacy Socket] → [Legacy Clients]
```

### 3.2 核心组件
- **RESTful API 服务**: 现代 HTTP 接口 (端口 8421)
- **传统 Socket 服务**: 兼容性 TCP 接口 (端口 30415)
- **数据存储引擎**: 线程安全的时序数据管理
- **实时数据处理**: 60 FPS 数据生成和分析
- **5帧插值算法**: 核心波峰检测算法

### 3.3 数据流架构
```
实时数据流: 屏幕捕获 → ROI灰度提取 → 时间序列存储 → 波峰检测 → 信号输出 → 前端可视化
控制流:   用户指令 → 参数验证 → 状态更新 → 结果返回 → 界面更新
```

## 4. API 端点需求

### 4.1 健康检查端点

#### 4.1.1 接口定义
- **路径**: `GET /health`
- **功能**: 系统健康状态检查
- **用途**: 服务可用性监控、负载均衡健康检查

#### 4.1.2 响应格式
```json
{
    "status": "ok",
    "system": "NewFEM API Server"
}
```

#### 4.1.3 性能要求
- **响应时间**: < 10ms
- **并发支持**: 100+ 并发请求
- **负载类型**: 轻量级检查，无资源消耗

### 4.2 系统状态端点

#### 4.2.1 接口定义
- **路径**: `GET /status`
- **功能**: 获取当前系统运行状态
- **用途**: 前端状态监控、系统健康检查

#### 4.2.2 响应格式
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

#### 4.2.3 数据字段说明
- `status`: 系统运行状态 (running/stopped/error)
- `frame_count`: 已处理的帧数
- `current_value`: 当前 ROI 灰度值
- `peak_signal`: 当前波峰信号 (1/0/null)
- `buffer_size`: 当前缓冲区大小
- `baseline`: 当前基线值
- `timestamp`: 响应时间戳 (ISO 8601)

#### 4.2.4 性能要求
- **响应时间**: < 50ms
- **更新频率**: 支持高频查询
- **数据一致性**: 实时数据一致性保证

### 4.3 实时数据端点

#### 4.3.1 接口定义
- **路径**: `GET /data/realtime`
- **查询参数**: `count` (可选, 默认 100)
- **功能**: 获取实时数据流用于前端可视化
- **用途**: 实时图表更新、数据监控

#### 4.3.2 响应格式
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

#### 4.3.3 数据结构说明
- `type`: 数据类型标识
- `series`: 时间序列数据数组
- `series[i].t`: 相对时间戳 (秒)
- `series[i].value`: 灰度值 (0-255)
- `roi_data`: ROI 区域数据
- `peak_signal`: 波峰检测结果
- `baseline`: 计算基线值

#### 4.3.4 性能要求
- **响应时间**: < 100ms
- **数据量**: 支持 100-1000 个数据点
- **实时性**: 数据新鲜度 < 50ms

### 4.4 控制命令端点

#### 4.4.1 接口定义
- **路径**: `POST /control`
- **方法**: POST
- **认证**: 密码验证 (31415)
- **功能**: 接收控制命令并执行相应操作

#### 4.4.2 请求格式
```
Content-Type: application/x-www-form-urlencoded

command=PEAK_SIGNAL&password=31415
```

#### 4.4.3 支持的命令类型

**PEAK_SIGNAL**: 获取波峰信号
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

**STATUS**: 获取系统状态
```json
{
    "type": "status",
    "timestamp": "2025-01-15T10:30:25.123456",
    "server_status": "running",
    "connected_clients": 1,
    "last_peak_signal": 1
}
```

**检测控制命令**:
- `start_detection`: 开始检测
- `stop_detection`: 停止检测
- `pause_detection`: 暂停检测
- `resume_detection`: 恢复检测

```json
{
    "type": "control_response",
    "timestamp": "2025-01-15T10:30:25.123456",
    "command": "start_detection",
    "status": "success",
    "message": "Detection started"
}
```

#### 4.4.4 安全要求
- **密码验证**: 必须提供正确密码
- **命令验证**: 验证命令有效性
- **权限控制**: 最小权限原则
- **审计日志**: 记录所有控制操作

### 4.5 视频分析端点

#### 4.5.1 接口定义
- **路径**: `POST /analyze`
- **方法**: POST
- **认证**: 无 (公共端点)
- **功能**: 视频文件分析或实时分析

#### 4.5.2 请求参数

**实时分析模式**:
```
Content-Type: multipart/form-data

realtime=true&duration=10.0
```

**视频文件分析**:
```
Content-Type: multipart/form-data

file=@video.mp4&roi_x=0.5&roi_y=0.5&roi_w=0.2&roi_h=0.2&sample_fps=8.0
```

#### 4.5.3 响应格式
```json
{
    "has_hem": true,
    "events": [
        {
            "t": 10.5,
            "type": "peak_detected",
            "score": 1.0
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
        }
    ],
    "realtime": true,
    "peak_signal": 1,
    "frame_count": 1234
}
```

## 5. 数据处理需求

### 5.1 数据存储引擎

#### 5.1.1 NewFEMData 类设计
```python
class NewFEMData:
    def __init__(self):
        self.values = []           # 灰度值数组
        self.timestamps = []       # 时间戳数组
        self.signal = None         # 当前波峰信号
        self.frame_count = 0      # 帧数计数
        self.lock = threading.Lock()  # 线程锁
        self.max_buffer_size = 100 # 最大缓冲区大小
        self.running = False       # 运行状态标志
```

#### 5.1.2 核心方法需求

**add_frame(value)**:
- 功能: 线程安全地添加新的帧数据
- 参数: 灰度值 (float)
- 处理: 时间戳记录、缓冲区管理、帧数统计

**get_recent_frames(count)**:
- 功能: 获取最近的帧数据
- 参数: 数据点数量 (int)
- 返回: 时间序列数据数组
- 格式: 相对时间戳 + 灰度值

**get_baseline()**:
- 功能: 计算基线值
- 算法: 60帧移动平均
- 返回: 基线值 (float)

#### 5.1.3 线程安全要求
- 所有数据操作必须使用线程锁保护
- 缓冲区操作必须是原子性的
- 时间戳必须使用统一的时间源

### 5.2 实时数据生成

#### 5.2.1 数据生成引擎
```python
def generate_mock_data():
    """生成模拟的超声波数据"""
    base_value = 120.0
    noise = np.random.uniform(-3, 3)

    # 模拟周期性波峰
    if data_store.frame_count % 100 == 50:
        base_value += np.random.uniform(8, 15)
    elif data_store.frame_count % 100 == 70:
        base_value += np.random.uniform(-8, 0)

    return base_value + noise
```

#### 5.2.2 生成需求
- **帧率**: 60 FPS (16.67ms 间隔)
- **噪声**: ±3 灰度单位的随机噪声
- **波峰**: 每 100 帧出现一次波峰信号
- **稳定性**: 长期运行稳定性

#### 5.2.3 性能要求
- **CPU 使用**: < 25% 单核使用率
- **内存使用**: < 300MB 峰值内存
- **延迟**: < 16ms 每帧处理时间
- **线程安全**: 无竞态条件

### 5.3 波峰检测算法

#### 5.3.1 5帧插值算法
```python
def detect_peak(value):
    """5帧插值波峰检测算法"""
    if len(data_store.values) < 60:
        return None

    # 计算基线 (最近60帧)
    baseline = sum(data_store.values[-60:]) / 60

    # 检测波峰阈值
    if value - baseline > 5.0:
        # 5帧插值计算
        before_avg = sum(data_store.values[-10:-5]) / 5
        after_avg = sum(data_store.values[-4:]) / 4
        frame_diff = after_avg - before_avg

        # 信号分类
        if frame_diff > 2.1:
            return 1  # 绿色波峰 (强 HEM 事件)
        else:
            return 0  # 红色波峰 (弱 HEM 事件)

    return None
```

#### 5.3.2 算法参数
- **基线窗口**: 60帧移动平均
- **波峰阈值**: 5.0 灰度单位
- **插值窗口**: 前5帧 + 后5帧
- **分类阈值**: 2.1 灰度差值
- **最小距离**: 10帧波峰间隔

#### 5.3.3 算法性能
- **计算复杂度**: O(1) 每帧
- **内存使用**: O(100) 固定缓冲区
- **延迟**: < 1ms 检测计算
- **准确性**: > 95% 检测率

### 5.4 数据缓冲管理

#### 5.4.1 循环缓冲区设计
- **大小**: 固定 100 帧缓冲区
- **管理**: FIFO (先进先出) 策略
- **内存**: 常内优化内存分配
- **清理**: 自动清理过期数据

#### 5.4.2 缓冲区策略
```python
def add_frame(self, value):
    with self.lock:
        # 添加新数据
        self.values.append(value)
        self.timestamps.append(time.time())
        self.frame_count += 1

        # 循环缓冲区管理
        if len(self.values) > self.max_buffer_size:
            self.values.pop(0)
            self.timestamps.pop(0)
```

#### 5.4.3 性能优化
- **内存预分配**: 固定大小数组
- **索引计算**: O(1) 访问时间
- **无拷贝操作**: 原地数据处理
- **缓存友好**: 连续内存布局

## 6. 多线程处理需求

### 6.1 线程架构
```
主线程: FastAPI 服务器
    ↓
数据线程: 60 FPS 数据生成和处理
    ↓
Socket 线程: 传统 TCP Socket 服务
    ↓
数据处理: 实时分析和检测
```

### 6.2 线程管理
- **主线程**: FastAPI HTTP 服务处理
- **数据线程**: 后台数据生成 (daemon)
- **Socket 线程**: TCP 连接处理 (daemon)
- **线程安全**: 锁保护的共享数据访问

### 6.3 同步机制
```python
# 线程锁保护所有共享数据访问
with self.lock:
    # 读取操作
    recent_data = self.values[-count:]

    # 写入操作
    self.values.append(new_value)
```

### 6.4 并发安全
- **读写锁**: 细粒度锁定策略
- **死锁避免**: 锁定顺序一致性
- **原子操作**: 关键操作的原子性
- **异常安全**: 异常情况的资源清理

## 7. 性能需求

### 7.1 响应性能
- **API 响应**: < 100ms (所有端点)
- **数据处理**: < 16ms 每帧
- **实时延迟**: < 50ms 端到端延迟
- **并发处理**: 100+ 并发请求

### 7.2 吞吐量需求
- **数据生成**: 60 FPS 持续处理
- **API 调用**: 20 FPS 实时数据查询
- **连接支持**: 10+ 并发客户端
- **数据处理**: 100+ 帧/秒分析能力

### 7.3 资源使用
- **内存使用**: < 500MB 峰值内存
- **CPU 使用**: < 50% 平均 CPU 占用
- **磁盘 I/O**: 最小化磁盘操作
- **网络带宽**: < 1MB/秒 总带宽

### 7.4 可扩展性
- **水平扩展**: 支持负载均衡部署
- **垂直扩展**: 支持多核 CPU 利用
- **缓存策略**: 内存缓存优化
- **异步处理**: 非阻塞 I/O 操作

## 8. 安全需求

### 8.1 认证和授权
- **密码保护**: 固定密码 31415
- **输入验证**: 所有输入参数验证
- **SQL 注入防护**: 参数化查询
- **XSS 防护**: 输出内容转义

### 8.2 API 安全
- **CORS 配置**: 开发环境全开放，生产环境限制
- **速率限制**: API 调用频率限制
- **IP 白名单**: 可选的 IP 访问控制
- **请求大小**: 请求大小限制

### 8.3 数据安全
- **敏感数据**: 不存储敏感信息
- **数据加密**: 传输层加密
- **访问日志**: 完整的访问日志
- **错误处理**: 安全的错误信息

## 9. 错误处理需求

### 9.1 HTTP 错误处理
- **400 Bad Request**: 无效请求参数
- **401 Unauthorized**: 认证失败
- **404 Not Found**: 资源不存在
- **500 Internal Error**: 服务器内部错误

### 9.2 业务错误处理
```python
try:
    # 业务逻辑处理
    result = process_data(data)
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    raise HTTPException(status_code=500, detail="Internal server error")
```

### 9.3 错误响应格式
```json
{
    "type": "error",
    "timestamp": "2025-01-15T10:30:25.123456",
    "error_code": "INVALID_PARAMETER",
    "error_message": "Parameter validation failed",
    "details": {
        "parameter": "count",
        "value": "invalid",
        "constraint": "must be positive integer"
    }
}
```

### 9.4 异常恢复
- **自动重试**: 网络错误自动重试
- **降级处理**: 功能降级策略
- **资源清理**: 异常情况的资源清理
- **日志记录**: 完整的异常日志

## 10. 监控需求

### 10.1 系统监控
- **健康检查**: `/health` 端点监控
- **性能指标**: 响应时间、吞吐量监控
- **资源使用**: CPU、内存、磁盘监控
- **错误率**: API 错误率监控

### 10.2 业务监控
- **数据处理**: 60 FPS 数据生成监控
- **检测效果**: 波峰检测准确率监控
- **用户活动**: API 调用频率监控
- **系统状态**: 运行状态实时监控

### 10.3 日志管理
- **访问日志**: 所有 API 访问记录
- **错误日志**: 详细的错误信息和堆栈
- **性能日志**: 性能指标记录
- **审计日志**: 安全相关操作记录

## 11. 部署需求

### 11.1 环境要求
- **Python**: 3.8+ (推荐 3.10+)
- **内存**: 最小 1GB，推荐 2GB+
- **CPU**: 多核处理器推荐
- **存储**: 100MB+ 可用空间

### 11.2 依赖管理
```python
# requirements.txt
fastapi==0.115.0
uvicorn==0.30.6
numpy>=1.21.0
python-multipart==0.0.9
starlette==0.38.4
```

### 11.3 配置管理
```python
# config.py
APP_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "api_port": 8421,
        "socket_port": 30415,
        "max_clients": 10
    },
    "data": {
        "fps": 60,
        "buffer_size": 100,
        "max_frame_count": 10000
    },
    "security": {
        "password": "31415",
        "enable_cors": True,
        "allowed_origins": ["*"]
    }
}
```

### 11.4 启动脚本
```python
# run.py - 主启动脚本
def main():
    # 启动 FastAPI 服务器
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()

    # 启动数据处理系统
    fem_system.start()
```

## 12. 测试需求

### 12.1 单元测试
- **算法测试**: 波峰检测算法准确性测试
- **数据结构测试**: 数据存储功能测试
- **API 端点测试**: 各个端点功能测试
- **错误处理测试**: 异常情况处理测试

### 12.2 集成测试
- **API 集成**: 前后端完整流程测试
- **性能测试**: 高并发和长时间运行测试
- **兼容性测试**: 不同浏览器兼容性测试
- **压力测试**: 极限负载情况测试

### 12.3 测试工具
- **pytest**: 单元测试框架
- **requests**: HTTP 请求测试
- **locust**: 负载测试工具
- **coverage**: 代码覆盖率测试

---

此文档定义了 NewFEM 后端的完整技术需求，为系统开发、部署和维护提供详细的技术规范和实现指导。