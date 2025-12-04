#!/usr/bin/env python3
"""
测试波峰标注功能的独立脚本
"""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple

# 添加backend路径到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backends'))

from app.peak_detection import detect_peaks
from app.utils.roi_image_generator import generate_waveform_image_with_peaks
import base64
from io import BytesIO

def generate_test_waveform_data(count: int = 100) -> List[float]:
    """
    生成测试用的波形数据，包含一些预设的波峰
    """
    baseline = 100
    noise = np.random.normal(0, 3, count)

    # 基础信号
    signal = np.ones(count) * baseline + noise

    # 添加绿色波峰（较强的波峰）
    green_peaks_positions = [20, 45, 70]
    for peak_pos in green_peaks_positions:
        if peak_pos < count:
            peak_width = 5
            for i in range(max(0, peak_pos - peak_width), min(count, peak_pos + peak_width + 1)):
                signal[i] += 35 * np.exp(-((i - peak_pos) ** 2) / 8)

    # 添加红色波峰（较弱的波峰）
    red_peaks_positions = [10, 30, 60, 85]
    for peak_pos in red_peaks_positions:
        if peak_pos < count:
            peak_width = 3
            for i in range(max(0, peak_pos - peak_width), min(count, peak_pos + peak_width + 1)):
                signal[i] += 20 * np.exp(-((i - peak_pos) ** 2) / 6)

    return signal.tolist()

def test_peak_detection():
    """测试波峰检测功能"""
    print("Testing peak detection...")

    # 生成测试数据
    test_data = generate_test_waveform_data(100)

    # 执行波峰检测
    green_peaks, red_peaks = detect_peaks(
        curve=test_data,
        threshold=105.0,
        marginFrames=5,
        differenceThreshold=2.1
    )

    print(f"[OK] Peak detection completed:")
    print(f"   - Green peaks: {len(green_peaks)}")
    print(f"   - Red peaks: {len(red_peaks)}")
    print(f"   - Total peaks: {len(green_peaks) + len(red_peaks)}")

    if green_peaks:
        print(f"   - Green peak ranges: {green_peaks}")
    if red_peaks:
        print(f"   - Red peak ranges: {red_peaks}")

    return test_data, green_peaks, red_peaks

def test_waveform_annotation():
    """测试波形标注功能"""
    print("\n🎨 Testing waveform annotation...")

    # 获取测试数据
    test_data, green_peaks, red_peaks = test_peak_detection()

    try:
        # 生成带有波峰标注的图像
        image_base64 = generate_waveform_image_with_peaks(
            curve_data=test_data,
            green_peaks=green_peaks,
            red_peaks=red_peaks,
            width=800,
            height=400
        )

        print(f"✅ Waveform annotation image generated successfully!")
        print(f"   - Image size: {len(image_base64)} characters")
        print(f"   - Data type: {'base64' if image_base64.startswith('data:image') else 'unknown'}")

        # 保存图像到文件用于验证
        try:
            # 解码base64图像
            header, encoded = image_base64.split(',', 1)
            image_data = base64.b64decode(encoded)

            # 保存为文件
            with open('test_waveform_with_peaks.png', 'wb') as f:
                f.write(image_data)

            print(f"✅ Test image saved as 'test_waveform_with_peaks.png'")

        except Exception as e:
            print(f"⚠️ Could not save test image: {e}")

        return True

    except Exception as e:
        print(f"❌ Waveform annotation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_comparison_chart():
    """创建对比图表显示原始数据和检测结果"""
    print("\n📊 Creating comparison chart...")

    try:
        # 生成测试数据
        test_data, green_peaks, red_peaks = test_peak_detection()

        # 创建图表
        plt.figure(figsize=(12, 6))

        # 绘制波形数据
        x = range(len(test_data))
        plt.plot(x, test_data, 'b-', linewidth=2, label='Waveform', alpha=0.7)

        # 标记绿色波峰
        for start, end in green_peaks:
            if start < len(test_data) and end < len(test_data):
                peak_region = test_data[start:end+1]
                peak_value = max(peak_region)
                peak_position = start + peak_region.index(peak_value)
                plt.axvspan(start, end, alpha=0.3, color='green', label='Green Peak' if start == green_peaks[0][0] else "")
                plt.plot(peak_position, peak_value, 'go', markersize=8)

        # 标记红色波峰
        for start, end in red_peaks:
            if start < len(test_data) and end < len(test_data):
                peak_region = test_data[start:end+1]
                peak_value = max(peak_region)
                peak_position = start + peak_region.index(peak_value)
                plt.axvspan(start, end, alpha=0.3, color='red', label='Red Peak' if start == red_peaks[0][0] else "")
                plt.plot(peak_position, peak_value, 'ro', markersize=8)

        # 添加阈值线
        plt.axhline(y=105, color='orange', linestyle='--', alpha=0.7, label='Threshold')

        plt.title('Peak Detection Test Results')
        plt.xlabel('Frame Index')
        plt.ylabel('Signal Value')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        # 保存图表
        plt.savefig('peak_detection_comparison.png', dpi=150, bbox_inches='tight')
        plt.close()

        print("✅ Comparison chart saved as 'peak_detection_comparison.png'")
        return True

    except Exception as e:
        print(f"❌ Failed to create comparison chart: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 Starting waveform annotation tests...\n")

    success = True

    # 测试1: 波峰检测
    try:
        test_peak_detection()
    except Exception as e:
        print(f"❌ Peak detection test failed: {e}")
        success = False

    # 测试2: 波形标注
    try:
        if not test_waveform_annotation():
            success = False
    except Exception as e:
        print(f"❌ Waveform annotation test failed: {e}")
        success = False

    # 测试3: 创建对比图表（可选，需要matplotlib）
    try:
        create_comparison_chart()
    except ImportError:
        print("⚠️ matplotlib not available, skipping comparison chart")
    except Exception as e:
        print(f"⚠️ Comparison chart creation failed: {e}")

    # 输出结果
    if success:
        print("\n🎉 All core tests completed successfully!")
        print("📁 Check the following files:")
        print("   - test_waveform_with_peaks.png (annotated waveform image)")
        print("   - peak_detection_comparison.png (comparison chart)")
    else:
        print("\n❌ Some tests failed. Check the error messages above.")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())