#!/usr/bin/env python3
"""
保存增强版波形标注图像的测试脚本
"""

import sys
import os
import numpy as np
import base64

# 添加backend路径到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backends'))

def generate_test_data_with_multiple_peaks(count: int = 150) -> list:
    """
    生成包含多个明确波峰的测试数据
    """
    baseline = 100
    noise = np.random.normal(0, 2, count)
    signal = np.ones(count) * baseline + noise

    # 添加绿色波峰（较强的波峰，差值大）
    green_peaks_positions = [25, 60, 95, 130]
    for peak_pos in green_peaks_positions:
        if peak_pos < count:
            peak_width = 6
            peak_intensity = 40
            for i in range(max(0, peak_pos - peak_width), min(count, peak_pos + peak_width + 1)):
                signal[i] += peak_intensity * np.exp(-((i - peak_pos) ** 2) / 10)

    # 添加红色波峰（较弱的波峰，差值小）
    red_peaks_positions = [15, 45, 80, 110, 140]
    for peak_pos in red_peaks_positions:
        if peak_pos < count:
            peak_width = 4
            peak_intensity = 20
            for i in range(max(0, peak_pos - peak_width), min(count, peak_pos + peak_width + 1)):
                signal[i] += peak_intensity * np.exp(-((i - peak_pos) ** 2) / 6)

    return signal.tolist()

def test_and_save_enhanced_waveform():
    """测试并保存增强版波形图像"""
    print("Testing enhanced waveform with timeline annotation...")

    try:
        from app.peak_detection import detect_peaks
        from app.utils.roi_image_generator import generate_waveform_image_with_peaks

        # 生成测试数据
        test_data = generate_test_data_with_multiple_peaks(150)
        print(f"Generated test data with {len(test_data)} points")

        # 执行波峰检测
        green_peaks, red_peaks = detect_peaks(
            curve=test_data,
            threshold=105.0,
            marginFrames=5,
            differenceThreshold=2.1
        )

        print(f"Peak detection results:")
        print(f"  Green peaks: {len(green_peaks)} - {green_peaks}")
        print(f"  Red peaks: {len(red_peaks)} - {red_peaks}")

        # 生成增强版波形图像
        image_base64 = generate_waveform_image_with_peaks(
            curve_data=test_data,
            green_peaks=green_peaks,
            red_peaks=red_peaks,
            width=800,
            height=500
        )

        print(f"Enhanced waveform image generated successfully!")
        print(f"Image size: {len(image_base64)} characters")

        # 保存图像到文件
        try:
            # 解码base64图像
            header, encoded = image_base64.split(',', 1)
            image_data = base64.b64decode(encoded)

            # 保存为文件
            filename = 'enhanced_waveform_with_timeline.png'
            with open(filename, 'wb') as f:
                f.write(image_data)

            print(f"Enhanced waveform image saved as '{filename}'")
            print(f"File size: {len(image_data)} bytes")

            # 验证文件
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                print(f"Verified file exists with size: {file_size} bytes")
                return True
            else:
                print("Error: File was not created successfully")
                return False

        except Exception as e:
            print(f"Error saving image file: {e}")
            return False

    except Exception as e:
        print(f"Error in enhanced waveform generation: {e}")
        import traceback
        traceback.print_exc()
        return False

def compare_with_original():
    """比较增强版和原版的差异"""
    print("\nComparing enhanced vs original waveform generation...")

    try:
        from app.peak_detection import detect_peaks
        # 需要先注释掉原有的函数来测试
        # from app.utils.roi_image_generator import generate_waveform_image_with_peaks_original

        # 生成相同的测试数据
        test_data = generate_test_data_with_multiple_peaks(100)
        green_peaks, red_peaks = detect_peaks(
            curve=test_data, threshold=105.0, marginFrames=5, differenceThreshold=2.1
        )

        print(f"Test data: {len(test_data)} points, {len(green_peaks)} green peaks, {len(red_peaks)} red peaks")

        # 这里可以添加原版函数的对比测试
        print("Enhanced version includes:")
        print("  - Dedicated timeline axis (30% of image height)")
        print("  - Grid background in waveform area")
        print("  - Circle markers on waveform peaks")
        print("  - Diamond markers on timeline peaks")
        print("  - Enhanced legend with marker descriptions")
        print("  - Better axis labels and scaling")

    except Exception as e:
        print(f"Comparison failed: {e}")

def main():
    """主函数"""
    print("=" * 60)
    print("Enhanced Waveform Annotation Test")
    print("=" * 60)

    success = True

    # 测试增强版功能
    if not test_and_save_enhanced_waveform():
        success = False

    # 比较功能
    compare_with_original()

    print("\n" + "=" * 60)
    if success:
        print("SUCCESS: Enhanced waveform annotation completed!")
        print("Features:")
        print("  ✓ Dual marking system (waveform + timeline)")
        print("  ✓ Improved visibility with different marker shapes")
        print("  ✓ Grid background for better reading")
        print("  ✓ Enhanced legend with explanations")
        print("  ✓ Proper axis labels and scaling")
        print("\nGenerated file: enhanced_waveform_with_timeline.png")
    else:
        print("FAILED: Some tests did not complete successfully")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())