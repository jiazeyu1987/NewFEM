#!/usr/bin/env python3
"""
测试自动配置加载功能
"""

import requests
import json

def test_auto_config_loading():
    """测试自动配置加载功能"""
    print("测试自动配置加载功能...")

    base_url = "http://localhost:8422"
    password = "31415"

    try:
        # 1. 测试健康检查
        print("1. 测试服务器健康检查...")
        health_response = requests.get(f"{base_url}/health", timeout=5)
        if health_response.status_code == 200:
            print("   [OK] 服务器健康检查通过")
        else:
            print(f"   [FAIL] 健康检查失败: {health_response.status_code}")
            return False

        # 2. 测试配置加载
        print("2. 测试配置API...")
        config_response = requests.get(
            f"{base_url}/config",
            params={"password": password},
            timeout=5
        )

        if config_response.status_code == 200:
            config_data = config_response.json()
            if "config" in config_data:
                config = config_data["config"]
                print("   [OK] 配置获取成功")

                # 3. 验证关键配置字段
                print("3. 验证关键配置字段...")

                # ROI配置验证
                if "roi_capture" in config and "default_config" in config["roi_capture"]:
                    roi_config = config["roi_capture"]["default_config"]
                    x1, y1 = roi_config.get("x1", 0), roi_config.get("y1", 0)
                    x2, y2 = roi_config.get("x2", 200), roi_config.get("y2", 150)
                    print(f"   [OK] ROI配置: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
                else:
                    print("   [FAIL] ROI配置缺失")
                    return False

                # 波峰检测配置验证
                if "peak_detection" in config:
                    peak_config = config["peak_detection"]
                    threshold = peak_config.get("threshold", 105.0)
                    margin = peak_config.get("margin_frames", 5)
                    print(f"   [OK] 波峰检测配置: threshold={threshold}, margin={margin}")
                else:
                    print("   [FAIL] 波峰检测配置缺失")
                    return False

                print("4. 模拟自动配置应用...")
                # 模拟客户端应用配置
                simulated_roi_data = {
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "password": password
                }
                print(f"   [INFO] 将应用的ROI配置: {simulated_roi_data}")

                print("自动配置加载功能验证完成！")
                return True

            else:
                print("   [FAIL] 配置响应格式错误")
                return False
        else:
            print(f"   [FAIL] 获取配置失败: HTTP {config_response.status_code}")
            return False

    except Exception as e:
        print(f"   [FAIL] 测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_auto_config_loading()
    if success:
        print("\n✅ 自动配置加载功能测试通过")
        exit(0)
    else:
        print("\n❌ 自动配置加载功能测试失败")
        exit(1)