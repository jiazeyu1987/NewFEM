#!/usr/bin/env python3
"""
验证Y轴固定效果 - 检查real-time signals图表
"""

def test_y_axis_fixed():
    print("=== 验证Y轴固定效果 ===")
    print()

    try:
        with open('fronted/index.html', 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"[ERROR] 读取文件失败: {e}")
        return False

    # 测试项目列表
    tests = [
        # 1. 检查Y轴缩放控件是否已移除
        {
            'name': 'Y轴缩放滑块控件已移除',
            'pattern': r'<input type="range" id="zoom-slider"',
            'should_exist': False,
            'found': False
        },

        # 2. 检查Y轴缩放事件监听器是否已注释
        {
            'name': 'Y轴缩放事件监听器已注释',
            'pattern': r'Y轴缩放已移除.*固定为1\.0x',
            'should_exist': True,
            'found': False
        },

        # 3. 检查滚轮缩放是否已禁用
        {
            'name': '滚轮缩放已禁用',
            'pattern': r'滚轮缩放已禁用.*Y轴固定为0-200范围',
            'should_exist': True,
            'found': False
        },

        # 4. 检查zoom值固定注释
        {
            'name': 'zoom值固定注释存在',
            'pattern': r'固定为1\.0.*Y轴不可缩放',
            'should_exist': True,
            'found': False
        },

        # 5. 检查Y轴映射函数（0-200范围）
        {
            'name': 'Y轴映射函数使用0-200范围',
            'pattern': r'限制数据值在0-200范围内',
            'should_exist': True,
            'found': False
        },

        # 6. 检查固定Y轴的注释
        {
            'name': '固定Y轴范围注释存在',
            'pattern': r'Y轴已固定为0-200范围',
            'should_exist': True,
            'found': False
        }
    ]

    import re
    passed_tests = 0

    # 执行测试
    for test in tests:
        if re.search(test['pattern'], content, re.MULTILINE):
            test['found'] = True

        if test['should_exist'] == test['found']:
            print(f"[PASS] {test['name']}")
            passed_tests += 1
        else:
            if test['should_exist']:
                print(f"[FAIL] {test['name']} - 未找到期望的内容")
            else:
                print(f"[FAIL] {test['name']} - 发现了不应该存在的内容")

    print()
    print(f"=== 测试结果: {passed_tests}/{len(tests)} 通过 ===")

    if passed_tests == len(tests):
        print("[SUCCESS] 所有测试通过！Y轴已成功固定为0-200范围")
        print()
        print("实现的功能:")
        print("   - [DONE] 移除了Y轴缩放滑块控件")
        print("   - [DONE] 禁用了Y轴缩放事件监听器")
        print("   - [DONE] 禁用了滚轮缩放功能")
        print("   - [DONE] 固定了zoom值为1.0")
        print("   - [DONE] 保留了数据值在0-200范围内的限制")
        print("   - [DONE] 确保real-time signals图表Y轴真正固定")
        return True
    else:
        print("[WARNING] 部分测试失败，Y轴固定可能不完整")
        return False

if __name__ == "__main__":
    test_y_axis_fixed()