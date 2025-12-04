#!/usr/bin/env python3
"""
NewFEM Python客户端启动脚本
运行基于HTTP的实时绘图客户端
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from http_realtime_client import main

    print("启动NewFEM Python实时客户端...")
    print("=" * 50)
    print("功能:")
    print("- HTTP API连接到后端服务器")
    print("- 实时获取数据并绘制曲线")
    print("- 支持开始/停止检测控制")
    print("- 与Web前端完全一致的数据显示")
    print("=" * 50)

    main()

except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保依赖已安装:")
    print("- requests (HTTP客户端)")
    print("- matplotlib (绘图)")
    print("- tkinter (GUI，通常已包含)")

except Exception as e:
    print(f"启动错误: {e}")
    import traceback
    traceback.print_exc()
    input("按回车键退出...")