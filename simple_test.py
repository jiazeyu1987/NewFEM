#!/usr/bin/env python3
"""
简单的波峰标注功能测试
"""

import sys
import os
import numpy as np

# 添加backend路径到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backends'))

def test_peak_detection():
    """测试波峰检测功能"""
    try:
        from app.peak_detection import detect_peaks

        # 生成测试数据
        count = 100
        baseline = 100
        noise = np.random.normal(0, 3, count)
        signal = np.ones(count) * baseline + noise

        # 添加一些波峰
        signal[20:26] += 35  # 绿色波峰
        signal[45:50] += 35  # 绿色波峰
        signal[70:74] += 35  # 绿色波峰
        signal[10:14] += 20  # 红色波峰
        signal[30:34] += 20  # 红色波峰

        test_data = signal.tolist()

        # 执行波峰检测
        green_peaks, red_peaks = detect_peaks(
            curve=test_data,
            threshold=105.0,
            marginFrames=5,
            differenceThreshold=2.1
        )

        print(f"Peak detection test completed successfully:")
        print(f"  Green peaks: {len(green_peaks)}")
        print(f"  Red peaks: {len(red_peaks)}")

        if green_peaks:
            print(f"  Green peak ranges: {green_peaks}")
        if red_peaks:
            print(f"  Red peak ranges: {red_peaks}")

        return test_data, green_peaks, red_peaks

    except Exception as e:
        print(f"Peak detection test failed: {e}")
        import traceback
        traceback.print_exc()
        return None, [], []

def test_waveform_annotation():
    """测试波形标注功能"""
    try:
        from app.utils.roi_image_generator import generate_waveform_image_with_peaks

        # 获取测试数据
        test_data, green_peaks, red_peaks = test_peak_detection()

        if test_data is None:
            print("Cannot test waveform annotation - peak detection failed")
            return False

        # 生成带有波峰标注的图像
        image_base64 = generate_waveform_image_with_peaks(
            curve_data=test_data,
            green_peaks=green_peaks,
            red_peaks=red_peaks,
            width=800,
            height=400
        )

        print(f"Waveform annotation test completed successfully!")
        print(f"Generated image size: {len(image_base64)} characters")

        # 简单验证返回的数据格式
        if image_base64.startswith('data:image/png;base64,'):
            print("Image format is correct (PNG base64)")
        else:
            print("Warning: Unexpected image format")

        return True

    except Exception as e:
        print(f"Waveform annotation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("Starting waveform annotation tests...")
    print("=" * 50)

    success = True

    # 测试1: 波峰检测和波形标注
    if not test_waveform_annotation():
        success = False

    print("=" * 50)
    if success:
        print("All tests completed successfully!")
        return 0
    else:
        print("Some tests failed!")
        return 1

if __name__ == "__main__":
    exit(main())