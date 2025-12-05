#!/usr/bin/env python3
"""
测试UI切换功能实现
验证缩小/放大按钮的实现是否正确
"""

import re

def test_ui_switching_implementation():
    """测试UI切换功能的实现"""
    print("=== 测试UI切换功能实现 ===")
    print()

    try:
        with open('fronted/index.html', 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"[ERROR] 读取文件失败: {e}")
        return False

    # 测试项目列表
    tests = [
        # 1. 检查UI切换按钮是否存在
        {
            'name': 'UI切换按钮HTML元素存在',
            'pattern': r'<button id="ui-toggle-btn".*?>\s*<span id="ui-toggle-text">缩小</span>\s*</button>',
            'should_exist': True,
            'found': False
        },

        # 2. 检查CSS样式是否定义
        {
            'name': 'UI切换按钮CSS样式定义',
            'pattern': r'\.ui-toggle-btn\s*\{',
            'should_exist': True,
            'found': False
        },

        # 3. 检查紧凑模式CSS样式
        {
            'name': '紧凑模式CSS样式定义',
            'pattern': r'body\.compact-mode\s*\{',
            'should_exist': True,
            'found': False
        },

        # 4. 检查隐藏组件CSS规则
        {
            'name': '隐藏组件CSS规则定义',
            'pattern': r'body\.compact-mode\s*\.hide-in-compact\s*\{',
            'should_exist': True,
            'found': False
        },

        # 5. 检查appState中UI模式属性
        {
            'name': 'appState中UI模式属性定义',
            'pattern': r'uiMode:\s*[\'"]expanded[\'"]',
            'should_exist': True,
            'found': False
        },

        # 6. 检查切换函数定义
        {
            'name': 'UI模式切换函数定义',
            'pattern': r'function toggleUIMode\(\)\s*\{',
            'should_exist': True,
            'found': False
        },

        # 7. 检查恢复函数定义
        {
            'name': 'UI模式恢复函数定义',
            'pattern': r'function restoreUIMode\(\)\s*\{',
            'should_exist': True,
            'found': False
        },

        # 8. 检查事件监听器
        {
            'name': 'UI切换按钮事件监听器',
            'pattern': r'uiToggleBtn\.addEventListener\([\'"]click[\'"],\s*toggleUIMode\)',
            'should_exist': True,
            'found': False
        },

        # 9. 检查必要组件标识
        {
            'name': '必要按钮组件标识',
            'pattern': r'class="essential-btn"',
            'should_exist': True,
            'found': False
        },

        # 10. 检查隐藏组件标识
        {
            'name': '隐藏组件标识',
            'pattern': r'class="hide-in-compact"',
            'should_exist': True,
            'found': False
        },

        # 11. 检查localStorage支持
        {
            'name': 'localStorage持久化支持',
            'pattern': r'localStorage\.setItem\([\'"]newfem-ui-mode[\'"]',
            'should_exist': True,
            'found': False
        },

        # 12. 检查按钮文本切换逻辑
        {
            'name': '按钮文本切换逻辑',
            'pattern': r'uiToggleText\.textContent\s*=\s*newMode\s*===\s*[\'"]compact[\'"]\s*\?\s*[\'"]放大[\'"]\s*:\s*[\'"]缩小[\'"]',
            'should_exist': True,
            'found': False
        }
    ]

    passed_tests = 0

    # 执行测试
    for test in tests:
        if re.search(test['pattern'], content, re.MULTILINE | re.DOTALL):
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
        print("[SUCCESS] UI切换功能实现完整！")
        print()
        print("实现的功能:")
        print("   - [DONE] UI切换按钮 (缩小/放大)")
        print("   - [DONE] CSS样式和类选择器")
        print("   - [DONE] 组件分类标识 (essential-btn, hide-in-compact)")
        print("   - [DONE] JavaScript切换逻辑")
        print("   - [DONE] 用户偏好存储 (localStorage)")
        print("   - [DONE] 按钮文本动态切换")
        print("   - [DONE] 紧凑模式和展开模式样式")
        print()
        print("使用方法:")
        print("   1. 点击工具栏中的'缩小'按钮进入紧凑模式")
        print("   2. 紧凑模式只显示: ROI截图, 主曲线, 截图曲线, 开始, 停止, 截图")
        print("   3. 点击'放大'按钮返回完整UI")
        print("   4. UI模式偏好会自动保存和恢复")
        return True
    else:
        print("[WARNING] 部分测试失败，UI切换功能实现可能不完整")
        return False

if __name__ == "__main__":
    test_ui_switching_implementation()