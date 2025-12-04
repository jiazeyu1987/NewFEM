#!/usr/bin/env python3
"""
测试阈值和边界扩展参数的实时同步功能
"""

import sys
import os
import requests
import json
import time

# 添加backend路径到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backends'))

def test_parameter_sync():
    """测试参数同步功能"""
    base_url = "http://localhost:8421"

    print("=" * 60)
    print("测试阈值和边界扩展参数实时同步")
    print("=" * 60)

    # 1. 首先获取当前配置
    try:
        response = requests.get(f"{base_url}/peak-detection/config")
        if response.status_code == 200:
            current_config = response.json()
            print(f"当前配置: {current_config}")
        else:
            print(f"获取配置失败: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"连接服务器失败: {e}")
        return False

    # 2. 测试不同的参数值
    test_cases = [
        {"threshold": 120.0, "margin_frames": 8},
        {"threshold": 95.0, "margin_frames": 3},
        {"threshold": 150.0, "margin_frames": 10},
        {"threshold": 80.0, "margin_frames": 2}
    ]

    for i, test_params in enumerate(test_cases, 1):
        print(f"\n--- 测试用例 {i}: 阈值={test_params['threshold']}, 边界={test_params['margin_frames']} ---")

        # 3. 更新配置
        try:
            update_data = {
                "threshold": test_params["threshold"],
                "margin_frames": test_params["margin_frames"],
                "password": "31415"
            }

            response = requests.post(f"{base_url}/peak-detection/config", data=update_data)
            if response.status_code == 200:
                print(f"[SUCCESS] 配置更新成功")
            else:
                print(f"[FAIL] 配置更新失败: {response.status_code}")
                continue
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] 更新配置请求失败: {e}")
            continue

        # 等待配置生效
        time.sleep(0.5)

        # 4. 测试API端点是否使用新参数
        try:
            # 测试 waveform-with-peaks 端点（不传递查询参数，应该使用配置值）
            response = requests.get(f"{base_url}/data/waveform-with-peaks?count=50")
            if response.status_code == 200:
                result = response.json()
                if "peak_detection_params" in result:
                    used_params = result["peak_detection_params"]
                    print(f"[SUCCESS] waveform-with-peaks 使用参数: 阈值={used_params.get('threshold')}, 边界={used_params.get('margin_frames')}")

                    # 验证参数是否正确
                    if (used_params.get('threshold') == test_params["threshold"] and
                        used_params.get('margin_frames') == test_params["margin_frames"]):
                        print(f"[SUCCESS] 参数同步正确")
                    else:
                        print(f"[FAIL] 参数同步失败")
                else:
                    print("[WARN] 响应中未找到参数信息")
            else:
                print(f"[FAIL] waveform-with-peaks 请求失败: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] waveform-with-peaks 请求异常: {e}")

        try:
            # 测试 roi-window-capture-with-peaks 端点
            response = requests.get(f"{base_url}/data/roi-window-capture-with-peaks?count=50")
            if response.status_code == 200:
                result = response.json()
                if "peak_detection_params" in result:
                    used_params = result["peak_detection_params"]
                    print(f"[SUCCESS] roi-window-capture 使用参数: 阈值={used_params.get('threshold')}, 边界={used_params.get('margin_frames')}")

                    # 验证参数是否正确
                    if (used_params.get('threshold') == test_params["threshold"] and
                        used_params.get('margin_frames') == test_params["margin_frames"]):
                        print(f"[SUCCESS] 参数同步正确")
                    else:
                        print(f"[FAIL] 参数同步失败")
                else:
                    print("[WARN] 响应中未找到参数信息")
            else:
                print(f"[FAIL] roi-window-capture 请求失败: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] roi-window-capture 请求异常: {e}")

        # 短暂等待下一个测试用例
        time.sleep(0.5)

    # 5. 恢复原始配置
    try:
        restore_data = {
            "threshold": current_config.get("threshold", 105.0),
            "margin_frames": current_config.get("margin_frames", 5),
            "password": "31415"
        }
        requests.post(f"{base_url}/peak-detection/config", data=restore_data)
        print(f"\n[SUCCESS] 已恢复原始配置")
    except:
        print(f"\n[WARN] 恢复原始配置失败")

    print("\n" + "=" * 60)
    print("参数同步测试完成")
    print("=" * 60)
    return True

def main():
    """主函数"""
    success = test_parameter_sync()
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())