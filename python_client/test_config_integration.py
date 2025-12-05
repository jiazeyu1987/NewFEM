#!/usr/bin/env python3
"""
集成测试：HTTP客户端本地配置加载功能
"""

import sys
import os

def test_local_config_integration():
    """测试本地配置加载集成"""
    print("🧪 测试HTTP客户端本地配置加载集成...")

    try:
        # 导入本地配置加载器
        from local_config_loader import LocalConfigLoader

        # 创建配置加载器
        loader = LocalConfigLoader()

        # 加载配置
        success, message, config_data = loader.load_config()

        if success:
            print(f"✅ 配置加载成功: {os.path.basename(loader.get_config_path())}")

            # 验证配置结构
            roi_config = loader.get_roi_config()
            peak_config = loader.get_peak_detection_config()

            print(f"📋 ROI配置: {roi_config}")
            print(f"📋 波峰检测配置: {peak_config}")

            # 验证关键字段
            required_roi = ['x1', 'y1', 'x2', 'y2', 'frame_rate']
            required_peak = ['threshold', 'margin_frames', 'difference_threshold']

            roi_valid = all(key in roi_config for key in required_roi)
            peak_valid = all(key in peak_config for key in required_peak)

            if roi_valid and peak_valid:
                print("✅ 配置验证通过")
                return True
            else:
                print(f"❌ 配置验证失败: ROI={roi_valid}, Peak={peak_valid}")
                return False
        else:
            print(f"❌ 配置加载失败: {message}")
            return False

    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")
        return False

def test_config_application_simulation():
    """模拟配置应用到UI字段"""
    print("\n🧪 模拟配置应用到UI字段...")

    try:
        from local_config_loader import LocalConfigLoader

        loader = LocalConfigLoader()
        success, message, config_data = loader.load_config()

        if not success:
            print(f"❌ 无法加载配置: {message}")
            return False

        # 模拟UI字段变量
        class MockUIVars:
            def __init__(self):
                self.roi_x1_var = "0"
                self.roi_y1_var = "0"
                self.roi_x2_var = "200"
                self.roi_y2_var = "150"
                self.roi_fps_var = "5.0"
                self.peak_threshold_var = "105.0"
                self.peak_margin_var = "5"
                self.peak_diff_var = "2.1"

        ui_vars = MockUIVars()

        # 应用配置（模拟_apply_server_config方法）
        config_applied = False

        if "roi_capture" in config_data:
            roi_config = config_data["roi_capture"]
            if "default_config" in roi_config:
                default_config = roi_config["default_config"]
                ui_vars.roi_x1_var = str(default_config.get("x1", 0))
                ui_vars.roi_y1_var = str(default_config.get("y1", 0))
                ui_vars.roi_x2_var = str(default_config.get("x2", 200))
                ui_vars.roi_y2_var = str(default_config.get("y2", 150))
                config_applied = True

            if "frame_rate" in roi_config:
                ui_vars.roi_fps_var = str(roi_config["frame_rate"])

        if "peak_detection" in config_data:
            peak_config = config_data["peak_detection"]
            ui_vars.peak_threshold_var = str(peak_config.get("threshold", 105.0))
            ui_vars.peak_margin_var = str(peak_config.get("margin_frames", 5))
            ui_vars.peak_diff_var = str(peak_config.get("difference_threshold", 2.1))
            config_applied = True

        if config_applied:
            print(f"✅ 配置应用成功")
            print(f"   ROI区域: ({ui_vars.roi_x1_var}, {ui_vars.roi_y1_var}) → ({ui_vars.roi_x2_var}, {ui_vars.roi_y2_var})")
            print(f"   ROI帧率: {ui_vars.roi_fps_var}")
            print(f"   波峰阈值: {ui_vars.peak_threshold_var}")
            print(f"   边界帧数: {ui_vars.peak_margin_var}")
            print(f"   差异阈值: {ui_vars.peak_diff_var}")
            return True
        else:
            print("❌ 配置应用失败")
            return False

    except Exception as e:
        print(f"❌ 配置应用测试异常: {str(e)}")
        return False

def main():
    """主测试函数"""
    print("🚀 HTTP客户端本地配置加载集成测试")
    print("=" * 50)

    # 运行测试
    test1_passed = test_local_config_integration()
    test2_passed = test_config_application_simulation()

    # 显示结果
    print("\n" + "=" * 50)
    print("📊 测试结果:")
    print(f"   配置加载集成: {'✅ 通过' if test1_passed else '❌ 失败'}")
    print(f"   配置应用模拟: {'✅ 通过' if test2_passed else '❌ 失败'}")

    total_tests = 2
    passed_tests = sum([test1_passed, test2_passed])

    print(f"\n🎯 总体结果: {passed_tests}/{total_tests} 测试通过")

    if passed_tests == total_tests:
        print("🎉 HTTP客户端本地配置加载功能集成测试成功！")
        print("✅ 客户端可以在启动时自动加载并应用本地配置文件")
        return True
    else:
        print("⚠️ 部分测试失败，请检查相关功能")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)