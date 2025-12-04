#!/usr/bin/env python3
"""
测试直接在波形曲线上着色的新方法
"""

import sys
import os
import numpy as np
import base64

# 添加backend路径到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backends'))

def create_test_data_with_obvious_peaks():
    """创建有明显波峰的测试数据"""
    count = 80
    baseline = 100
    data = [baseline] * count

    # 添加一些基础噪声
    for i in range(count):
        data[i] += np.random.normal(0, 1)

    # 添加明显的绿色波峰（高而尖锐）
    for pos in [15, 40, 65]:
        if pos < count:
            # 创建尖锐的高峰
            for offset in [-2, -1, 0, 1, 2]:
                idx = pos + offset
                if 0 <= idx < count:
                    if offset == 0:
                        data[idx] += 50  # 峰顶
                    elif offset == -1 or offset == 1:
                        data[idx] += 35  # 次高点
                    else:
                        data[idx] += 20  # 边缘点

    # 添加明显的红色波峰（较低但明显）
    for pos in [25, 55]:
        if pos < count:
            # 创建较低但明显的波峰
            for offset in [-1, 0, 1]:
                idx = pos + offset
                if 0 <= idx < count:
                    if offset == 0:
                        data[idx] += 25  # 峰顶
                    else:
                        data[idx] += 15  # 边缘点

    return data

def test_direct_curve_coloring():
    """测试直接曲线着色功能"""
    try:
        from app.peak_detection import detect_peaks
        from app.utils.roi_image_generator import generate_waveform_image_with_peaks

        print("=" * 60)
        print("DIRECT WAVEFORM CURVE COLORING TEST")
        print("=" * 60)

        # 创建测试数据
        test_data = create_test_data_with_obvious_peaks()
        print(f"Generated test data with {len(test_data)} points")

        # 显示一些关键位置的数值
        key_positions = [15, 25, 40, 55, 65]
        print("Key positions:")
        for pos in key_positions:
            if pos < len(test_data):
                print(f"  Position {pos}: {test_data[pos]:.1f}")

        # 使用较低的阈值确保检测到所有波峰
        threshold = 110.0
        green_peaks, red_peaks = detect_peaks(
            curve=test_data,
            threshold=threshold,
            marginFrames=3,
            differenceThreshold=1.5
        )

        print(f"\nPeak detection results with threshold {threshold}:")
        print(f"  Green peaks: {len(green_peaks)} - {green_peaks}")
        print(f"  Red peaks: {len(red_peaks)} - {red_peaks}")

        # 生成带有直接着色的波形图像
        print(f"\nGenerating waveform with direct curve coloring...")
        image_base64 = generate_waveform_image_with_peaks(
            curve_data=test_data,
            green_peaks=green_peaks,
            red_peaks=red_peaks,
            width=800,
            height=400
        )

        if image_base64:
            print(f"Image generated successfully! Size: {len(image_base64)} characters")

            # 保存图像
            header, encoded = image_base64.split(',', 1)
            image_data = base64.b64decode(encoded)

            filename = 'direct_colored_waveform_test.png'
            with open(filename, 'wb') as f:
                f.write(image_data)

            file_size = len(image_data)
            print(f"Image saved as '{filename}' ({file_size} bytes)")

            # 验证文件存在
            if os.path.exists(filename):
                actual_size = os.path.getsize(filename)
                print(f"File verification: SUCCESS - {actual_size} bytes")

                print("\n" + "=" * 60)
                print("SUCCESS: Direct curve coloring test completed!")
                print("\nWhat you should see in the image:")
                print("  - Normal waveform: Blue thin lines")
                print("  - Green peak segments: Green thick lines")
                print("  - Red peak segments: Red thick lines")
                print("  - Timeline with diamond markers at peak positions")
                print("  - Grid background for better visualization")
                print(f"\nExpected colored segments based on detected peaks:")
                print(f"  Green segments: {len(green_peaks)} regions")
                print(f"  Red segments: {len(red_peaks)} regions")

                return True
            else:
                print("File verification: FAILED - file not created")
                return False
        else:
            print("FAILED: No image generated")
            return False

    except Exception as e:
        print(f"Error in direct curve coloring test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    success = test_direct_curve_coloring()
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())