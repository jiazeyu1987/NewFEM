# NewFEM HTTP客户端使用指南

## 问题已解决！✅

**原始问题**: "看不到绘制的曲线，坐标系都看不到了"
**解决方案**: 已修复所有matplotlib canvas集成问题

## 修复内容

### 1. 数据提取问题修复 ✅
- **问题**: 代码从错误的JSON字段提取信号值
- **修复**: 从`series[0].value`中正确提取信号值
- **影响**: 现在可以正确接收和显示实时数据

### 2. GUI Canvas显示问题修复 ✅
- **问题**: matplotlib canvas没有正确嵌入到Tkinter GUI中
- **修复**:
  - 添加了正确的logger导入
  - 修复了matplotlib字体配置
  - 确保canvas正确创建和嵌入
- **影响**: 现在可以看到完整的坐标系和图表

### 3. 字体问题修复 ✅
- **问题**: 中文字符导致matplotlib警告和显示问题
- **修复**: 使用英文字体和标签
- **影响**: 消除了字体警告，提高了显示稳定性

## 使用方法

### 方法1: 完整GUI客户端 (推荐)
```bash
# 1. 启动后端服务器
cd backends
python run.py

# 2. 在新终端中启动HTTP客户端GUI
cd python_client
python http_realtime_client.py
```

**功能特性**:
- ✅ 完整的Tkinter GUI界面
- ✅ 实时matplotlib图表显示
- ✅ HTTP连接管理
- ✅ ROI自动配置
- ✅ 检测控制面板
- ✅ 实时数据统计
- ✅ 日志显示
- ✅ 截图保存功能

### 方法2: 简化演示版本
```bash
cd NewFEM
python demo_http_client.py
```

### 方法3: Canvas测试工具
```bash
cd NewFEM
python test_http_canvas.py
```

## 用户界面说明

### GUI组件
1. **连接配置面板**: 设置服务器URL和密码
2. **控制面板**: 开始/停止检测、清除数据、保存截图
3. **实时信息面板**: 显示数据点数、FPS、检测状态等
4. **日志面板**: 显示操作日志和错误信息
5. **实时图表区域**: 显示信号曲线和波峰信号

### 图表显示
- **主图表**: 蓝色信号曲线，红色虚线基线，圆点标记波峰
- **底部图表**: 波峰信号状态显示
- **坐标轴**: 自动缩放，显示最近10秒数据
- **网格**: 半透明网格线便于读数

## 性能特性

- **数据刷新率**: 20 FPS (每50ms更新一次)
- **网络连接**: HTTP Keep-Alive连接复用
- **内存管理**: 最多1000个数据点，自动清理旧数据
- **错误恢复**: 自动重连和错误处理机制

## 故障排除

### 如果仍然看不到图表:
1. **检查matplotlib安装**: `pip install matplotlib`
2. **检查GUI环境**: 确保支持Tkinter
3. **检查防火墙**: 确保8421端口可访问
4. **检查后端状态**: 确保后端服务器正在运行

### 测试步骤:
1. 运行 `python test_http_canvas.py` 验证canvas功能
2. 运行 `python test_gui_client.py` 进行全面测试
3. 检查生成的测试图片文件

## 技术架构

```
Python GUI Client (Tkinter + matplotlib)
    ↓ HTTP Requests (20 FPS)
FastAPI Backend (Port 8421)
    ↓
DataProcessor (60 FPS Signal Generation)
```

## 文件结构

```
NewFEM/
├── python_client/
│   ├── http_realtime_client.py    # 主GUI客户端
│   ├── realtime_plotter.py        # matplotlib绘图组件
│   └── run_realtime_client.py     # 启动脚本
├── demo_http_client.py            # 简化演示
├── test_http_canvas.py            # Canvas测试工具
└── HTTP_CLIENT_USAGE_GUIDE.md     # 本使用指南
```

## 成功指标

当以下功能正常工作时，说明安装成功：
- ✅ GUI窗口能够正常打开
- ✅ 可以看到坐标系和网格线
- ✅ 连接服务器后显示"Connected"状态
- ✅ 点击"开始检测"后看到实时数据曲线
- ✅ 数据点数持续增加
- ✅ FPS显示正常的更新频率

## 总结

HTTP客户端现在完全正常工作！用户可以看到：
- 完整的坐标轴和标签
- 实时更新的信号曲线
- 网格线和图例
- 数据统计信息
- 控制面板功能

所有之前的问题都已解决，matplotlib canvas已正确集成到Tkinter GUI中。