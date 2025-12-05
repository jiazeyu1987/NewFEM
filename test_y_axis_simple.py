#!/usr/bin/env python3
"""
Simple test to verify Y-axis is fixed to 0-200 range
"""

import re

def main():
    print("Testing Y-axis fixed range (0-200)")
    print("=" * 50)

    # Test frontend
    print("\n[Frontend Test]")
    try:
        with open('fronted/index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Check for Y-axis mapping 0-200
        if '0-200' in html_content and 'Y轴' in html_content:
            print("PASS: Y-axis mapping comment found (0-200)")
        else:
            print("FAIL: Y-axis mapping comment not found")

        # Check for grid lines 0-200
        if 'for (let v = 0; v <= 200; v += 40)' in html_content:
            print("PASS: Grid lines configured for 0-200 range")
        else:
            print("FAIL: Grid lines not properly configured")

        # Check for fixed Y-axis comment
        if '固定Y轴范围0~200' in html_content:
            print("PASS: Fixed Y-axis comment found")
        else:
            print("FAIL: Fixed Y-axis comment not found")

    except Exception as e:
        print(f"ERROR: Frontend test failed - {e}")

    # Test Python client
    print("\n[Python Client Test]")
    try:
        with open('python_client/simple_http_client.py', 'r', encoding='utf-8') as f:
            py_content = f.read()

        # Count Y-axis settings
        ylim_count = py_content.count('set_ylim(0, 200)')
        if ylim_count >= 2:
            print(f"PASS: Found {ylim_count} instances of set_ylim(0, 200)")
        else:
            print(f"FAIL: Only found {ylim_count} instances of set_ylim(0, 200)")

        # Check for auto-scale comment
        if 'Y轴固定范围0-200，不进行自动缩放' in py_content:
            print("PASS: Auto-scale disabled comment found")
        else:
            print("FAIL: Auto-scale disabled comment not found")

    except Exception as e:
        print(f"ERROR: Python client test failed - {e}")

    print("\n" + "=" * 50)
    print("Test completed. Check results above.")

if __name__ == "__main__":
    main()