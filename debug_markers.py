#!/usr/bin/env python3
"""
调试波峰标记显示问题的脚本
"""

import sys
import os
import numpy as np
import base64

# 添加backend路径到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backends'))

def test_with_debug():
    """测试并添加调试信息"""
    try:
        from app.peak_detection import detect_peaks
        from app.utils.roi_image_generator import generate_waveform_image_with_peaks

        # 生成简单的测试数据
        count = 50
        baseline = 100
        test_data = [baseline] * count

        # 在特定位置添加明显的波峰
        test_data[10:15] = [140, 145, 150, 145, 140]  # 强波峰 (应该是绿色)
        test_data[25:30] = [125, 130, 135, 130, 125]  # 中等波峰 (可能是红色)

        print(f"Test data created with {len(test_data)} points")
        print(f"Peak at position 12: {test_data[12]} (should be green)")
        print(f"Peak at position 27: {test_data[27]} (should be red)")

        # 执行波峰检测
        green_peaks, red_peaks = detect_peaks(
            curve=test_data,
            threshold=120.0,  # 降低阈值以确保检测到波峰
            marginFrames=3,
            differenceThreshold=1.0
        )

        print(f"\nPeak detection results:")
        print(f"Green peaks: {green_peaks}")
        print(f"Red peaks: {red_peaks}")

        # 手动创建一个测试用的小图像，确保标记函数工作
        print(f"\nTesting marker drawing with simple case...")

        # 生成图像
        image_base64 = generate_waveform_image_with_peaks(
            curve_data=test_data,
            green_peaks=green_peaks,
            red_peaks=red_peaks,
            width=400,
            height=300
        )

        print(f"Enhanced waveform image generated successfully!")
        print(f"Image size: {len(image_base64)} characters")

        # 保存图像
        header, encoded = image_base64.split(',', 1)
        image_data = base64.b64decode(encoded)

        with open('debug_waveform_with_markers.png', 'wb') as f:
            f.write(image_data)

        print(f"Debug image saved as 'debug_waveform_with_markers.png'")
        print(f"File size: {len(image_data)} bytes")

        # 检查预期的标记位置
        print(f"\nExpected marker positions:")
        if green_peaks:
            for i, (start, end) in enumerate(green_peaks):
                center = (start + end) // 2
                print(f"Green marker {i+1}: frame {center} (value: {test_data[center]})")
        if red_peaks:
            for i, (start, end) in enumerate(red_peaks):
                center = (start + end) // 2
                print(f"Red marker {i+1}: frame {center} (value: {test_data[center]})")

        return True

    except Exception as e:
        print(f"Error in debug test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("Debugging Peak Marker Display")
    print("=" * 40)

    success = test_with_debug()

    print("=" * 40)
    if success:
        print("Debug completed!")
        print("Check 'debug_waveform_with_markers.png' for marker visibility")
    else:
        print("Debug failed!")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())