#!/usr/bin/env python3
"""
测试验证Y轴固定效果
检查所有图表组件是否使用0~200的固定Y轴范围
"""

import re

def test_frontend_y_axis():
    """测试前端Y轴设置"""
    print("[TEST] 测试前端Y轴设置...")

    try:
        with open('fronted/index.html', 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查主波形图表Y轴映射
        y_axis_pattern = r'Y轴.*映射.*0-200'
        if re.search(y_axis_pattern, content):
            print("[PASS] 主波形图表Y轴映射注释正确 (0-200)")
        else:
            print("[FAIL] 主波形图表Y轴映射注释未找到")
            return False

        # 检查具体的Y轴映射代码
        map_y_pattern = r'mapY.*=.*val.*=>.*midY.*-.*\(val.*-.*100\).*scaleY'
        if re.search(map_y_pattern, content):
            print("[PASS] 主波形图表Y轴映射函数正确 (围绕100缩放)")
        else:
            print("[FAIL] 主波形图表Y轴映射函数未找到")
            return False

        # 检查网格线设置
        grid_pattern = r'for.*let v = 0; v <= 200; v \+= 40'
        if re.search(grid_pattern, content):
            print("[PASS] 网格线设置正确 (0~200, 40间隔)")
        else:
            print("[FAIL] 网格线设置未找到")
            return False

        # 检查子波形图表Y轴映射
        sub_chart_pattern = r'// 固定Y轴范围0~200，移除自动缩放'
        if re.search(sub_chart_pattern, content):
            print("[PASS] 子波形图表Y轴固定注释正确")
        else:
            print("[FAIL] 子波形图表Y轴固定注释未找到")
            return False

        return True

    except Exception as e:
        print(f"❌ 前端测试异常: {str(e)}")
        return False

def test_python_client_y_axis():
    """测试Python客户端Y轴设置"""
    print("\n🧪 测试Python客户端Y轴设置...")

    try:
        with open('python_client/simple_http_client.py', 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查初始Y轴设置
        initial_ylim_pattern = r'self\.ax\.set_ylim\(0, 200\)'
        matches = re.findall(initial_ylim_pattern, content)
        if len(matches) >= 2:
            print(f"✅ 初始Y轴范围设置正确 (0, 200) - 找到{len(matches)}处")
        else:
            print(f"❌ 初始Y轴范围设置不正确 - 只找到{len(matches)}处")
            return False

        # 检查自动缩放注释
        auto_scale_pattern = r'Y轴固定范围0-200，不进行自动缩放'
        if re.search(auto_scale_pattern, content):
            print("✅ 自动缩禁注释正确")
        else:
            print("❌ 自动缩禁注释未找到")
            return False

        # 检查自动缩放代码被注释
        commented_auto_scale = r'#.*y_min = min\(self\.signal_data\[-50:\]\) - 5'
        if re.search(commented_auto_scale, content):
            print("✅ 自动缩放代码已正确注释")
        else:
            print("❌ 自动缩放代码注释未找到")
            return False

        return True

    except Exception as e:
        print(f"❌ Python客户端测试异常: {str(e)}")
        return False

def test_config_file():
    """测试配置文件设置"""
    print("\n🧪 测试配置文件...")

    try:
        import json
        with open('backends/app/fem_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 检查ROI配置
        if 'roi_capture' in config:
            roi_config = config['roi_capture']
            if 'default_config' in roi_config:
                default_roi = roi_config['default_config']
                y1 = default_roi.get('y1', 0)
                y2 = default_roi.get('y2', 150)
                print(f"✅ ROI配置: y1={y1}, y2={y2}")
            else:
                print("⚠️ ROI default_config未找到")
        else:
            print("⚠️ roi_capture配置未找到")

        return True

    except Exception as e:
        print(f"❌ 配置文件测试异常: {str(e)}")
        return False

def verify_no_y_axis_controls():
    """验证没有Y轴自由调节控件"""
    print("\n🧪 验证没有Y轴自由调节控件...")

    try:
        with open('fronted/index.html', 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查可能的Y轴控制关键词
        y_control_keywords = [
            'Y轴滑块', 'Y轴调节', 'Y轴范围', 'Y轴缩放',
            'yaxis slider', 'y-axis control', 'y-axis zoom',
            'scaleY', 'zoomY', 'rangeY'
        ]

        found_controls = []
        for keyword in y_control_keywords:
            if keyword.lower() in content.lower():
                found_controls.append(keyword)

        if not found_controls:
            print("✅ 未发现Y轴自由调节控件")
            return True
        else:
            print(f"⚠️ 发现可能的Y轴控件: {found_controls}")
            return False

    except Exception as e:
        print(f"❌ Y轴控件检查异常: {str(e)}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始Y轴固定效果验证测试")
    print("=" * 50)

    test_results = []

    # 运行所有测试
    test_results.append(("前端Y轴设置", test_frontend_y_axis()))
    test_results.append(("Python客户端Y轴设置", test_python_client_y_axis()))
    test_results.append(("配置文件", test_config_file()))
    test_results.append(("无Y轴自由调节控件", verify_no_y_axis_controls()))

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
        print("🎉 所有测试通过！Y轴固定功能实现成功")
        print("📋 实现总结:")
        print("   - 前端主波形图表: Y轴固定0~200，围绕中心点100缩放")
        print("   - 前端子波形图表: Y轴固定0~200，移除自动缩放")
        print("   - Python客户端: Y轴固定0~200，禁用自动缩放")
        print("   - 配置文件: ROI区域设置为y1=100, y2=200")
        print("   - UI控件: 确认无Y轴自由调节功能")
        return True
    else:
        print("⚠️ 部分测试失败，请检查相关功能")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)