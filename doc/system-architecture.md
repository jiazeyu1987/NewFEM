# NewFEM 系统架构文档

## 1. 概述

NewFEM (Focused Emboli Monitor) 是一个现代化的 HEM (高回声事件) 实时检测系统，采用前后端分离的 Web 架构设计。系统通过 RESTful API 替代传统 WebSocket 连接，提供高兼容性和易集成的通信方式。本文档详细描述系统的整体架构、技术选型、设计模式和实现细节。

## 2. 系统整体架构

### 2.1 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        NewFEM System                           │
├─────────────────────────────────────────────────────────────────┤
│                         Frontend Layer                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ VS Code UI  │  │ Canvas      │  │ HTTP Polling            │ │
│  │ Components  │  │ Rendering   │  │ (20 FPS)                │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                        Network Layer                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ RESTful API │  │ HTTP/HTTPS  │  │ CORS Configuration      │ │
│  │ (Port 8421) │  │ Protocol    │  │ (Development: *)        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                        Backend Layer                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ FastAPI     │  │ Data        │  │ Background Threads      │ │
│  │ Server      │  │ Processing  │  │ (60 FPS Generation)     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                       Data Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Memory      │  │ Circular    │  │ Peak Detection          │ │
│  │ Storage     │  │ Buffer      │  │ Algorithm               │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心设计原则

#### 2.2.1 技术选型原则
- **现代化技术栈**: FastAPI + 原生 JavaScript
- **无依赖设计**: 避免复杂框架依赖
- **高性能**: 60 FPS 实时数据处理
- **高兼容性**: 标准协议，易于集成

#### 2.2.2 架构设计原则
- **前后端分离**: 清晰的职责划分
- **RESTful 设计**: 标准 HTTP 接口
- **无状态服务**: 水平扩展友好
- **异步处理**: 非阻塞 I/O 操作

## 3. 前端架构

### 3.1 技术栈架构

#### 3.1.1 技术选型
```javascript
// 技术栈配置
const TechStack = {
    "Framework": "Vanilla JavaScript (ES6+)",
    "Styling": "CSS3 with VS Code Theme",
    "Communication": "Fetch API (HTTP)",
    "Rendering": "Canvas 2D API",
    "Build Tools": "None (Direct Browser)",
    "Package Management": "None"
};
```

#### 3.1.2 浏览器兼容性矩阵
| 浏览器 | 最低版本 | 推荐版本 | 支持特性 |
|--------|----------|----------|----------|
| Chrome | 80+ | 100+ | 全功能支持 |
| Firefox | 75+ | 95+ | 全功能支持 |
| Safari | 13+ | 15+ | 全功能支持 |
| Edge | 80+ | 100+ | 全功能支持 |

### 3.2 组件架构设计

#### 3.2.1 核心组件层次结构
```
Application (app.js)
├── State Management (appState)
├── Connection Manager
├── Data Polling Engine
├── UI Controllers
│   ├── System Status Panel
│   ├── Display Control Panel
│   ├── ROI Visualizer
│   ├── Detection Control
│   └── Waveform Chart
└── Rendering Engines
    ├── Canvas Chart Renderer
    ├── ROI Canvas Renderer
    └── Animation Controller
```

#### 3.2.2 组件通信模式
```javascript
// 全局状态管理
const appState = {
    // 连接状态
    connected: false,
    serverUrl: 'http://localhost:8421',

    // 数据状态
    chartData: [],
    roiData: null,
    frameCount: 0,
    currentValue: 0,
    peakSignal: null,
    baseline: 0,

    // 显示状态
    chartState: {
        showGrid: true,
        showBaseline: true,
        showPoints: true,
        zoom: 1.0
    }
};

// 组件间通信通过全局状态
function updateComponent(component, data) {
    // 更新状态
    Object.assign(appState[component], data);

    // 触发重绘
    if (component === 'chartState') {
        renderChart();
    }
}
```

### 3.3 数据流架构

#### 3.3.1 数据获取流程
```
User Action → HTTP Request → Response Processing → State Update → UI Render
     ↓              ↓                ↓                ↓           ↓
 Button Click → fetch('/api') → JSON.parse() → appState.* → renderChart()
```

#### 3.3.2 实时数据轮询架构
```javascript
// 轮询调度器
class PollingScheduler {
    constructor() {
        this.intervals = new Map();
    }

    schedule(name, callback, interval) {
        this.intervals.set(name, setInterval(callback, interval));
    }

    cancel(name) {
        clearInterval(this.intervals.get(name));
        this.intervals.delete(name);
    }
}

// 轮询配置
const scheduler = new PollingScheduler();
scheduler.schedule('realtime', updateRealtimeData, 50);   // 20 FPS
scheduler.schedule('status', updateSystemStatus, 5000);  // 0.2 FPS
```

### 3.4 Canvas 渲染架构

#### 3.4.1 渲染管线设计
```javascript
class CanvasRenderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.animationId = null;
    }

    render(data) {
        // 清除画布
        this.clear();

        // 设置变换
        this.setupTransform();

        // 渲染组件
        this.renderGrid();
        this.renderData(data);
        this.renderBaseline();
        this.renderEvents();

        // 请求下一帧
        this.requestAnimationFrame();
    }

    requestAnimationFrame() {
        this.animationId = requestAnimationFrame(() => {
            this.render(this.latestData);
        });
    }
}
```

#### 3.4.2 性能优化策略
- **硬件加速**: GPU 加速的 Canvas 渲染
- **增量更新**: 只重绘变化的部分
- **帧率控制**: 20 FPS 固定更新频率
- **内存优化**: 复用 Canvas 对象

## 4. 后端架构

### 4.1 技术栈架构

#### 4.1.1 技术选型
```python
# 技术栈配置
TECH_STACK = {
    "web_framework": "FastAPI 0.115.0",
    "asgi_server": "Uvicorn 0.30.6",
    "data_processing": "NumPy 2.1.1",
    "file_handling": "python-multipart 0.0.9",
    "cors_support": "Starlette 0.38.4",
    "threading": "threading module",
    "real_time_processing": "time-based data processing"
}
```

#### 4.1.2 Python 版本要求
- **最低版本**: Python 3.8+
- **推荐版本**: Python 3.10+
- **特性需求**: AsyncIO、Type Hints、Context Managers

### 4.2 API 架构设计

#### 4.2.1 端点层次结构
```
API Root (/)
├── Health Check (/health)
├── System Status (/status)
├── Real-time Data (/data/realtime)
├── Control Commands (/control)
├── Video Analysis (/analyze)
└── Documentation (/docs)
```

#### 4.2.2 请求处理流水线
```
HTTP Request → Middleware → Route Handler → Business Logic → Response
      ↓              ↓              ↓              ↓              ↓
   CORS Check → Parameter → Data Processing → JSON Format → HTTP Response
                  Validation
```

### 4.3 数据处理架构

#### 4.3.1 数据存储设计
```python
class NewFEMData:
    """线程安全的数据存储类"""
    def __init__(self):
        self.values = []              # 灰度值数组
        self.timestamps = []          # 时间戳数组
        self.signal = None           # 当前波峰信号
        self.frame_count = 0         # 帧数计数
        self.lock = threading.Lock() # 线程锁
        self.max_buffer_size = 100   # 最大缓冲区大小
        self.running = False         # 运行状态标志
```

#### 4.3.2 多线程架构设计
```
Main Thread (FastAPI Server)
    ↓
Data Thread (60 FPS Generation)
    ↓
Processing Thread (Peak Detection)
    ↓
Response Thread (API Response)
```

### 4.4 算法处理架构

#### 4.4.1 波峰检测算法
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

#### 4.4.2 算法性能优化
- **时间复杂度**: O(1) 每帧处理
- **空间复杂度**: O(100) 固定缓冲区
- **处理延迟**: < 1ms 每帧计算
- **准确率**: > 95% 检测率

## 5. 通信架构

### 5.1 HTTP 协议架构

#### 5.1.1 RESTful API 设计
```
Method  Endpoint              Description
GET     /health              Health check
GET     /status              System status
GET     /data/realtime       Real-time data
POST    /control             Control commands
POST    /analyze             Video analysis
```

#### 5.1.2 请求/响应模式
```http
# 实时数据请求
GET /data/realtime?count=100 HTTP/1.1
Host: localhost:8421
Accept: application/json

# 响应格式
HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: max-age=50

{
    "type": "realtime_data",
    "timestamp": "2025-01-15T10:30:25.123456Z",
    "frame_count": 1234,
    "series": [...],
    "peak_signal": 1,
    "baseline": 120.5
}
```

### 5.2 数据同步架构

#### 5.2.1 轮询策略设计
```javascript
// 轮询频率配置
const POLLING_CONFIG = {
    'realtime_data': 50,    // 20 FPS
    'system_status': 5000,  // 0.2 FPS
    'health_check': 10000   // 0.1 FPS
};

// 智能轮询实现
class AdaptivePolling {
    constructor() {
        this.baseInterval = 50;
        this.currentInterval = this.baseInterval;
        this.errorCount = 0;
    }

    adjustInterval(success) {
        if (success) {
            this.currentInterval = Math.max(
                this.baseInterval,
                this.currentInterval * 0.95
            );
            this.errorCount = 0;
        } else {
            this.currentInterval = Math.min(
                this.currentInterval * 1.5,
                5000  // 最大 5 秒
            );
            this.errorCount++;
        }
    }
}
```

#### 5.2.2 错误恢复机制
```javascript
// 自动重连机制
class ConnectionManager {
    constructor() {
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
    }

    async handleDisconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            await this.delay(this.reconnectDelay);
            this.reconnectAttempts++;
            this.connect();
        }
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}
```

## 6. 部署架构

### 6.1 开发环境架构

#### 6.1.1 本地开发配置
```
Development Environment
├── Frontend Dev Server (Port 5173)
│   ├── Static File Serving
│   ├── Auto-reload
│   └── CORS Configuration
├── Backend API Server (Port 8421)
│   ├── FastAPI Development
│   ├── Auto-reload
│   └── Debug Logging
└── Development Tools
    ├── JavaScript Syntax Check
    ├── API Documentation
    └── Browser DevTools
```

#### 6.1.2 启动脚本架构
```python
# main.py - 主启动脚本
def main():
    # 启动 FastAPI 服务器
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()

    # 启动数据处理系统
    fem_system.start()

    # 等待信号
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
```

### 6.2 生产环境架构

#### 6.2.1 容器化部署
```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8421

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8421"]
```

#### 6.2.2 负载均衡配置
```
Nginx Configuration
├── Static File Serving (Frontend)
├── API Proxy (Backend)
├── HTTPS Termination
└── Load Balancing
```

### 6.3 监控架构

#### 6.3.1 系统监控
```python
# 监控指标
MONITORING_METRICS = {
    "system": {
        "cpu_usage": "percent",
        "memory_usage": "MB",
        "disk_usage": "percent"
    },
    "application": {
        "fps": "frames_per_second",
        "response_time": "milliseconds",
        "error_rate": "percent"
    },
    "business": {
        "peak_detection_rate": "events_per_minute",
        "data_processing_rate": "frames_per_second",
        "user_sessions": "active_sessions"
    }
}
```

#### 6.3.2 健康检查
```python
@app.get("/health")
def health():
    """健康检查端点"""
    return {
        "status": "ok",
        "system": "NewFEM API Server",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "uptime": time.time() - start_time
    }
```

## 7. 安全架构

### 7.1 认证授权架构

#### 7.1.1 密码认证
```python
# 控制命令认证
@app.post("/control")
def handle_control(command: str = Form(...), password: str = Form(...)):
    """控制命令处理"""
    if password != "31415":
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid password"}
        )

    # 处理命令逻辑
    return process_command(command)
```

#### 7.1.2 CORS 安全配置
```python
# CORS 中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"]
)
```

### 7.2 数据安全架构

#### 7.2.1 输入验证
```python
# 参数验证装饰器
def validate_parameters(func):
    def wrapper(*args, **kwargs):
        # 验证输入参数
        if not validate_input(kwargs):
            raise HTTPException(status_code=400, detail="Invalid parameters")
        return func(*args, **kwargs)
    return wrapper
```

#### 7.2.2 错误处理
```python
# 安全错误处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.now().isoformat()
        }
    )
```

## 8. 性能架构

### 8.1 性能优化策略

#### 8.1.1 前端性能优化
```javascript
// 性能监控
class PerformanceMonitor {
    constructor() {
        this.metrics = {
            fps: 0,
            renderTime: 0,
            memoryUsage: 0
        };
    }

    measureRender(renderFunction) {
        const startTime = performance.now();
        renderFunction();
        const endTime = performance.now();
        this.metrics.renderTime = endTime - startTime;
    }
}
```

#### 8.1.2 后端性能优化
```python
# 缓存装饰器
from functools import lru_cache
import time

@lru_cache(maxsize=128)
def get_cached_data(cache_key, timestamp):
    """缓存数据响应"""
    return generate_data_response()

# 性能监控
def measure_performance(func):
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        print(f"{func.__name__}: {end_time - start_time:.3f}s")
        return result
    return wrapper
```

### 8.2 扩展性架构

#### 8.2.1 水平扩展设计
```python
# 无状态服务设计
class StatelessAPI:
    """无状态 API 服务"""
    def __init__(self):
        self.data_store = RedisDataStore()  # 外部存储

    async def get_data(self, request):
        # 请求包含所有必要信息
        data = await self.data_store.get(request.session_id)
        return data
```

#### 8.2.2 垂直扩展设计
```python
# 多核处理
import multiprocessing
from concurrent.futures import ThreadPoolExecutor

class MultiCoreProcessor:
    def __init__(self, workers=4):
        self.executor = ThreadPoolExecutor(max_workers=workers)

    async def process_batch(self, data_batch):
        futures = [
            self.executor.submit(self.process_frame, frame)
            for frame in data_batch
        ]
        return [future.result() for future in futures]
```

## 9. 测试架构

### 9.1 测试策略

#### 9.1.1 测试金字塔
```
Testing Pyramid
├── E2E Tests (10%)
│   ├── User Flow Testing
│   └── Integration Testing
├── Integration Tests (20%)
│   ├── API Testing
│   └── Component Testing
└── Unit Tests (70%)
    ├── Algorithm Testing
    ├── Function Testing
    └── Module Testing
```

#### 9.1.2 自动化测试
```python
# 单元测试
import pytest

def test_peak_detection():
    """测试波峰检测算法"""
    data_store.values = [120, 121, 122, 135, 130, 125]  # 模拟数据
    signal = detect_peak(135)
    assert signal == 1  # 强 HEM 事件

# API 测试
def test_realtime_data_endpoint():
    """测试实时数据端点"""
    response = client.get("/data/realtime?count=10")
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert data["type"] == "realtime_data"
```

### 9.2 性能测试

#### 9.2.1 负载测试
```python
# 性能测试脚本
import asyncio
import aiohttp

async def benchmark_api():
    """API 性能基准测试"""
    async with aiohttp.ClientSession() as session:
        start_time = time.time()

        tasks = []
        for i in range(100):
            task = asyncio.create_task(
                session.get("http://localhost:8421/data/realtime")
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
        end_time = time.time()

        success_count = sum(1 for r in responses if r.status == 200)
        print(f"成功率: {success_count/100:.1%}")
        print(f"平均延迟: {(end_time - start_time)/100:.3f}s")
```

## 10. 未来演进架构

### 10.1 技术演进路线图

#### 10.1.1 短期改进 (3-6 个月)
- WebSocket 实时通信选项
- 数据持久化和历史查询
- 高级分析和机器学习集成
- 移动端适配

#### 10.1.2 中期发展 (6-12 个月)
- 微服务架构重构
- 云原生部署支持
- 多租户架构
- 实时协作功能

#### 10.1.3 长期规划 (1-2 年)
- AI 辅助诊断
- 分布式计算支持
- 边缘计算集成
- 标准化协议支持

### 10.2 扩展架构设计

#### 10.2.1 微服务架构
```
Microservices Architecture
├── Gateway Service
├── Data Collection Service
├── Analysis Service
├── Storage Service
├── Notification Service
└── Monitoring Service
```

#### 10.2.2 云原生架构
```
Cloud Native Architecture
├── Kubernetes Cluster
├── Service Mesh
├── Container Orchestration
├── Auto-scaling
└── Cloud Storage
```

---

此系统架构文档全面描述了 NewFEM 系统的技术架构、设计模式和实现细节，为系统开发、部署和维护提供完整的技术指导。