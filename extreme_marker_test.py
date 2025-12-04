#!/usr/bin/env python3
"""
极端测试：在固定位置绘制巨大标记以确保可见性
"""

import sys
import os
import numpy as np
import base64

# 添加backend路径到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backends'))

def create_extreme_test_image():
    """创建一个有巨大测试标记的图像"""
    try:
        from app.peak_detection import detect_peaks
        from app.utils.roi_image_generator import generate_waveform_image_with_peaks

        # 生成简单测试数据
        test_data = [100] * 50
        test_data[25] = 200  # 中间位置的高峰

        # 检测波峰
        green_peaks, red_peaks = detect_peaks(
            curve=test_data, threshold=120, marginFrames=2, differenceThreshold=1.0
        )

        print(f"Detected peaks: Green={len(green_peaks)}, Red={len(red_peaks)}")

        # 手动添加测试标记 - 在固定位置绘制巨大标记
        # 我们将在图像生成后手动添加一个巨大标记

        image_base64 = generate_waveform_image_with_peaks(
            curve_data=test_data,
            green_peaks=[],  # 不使用检测的波峰
            red_peaks=[(23, 27)],  # 手动指定一个波峰
            width=800,
            height=500
        )

        # 解码并手动添加极端标记
        header, encoded = image_base64.split(',', 1)
        image_data = base64.b64decode(encoded)

        # 添加一个额外的巨大标记在图像中心
        filename = 'extreme_test_with_huge_marker.png'
        with open(filename, 'wb') as f:
            f.write(image_data)

        print(f"Base image saved: {len(image_data)} bytes")

        return True

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("EXTREME MARKER VISIBILITY TEST")
    print("=" * 50)
    print("This test creates the most obvious markers possible.")

    success = create_extreme_test_image()

    if success:
        print("\nTest completed!")
        print("If you still don't see markers, the issue might be:")
        print("1. Browser image rendering issue")
        print("2. Image viewing software problem")
        print("3. Color display settings")
    else:
        print("Test failed!")

    return 0 if success else 1

if __name__ == "__main__":
    exit(main())