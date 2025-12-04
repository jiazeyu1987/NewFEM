#!/usr/bin/env python3
"""
最终的波峰标记测试 - 生成非常明显的标记
"""

import sys
import os
import numpy as np
import base64

# 添加backend路径到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backends'))

def create_obvious_peaks():
    """创建非常明显的波峰用于测试"""
    # 生成100个点的数据
    count = 100
    baseline = 100
    data = [baseline] * count

    # 添加一些噪声
    for i in range(count):
        data[i] += np.random.normal(0, 1)

    # 添加非常明显的波峰
    # 绿色波峰 - 高而尖
    for pos in [20, 50, 80]:
        if pos < count:
            data[pos-2:pos+3] = [130, 150, 170, 150, 130]

    # 红色波峰 - 低但明显
    for pos in [35, 65]:
        if pos < count:
            data[pos-1:pos+2] = [110, 120, 110]

    return data

def test_final_markers():
    """最终测试"""
    try:
        from app.peak_detection import detect_peaks
        from app.utils.roi_image_generator import generate_waveform_image_with_peaks

        print("Creating test data with obvious peaks...")
        test_data = create_obvious_peaks()

        # 使用较低的阈值确保检测到所有波峰
        threshold = 110.0
        green_peaks, red_peaks = detect_peaks(
            curve=test_data,
            threshold=threshold,
            marginFrames=3,
            differenceThreshold=1.5
        )

        print(f"Peak detection with threshold {threshold}:")
        print(f"  Green peaks: {len(green_peaks)} - {green_peaks}")
        print(f"  Red peaks: {len(red_peaks)} - {red_peaks}")

        # 计算一些预期位置用于验证
        expected_positions = {
            20: "Expected green peak (very high)",
            35: "Expected red peak (moderate)",
            50: "Expected green peak (very high)",
            65: "Expected red peak (moderate)",
            80: "Expected green peak (very high)"
        }

        print(f"\nData verification:")
        for pos, desc in expected_positions.items():
            if pos < len(test_data):
                print(f"  Position {pos}: {test_data[pos]:.1f} - {desc}")

        # 生成图像
        print(f"\nGenerating enhanced waveform image...")
        image_base64 = generate_waveform_image_with_peaks(
            curve_data=test_data,
            green_peaks=green_peaks,
            red_peaks=red_peaks,
            width=800,
            height=500
        )

        print(f"Image generated: {len(image_base64)} characters")

        # 保存图像
        header, encoded = image_base64.split(',', 1)
        image_data = base64.b64decode(encoded)

        filename = 'final_marker_test.png'
        with open(filename, 'wb') as f:
            f.write(image_data)

        file_size = len(image_data)
        print(f"Final test image saved as '{filename}' ({file_size} bytes)")

        # 验证文件存在
        if os.path.exists(filename):
            print(f"File verification: SUCCESS - {file_size} bytes")
        else:
            print(f"File verification: FAILED - file not created")

        return len(green_peaks) > 0 or len(red_peaks) > 0

    except Exception as e:
        print(f"Error in final test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("FINAL PEAK MARKER VISIBILITY TEST")
    print("=" * 60)
    print("This test creates very obvious peaks to ensure markers are visible.")
    print()

    success = test_final_markers()

    print("\n" + "=" * 60)
    if success:
        print("SUCCESS: Final test completed!")
        print("\nWhat you should see in the image:")
        print("  - Upper 70%: Waveform curve with large colored circles")
        print("    - Green circles: High peaks (stable HEM events)")
        print("    - Red circles: Lower peaks (unstable events)")
        print("  - Lower 30%: Timeline with diamond markers")
        print("  - Right side: Legend explaining the markers")
        print("  - Grid: Background grid for reading values")
        print("\nThe circles should be large and very visible!")
    else:
        print("FAILED: No peaks were detected or marked")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())