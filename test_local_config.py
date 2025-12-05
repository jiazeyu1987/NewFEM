#!/usr/bin/env python3
"""
测试本地配置加载功能
验证HTTP客户端是否能正确加载本地配置文件并应用到UI
"""

import sys
import os
import time
import threading
from local_config_loader import LocalConfigLoader

def test_local_config_loader():
    """测试本地配置加载器"""
    print("🧪 测试本地配置加载器...")

    try:
        # 创建配置加载器
        loader = LocalConfigLoader()

        # 加载配置
        success, message, config_data = loader.load_config()

        if success:
            print(f"✅ 配置加载成功: {message}")

            # 提取关键配置
            roi_config = loader.get_roi_config()
            peak_config = loader.get_peak_detection_config()

            print(f"📋 ROI配置: {roi_config}")
            print(f"📋 波峰检测配置: {peak_config}")

            # 验证配置完整性
            expected_roi_keys = ['x1', 'y1', 'x2', 'y2', 'frame_rate']
            expected_peak_keys = ['threshold', 'margin_frames', 'difference_threshold']

            roi_complete = all(key in roi_config for key in expected_roi_keys)
            peak_complete = all(key in peak_config for key in expected_peak_keys)

            if roi_complete and peak_complete:
                print("✅ 配置完整性验证通过")
                return True
            else:
                print(f"❌ 配置完整性验证失败")
                print(f"   ROI完整: {roi_complete}, 缺少: {[k for k in expected_roi_keys if k not in roi_config]}")
                print(f"   波峰检测完整: {peak_complete}, 缺少: {[k for k in expected_peak_keys if k not in peak_config]}")
                return False

        else:
            print(f"❌ 配置加载失败: {message}")
            return False

    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")
        return False

def test_config_field_mapping():
    """测试配置字段映射"""
    print("\n🧪 测试配置字段映射...")

    try:
        # 模拟客户端配置应用逻辑
        loader = LocalConfigLoader()
        success, message, config_data = loader.load_config()

        if not success:
            print(f"❌ 无法加载配置进行映射测试: {message}")
            return False

        # 模拟UI字段应用
        ui_fields = {}

        # ROI配置映射
        if "roi_capture" in config_data:
            roi_config = config_data["roi_capture"]
            if "default_config" in roi_config:
                default_config = roi_config["default_config"]
                ui_fields.update({
                    'roi_x1_var': str(default_config.get("x1", 0)),
                    'roi_y1_var': str(default_config.get("y1", 0)),
                    'roi_x2_var': str(default_config.get("x2", 200)),
                    'roi_y2_var': str(default_config.get("y2", 150))
                })

            if "frame_rate" in roi_config:
                ui_fields['roi_fps_var'] = str(roi_config["frame_rate"])

        # 波峰检测配置映射
        if "peak_detection" in config_data:
            peak_config = config_data["peak_detection"]
            ui_fields.update({
                'peak_threshold_var': str(peak_config.get("threshold", 105.0)),
                'peak_margin_var': str(peak_config.get("margin_frames", 5)),
                'peak_diff_var': str(peak_config.get("difference_threshold", 2.1))
            })

        print(f"✅ 映射的UI字段: {ui_fields}")

        # 验证必要字段
        required_fields = ['roi_x1_var', 'roi_y1_var', 'roi_x2_var', 'roi_y2_var',
                          'peak_threshold_var', 'peak_margin_var']
        missing_fields = [field for field in required_fields if field not in ui_fields]

        if not missing_fields:
            print("✅ 配置字段映射验证通过")
            return True
        else:
            print(f"❌ 配置字段映射验证失败，缺少字段: {missing_fields}")
            return False

    except Exception as e:
        print(f"❌ 映射测试异常: {str(e)}")
        return False

def test_client_integration():
    """测试客户端集成（简化版）"""
    print("\n🧪 测试客户端集成...")

    try:
        # 模拟导入客户端模块（不启动GUI）
        sys.path.append('python_client')

        # 测试导入是否成功
        try:
            from local_config_loader import LocalConfigLoader
            print("✅ 本地配置加载器导入成功")
        except ImportError as e:
            print(f"❌ 导入失败: {str(e)}")
            return False

        # 验证配置文件路径
        loader = LocalConfigLoader()
        config_path = loader.get_config_path()

        if os.path.exists(config_path):
            print(f"✅ 配置文件路径有效: {config_path}")
            return True
        else:
            print(f"❌ 配置文件路径无效: {config_path}")
            return False

    except Exception as e:
        print(f"❌ 集成测试异常: {str(e)}")
        return False

def simulate_client_startup():
    """模拟客户端启动流程"""
    print("\n🧪 模拟客户端启动流程...")

    try:
        print("1. 初始化本地配置加载器...")
        loader = LocalConfigLoader()

        print("2. 加载本地配置...")
        success, message, config_data = loader.load_config()

        if not success:
            print(f"   ❌ 配置加载失败: {message}")
            print("   → 客户端将使用默认配置启动")
            return False

        print(f"   ✅ 配置加载成功: {os.path.basename(loader.get_config_path())}")

        print("3. 应用配置到UI字段...")
        # 模拟UI更新
        if "roi_capture" in config_data:
            roi_config = config_data["roi_capture"].get("default_config", {})
            print(f"   ROI区域: ({roi_config.get('x1', 0)}, {roi_config.get('y1', 0)}) → ({roi_config.get('x2', 200)}, {roi_config.get('y2', 150)})")

        if "peak_detection" in config_data:
            peak_config = config_data["peak_detection"]
            print(f"   波峰阈值: {peak_config.get('threshold', 'N/A')}")
            print(f"   边界帧数: {peak_config.get('margin_frames', 'N/A')}")

        print("4. 配置应用完成，客户端可以启动")
        print("   ✅ 客户端启动流程模拟成功")
        return True

    except Exception as e:
        print(f"❌ 启动流程模拟异常: {str(e)}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始本地配置加载功能测试")
    print("=" * 50)

    test_results = []

    # 运行所有测试
    test_results.append(("本地配置加载器", test_local_config_loader()))
    test_results.append(("配置字段映射", test_config_field_mapping()))
    test_results.append(("客户端集成", test_client_integration()))
    test_results.append(("客户端启动流程", simulate_client_startup()))

    # 显示测试结果
    print("\n" + "=" * 50)
    print("📊 测试结果汇总:")

    passed = 0
    total = len(test_results)

    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1

    print(f"\n🎯 总体结果: {passed}/{total} 测试通过")

    if passed == total:
        print("🎉 所有测试通过！本地配置加载功能工作正常")
        return True
    else:
        print("⚠️ 部分测试失败，请检查相关功能")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)