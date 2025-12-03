"""
ROI图片生成工具模块

为ROI监控生成基于信号值的模拟灰度图片
"""

from __future__ import annotations

import io
import base64
from typing import Tuple, List

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def generate_roi_image(signal_value: float, width: int = 200, height: int = 150) -> str:
    """
    生成基于信号值的ROI图片，返回base64编码的图片数据

    Args:
        signal_value: 当前信号值 (用于生成图片内容)
        width: 图片宽度
        height: 图片高度

    Returns:
        base64编码的图片字符串
    """
    # 创建基础灰度图像
    base_gray = int(np.clip(signal_value, 0, 255))

    # 创建numpy数组，使用基础灰度值
    img_array = np.full((height, width), base_gray, dtype=np.uint8)

    # 添加一些模拟的ROI区域和高亮效果
    _add_roi_regions(img_array, signal_value)

    # 转换为PIL图像
    image = Image.fromarray(img_array, mode='L')

    # 在图像上绘制文字信息
    _add_text_overlay(image, signal_value)

    # 转换为base64
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return f"data:image/png;base64,{img_base64}"


def _add_roi_regions(img_array: np.ndarray, signal_value: float) -> None:
    """
    在图像中添加模拟的ROI区域

    Args:
        img_array: 图像numpy数组
        signal_value: 信号值
    """
    height, width = img_array.shape

    # 添加一个中心ROI区域（较亮的方块）
    center_x, center_y = width // 2, height // 2
    roi_size = 30

    # 根据信号值调整ROI区域的亮度
    roi_brightness = int(np.clip(signal_value + 50, 0, 255))

    # 绘制中心ROI区域
    x1 = max(0, center_x - roi_size // 2)
    y1 = max(0, center_y - roi_size // 2)
    x2 = min(width, center_x + roi_size // 2)
    y2 = min(height, center_y + roi_size // 2)

    img_array[y1:y2, x1:x2] = roi_brightness

    # 添加一些随机噪声模拟真实信号
    noise = np.random.normal(0, 10, (height, width))
    img_array = np.clip(img_array + noise, 0, 255).astype(np.uint8)

    # 将结果写回原数组
    img_array[:] = img_array


def _add_text_overlay(image: Image, signal_value: float) -> None:
    """
    在图像上添加文字覆盖层

    Args:
        image: PIL图像对象
        signal_value: 信号值
    """
    draw = ImageDraw.Draw(image)

    try:
        # 尝试使用系统字体
        font = ImageFont.truetype("arial.ttf", 12)
    except (OSError, IOError):
        # 如果系统字体不可用，使用默认字体
        font = ImageFont.load_default()

    # 添加ROI标签
    text_lines = [
        "ROI Region",
        f"Value: {signal_value:.1f}",
        "Active"
    ]

    # 在图像左上角添加文字
    y_offset = 5
    for line in text_lines:
        # 添加文字阴影效果
        draw.text((6, y_offset + 1), line, fill=0, font=font)  # 阴影
        draw.text((5, y_offset), line, fill=255, font=font)    # 文字
        y_offset += 15


def create_roi_data_with_image(signal_value: float) -> Tuple[str, float]:
    """
    创建包含图片数据的ROI数据

    Args:
        signal_value: 当前信号值

    Returns:
        (base64图片数据, 灰度值) 的元组
    """
    # 生成图片
    image_data = generate_roi_image(signal_value)

    # 计算平均灰度值
    gray_value = float(np.clip(signal_value, 0, 255))

    return image_data, gray_value


def generate_waveform_image_with_peaks(
    curve_data: List[float],
    green_peaks: List[Tuple[int, int]],
    red_peaks: List[Tuple[int, int]],
    width: int = 600,
    height: int = 400
) -> str:
    """
    生成带有波峰标注的波形图像，包含主波形图和时间轴标注

    Args:
        curve_data: 波形数据数组
        green_peaks: 绿色波峰列表 [(start_frame, end_frame), ...]
        red_peaks: 红色波峰列表 [(start_frame, end_frame), ...]
        width: 图像宽度
        height: 图像高度

    Returns:
        base64编码的PNG图片字符串
    """
    if not curve_data:
        # 如果没有数据，返回空白图像
        img_array = np.zeros((height, width, 3), dtype=np.uint8) + 255
        image = Image.fromarray(img_array, mode='RGB')

        # 添加"无数据"文字
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except (OSError, IOError):
            font = ImageFont.load_default()

        text = "No Data"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (width - text_width) // 2
        y = (height - text_height) // 2

        draw.text((x, y), text, fill=128, font=font)

        return _image_to_base64(image)

    # 分配图像区域：主波形图占70%，时间轴占30%
    waveform_height = int(height * 0.7)
    timeline_height = height - waveform_height

    # 创建RGB图像（支持彩色标注）
    img_array = np.ones((height, width, 3), dtype=np.uint8) * 255  # 白色背景

    # 绘制主波形图
    _draw_enhanced_waveform_curve(img_array, curve_data, green_peaks, red_peaks, width, waveform_height)

    # 绘制时间轴标注
    _draw_timeline_axis(img_array, green_peaks, red_peaks, len(curve_data), width, timeline_height, waveform_height)

    # 转换为PIL图像
    image = Image.fromarray(img_array, mode='RGB')

    # 添加图例和标签
    _add_enhanced_waveform_legend(image, green_peaks, red_peaks, width, height)

    return _image_to_base64(image)


def _draw_enhanced_waveform_curve(
    img_array: np.ndarray,
    curve_data: List[float],
    green_peaks: List[Tuple[int, int]],
    red_peaks: List[Tuple[int, int]],
    img_width: int,
    waveform_height: int
) -> None:
    """
    绘制增强版波形曲线，包含网格线和波峰标记点

    Args:
        img_array: 图像numpy数组
        curve_data: 波形数据
        green_peaks: 绿色波峰列表
        red_peaks: 红色波峰列表
        img_width: 图像宽度
        waveform_height: 波形区域高度
    """
    num_points = len(curve_data)
    if num_points < 2:
        return

    # 计算数据范围
    min_val = min(curve_data)
    max_val = max(curve_data)
    range_val = max_val - min_val
    if range_val == 0:
        range_val = 1

    # 设置边距
    margin_left = 40
    margin_right = 20
    margin_top = 20
    margin_bottom = 30

    # 可用绘制区域
    plot_width = img_width - margin_left - margin_right
    plot_height = waveform_height - margin_top - margin_bottom

    # 绘制网格背景
    _draw_grid(img_array, margin_left, margin_top, plot_width, plot_height, waveform_height)

    # 计算波形点的坐标
    points = []
    for i, value in enumerate(curve_data):
        x = margin_left + int((i / (num_points - 1)) * plot_width)
        y = margin_top + plot_height - int(((value - min_val) / range_val) * plot_height)
        points.append((x, y))

    # 绘制波形曲线，直接在波峰段进行着色
    _draw_colored_waveform_curve(img_array, points, green_peaks, red_peaks)

    # 绘制坐标轴标签
    _draw_axis_labels(img_array, min_val, max_val, num_points, margin_left, margin_top, plot_width, plot_height)


def _draw_grid(img_array: np.ndarray, x_start: int, y_start: int, width: int, height: int, total_height: int) -> None:
    """
    绘制网格线
    """
    # 水平网格线
    for i in range(5):
        y = y_start + int(i * height / 4)
        for x in range(x_start, x_start + width):
            if y < total_height:
                img_array[y, x] = (240, 240, 240)  # 浅灰色

    # 垂直网格线
    for i in range(10):
        x = x_start + int(i * width / 9)
        if x_start + width <= img_array.shape[1]:
            for y in range(y_start, y_start + height):
                if y < total_height and x < img_array.shape[1]:
                    img_array[y, x] = (240, 240, 240)  # 浅灰色


def _draw_colored_waveform_curve(
    img_array: np.ndarray,
    points: List[Tuple[int, int]],
    green_peaks: List[Tuple[int, int]],
    red_peaks: List[Tuple[int, int]]
) -> None:
    """
    直接在波形曲线上进行着色，根据波峰范围给曲线段上色

    Args:
        img_array: 图像numpy数组
        points: 波形点坐标列表
        green_peaks: 绿色波峰列表 [(start_frame, end_frame), ...]
        red_peaks: 红色波峰列表 [(start_frame, end_frame), ...]
    """
    height, width = img_array.shape[:2]
    print(f"DEBUG: Drawing colored waveform curve. Image size: {width}x{height}")
    print(f"DEBUG: Points: {len(points)}, Green peaks: {len(green_peaks)}, Red peaks: {len(red_peaks)}")

    if len(points) < 2:
        return

    # 创建段颜色数组，默认为蓝色（正常波形）
    num_segments = len(points) - 1
    segment_colors = [(0, 50, 150)] * num_segments  # 蓝色正常段
    segment_thickness = [2] * num_segments  # 正常段细线

    # 标记绿色波峰段
    for start_frame, end_frame in green_peaks:
        for i in range(start_frame, min(end_frame, num_segments)):
            if 0 <= i < num_segments:
                segment_colors[i] = (0, 150, 0)  # 绿色
                segment_thickness[i] = 4  # 波峰段粗线

    # 标记红色波峰段
    for start_frame, end_frame in red_peaks:
        for i in range(start_frame, min(end_frame, num_segments)):
            if 0 <= i < num_segments:
                segment_colors[i] = (200, 50, 50)  # 红色
                segment_thickness[i] = 4  # 波峰段粗线

    print(f"DEBUG: Segment colors assigned. Green segments: {sum(1 for c in segment_colors if c == (0, 150, 0))}")
    print(f"DEBUG: Red segments: {sum(1 for c in segment_colors if c == (200, 50, 50))}")

    # 绘制每一段波形
    for i in range(num_segments):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        color = segment_colors[i]
        thickness = segment_thickness[i]

        # 确保坐标在图像范围内
        if (0 <= x1 < width and 0 <= y1 < height and
            0 <= x2 < width and 0 <= y2 < height):
            _draw_thick_line(img_array, x1, y1, x2, y2, color, thickness)
        else:
            print(f"DEBUG: Segment {i} coordinates out of bounds: ({x1},{y1}) -> ({x2},{y2})")

    print(f"DEBUG: Finished drawing colored waveform with {num_segments} segments")


def _draw_thick_line(img_array: np.ndarray, x1: int, y1: int, x2: int, y2: int, color: Tuple[int, int, int], thickness: int) -> None:
    """
    绘制粗线条，支持任意厚度

    Args:
        img_array: 图像numpy数组
        x1, y1: 起点坐标
        x2, y2: 终点坐标
        color: 颜色 (R, G, B)
        thickness: 线条厚度
    """
    height, width = img_array.shape[:2]

    # Bresenham算法绘制线条，然后扩展到指定厚度
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx - dy

    x, y = x1, y1

    while True:
        # 在当前点周围绘制厚度的圆点
        for tx in range(max(0, x - thickness // 2), min(width, x + thickness // 2 + 1)):
            for ty in range(max(0, y - thickness // 2), min(height, y + thickness // 2 + 1)):
                if (tx - x) ** 2 + (ty - y) ** 2 <= (thickness // 2 + 1) ** 2:
                    img_array[ty, tx] = color

        # 检查是否到达终点
        if x == x2 and y == y2:
            break

        # 移动到下一个点
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy


def _draw_circle(img_array: np.ndarray, cx: int, cy: int, radius: int, color: Tuple[int, int, int]) -> None:
    """
    绘制实心圆
    """
    height, width = img_array.shape[:2]
    for x in range(max(0, cx - radius), min(width, cx + radius + 1)):
        for y in range(max(0, cy - radius), min(height, cy + radius + 1)):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                img_array[y, x] = color


def _draw_axis_labels(
    img_array: np.ndarray,
    min_val: float,
    max_val: float,
    num_points: int,
    margin_left: int,
    margin_top: int,
    plot_width: int,
    plot_height: int
) -> None:
    """
    绘制坐标轴标签
    """
    from PIL import Image, ImageDraw, ImageFont
    temp_img = Image.fromarray(img_array)
    draw = ImageDraw.Draw(temp_img)

    try:
        font = ImageFont.truetype("arial.ttf", 10)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # Y轴标签（数值）
    for i in range(5):
        value = min_val + (max_val - min_val) * (4 - i) / 4
        y = margin_top + int(i * plot_height / 4)
        text = f"{value:.0f}"
        draw.text((5, y - 5), text, fill=(0, 0, 0), font=font)

    # X轴标签（帧数）
    for i in range(6):
        frame_num = int(i * (num_points - 1) / 5)
        x = margin_left + int(i * plot_width / 5)
        text = str(frame_num)
        # 兼容不同版本的PIL
        try:
            text_width = draw.textlength(text, font=font)
        except AttributeError:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]

        draw.text((x - text_width // 2, margin_top + plot_height + 5), text, fill=(0, 0, 0), font=font)

    # 写回数组
    img_array[:] = np.array(temp_img)


def _draw_timeline_axis(
    img_array: np.ndarray,
    green_peaks: List[Tuple[int, int]],
    red_peaks: List[Tuple[int, int]],
    total_points: int,
    img_width: int,
    timeline_height: int,
    waveform_height: int
) -> None:
    """
    绘制时间轴，在时间轴上标注波峰位置

    Args:
        img_array: 图像numpy数组
        green_peaks: 绿色波峰列表
        red_peaks: 红色波峰列表
        total_points: 总数据点数
        img_width: 图像宽度
        timeline_height: 时间轴区域高度
        waveform_height: 波形区域高度
    """
    margin_left = 40
    margin_right = 20
    axis_y = waveform_height + 20  # 时间轴的Y位置

    # 绘制时间轴主线
    for x in range(margin_left, img_width - margin_right):
        img_array[axis_y, x] = (100, 100, 100)  # 灰色

    # 绘制时间刻度
    _draw_timeline_ticks(img_array, total_points, margin_left, margin_right, img_width, axis_y, timeline_height)

    # 在时间轴上标记波峰位置
    _draw_timeline_peak_markers(img_array, green_peaks, red_peaks, total_points, margin_left, margin_right, img_width, axis_y, timeline_height)

    # 添加时间轴标签
    _add_timeline_label(img_array, margin_left, axis_y, timeline_height)


def _draw_timeline_ticks(
    img_array: np.ndarray,
    total_points: int,
    margin_left: int,
    margin_right: int,
    img_width: int,
    axis_y: int,
    timeline_height: int
) -> None:
    """
    绘制时间刻度线
    """
    num_ticks = min(11, total_points)  # 最多11个刻度

    for i in range(num_ticks):
        frame_num = int(i * (total_points - 1) / (num_ticks - 1)) if num_ticks > 1 else 0
        x = margin_left + int(frame_num * (img_width - margin_left - margin_right) / (total_points - 1))

        # 绘制刻度线
        tick_height = 8
        for y in range(axis_y, min(axis_y + tick_height, axis_y + timeline_height)):
            if x < img_width and y < img_array.shape[0]:
                img_array[y, x] = (100, 100, 100)  # 灰色


def _draw_timeline_peak_markers(
    img_array: np.ndarray,
    green_peaks: List[Tuple[int, int]],
    red_peaks: List[Tuple[int, int]],
    total_points: int,
    margin_left: int,
    margin_right: int,
    img_width: int,
    axis_y: int,
    timeline_height: int
) -> None:
    """
    在时间轴上绘制波峰标记
    """
    # 绘制绿色波峰标记
    for start, end in green_peaks:
        center_frame = (start + end) // 2
        x = margin_left + int(center_frame * (img_width - margin_left - margin_right) / (total_points - 1))

        # 绘制绿色菱形标记
        _draw_diamond_marker(img_array, x, axis_y - 10, (0, 200, 0))  # 绿色

    # 绘制红色波峰标记
    for start, end in red_peaks:
        center_frame = (start + end) // 2
        x = margin_left + int(center_frame * (img_width - margin_left - margin_right) / (total_points - 1))

        # 绘制红色菱形标记
        _draw_diamond_marker(img_array, x, axis_y - 10, (200, 0, 0))  # 红色


def _draw_diamond_marker(img_array: np.ndarray, cx: int, cy: int, color: Tuple[int, int, int]) -> None:
    """
    绘制菱形标记
    """
    size = 6
    points = [
        (cx, cy - size),      # 上
        (cx + size, cy),      # 右
        (cx, cy + size),      # 下
        (cx - size, cy),      # 左
    ]

    # 使用填充算法绘制菱形
    height, width = img_array.shape[:2]
    for y in range(max(0, cy - size), min(height, cy + size + 1)):
        for x in range(max(0, cx - size), min(width, cx + size + 1)):
            # 检查点是否在菱形内
            if (abs(x - cx) + abs(y - cy) <= size):
                img_array[y, x] = color


def _add_timeline_label(img_array: np.ndarray, margin_left: int, axis_y: int, timeline_height: int) -> None:
    """
    添加时间轴标签
    """
    from PIL import Image, ImageDraw, ImageFont
    temp_img = Image.fromarray(img_array)
    draw = ImageDraw.Draw(temp_img)

    try:
        font = ImageFont.truetype("arial.ttf", 10)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # 添加"时间轴"标签
    label = "Timeline (Frame Index)"
    # 兼容不同版本的PIL
    try:
        text_width = draw.textlength(label, font=font)
    except AttributeError:
        bbox = draw.textbbox((0, 0), label, font=font)
        text_width = bbox[2] - bbox[0]

    x = margin_left + (temp_img.width - 2 * margin_left - text_width) // 2
    y = axis_y + 15

    draw.text((x, y), label, fill=(50, 50, 50), font=font)

    # 写回数组
    img_array[:] = np.array(temp_img)


def _draw_peak_region(
    img_array: np.ndarray,
    start_frame: int,
    end_frame: int,
    total_points: int,
    img_width: int,
    img_height: int,
    margin_top: int,
    margin_bottom: int,
    color: Tuple[int, int, int],
    label: str
) -> None:
    """
    绘制单个波峰区域的标注

    Args:
        img_array: 图像numpy数组
        start_frame: 波峰开始帧
        end_frame: 波峰结束帧
        total_points: 总帧数
        img_width: 图像宽度
        img_height: 图像高度
        margin_top: 顶部边距
        margin_bottom: 底部边距
        color: 标注颜色
        label: 标签文本
    """
    # 计算像素坐标
    x1 = int((start_frame / (total_points - 1)) * (img_width - 1))
    x2 = int((end_frame / (total_points - 1)) * (img_width - 1))

    # 绘制垂直线标注波峰范围
    y_start = margin_top
    y_end = img_height - margin_bottom

    # 绘制半透明填充区域
    for x in range(max(0, x1), min(img_width, x2 + 1)):
        for y in range(y_start, y_end):
            if 0 <= x < img_width and 0 <= y < img_height:
                # 混合颜色
                current_pixel = img_array[y, x].copy()
                img_array[y, x] = _blend_colors(current_pixel, color + (50,))  # 半透明

    # 绘制边界线
    if x1 >= 0 and x1 < img_width:
        for y in range(y_start, y_end):
            img_array[y, x1] = color

    if x2 >= 0 and x2 < img_width:
        for y in range(y_start, y_end):
            img_array[y, x2] = color

    # 在顶部添加标签
    center_x = (x1 + x2) // 2
    if 0 <= center_x < img_width:
        # 使用PIL绘制文字
        from PIL import Image, ImageDraw, ImageFont
        temp_img = Image.fromarray(img_array)
        draw = ImageDraw.Draw(temp_img)

        try:
            font = ImageFont.truetype("arial.ttf", 10)
        except (OSError, IOError):
            font = ImageFont.load_default()

        text = f"{label}[{start_frame}-{end_frame}]"
        # 兼容不同版本的PIL
        try:
            text_width = draw.textlength(text, font=font)
        except AttributeError:
            # 旧版本PIL没有textlength方法
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]

        if center_x - text_width // 2 >= 0 and center_x + text_width // 2 < img_width:
            draw.text((center_x - text_width // 2, margin_top - 12), text, fill=color, font=font)

        # 将结果写回数组
        img_array[:] = np.array(temp_img)


def _draw_line(img_array: np.ndarray, x1: int, y1: int, x2: int, y2: int, color: Tuple[int, int, int], width: int = 1) -> None:
    """
    在图像数组上绘制线条

    Args:
        img_array: 图像numpy数组
        x1, y1: 起点坐标
        x2, y2: 终点坐标
        color: 线条颜色
        width: 线条宽度
    """
    height, img_width = img_array.shape[:2]

    # 简单的Bresenham算法
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx - dy

    while True:
        if 0 <= x1 < img_width and 0 <= y1 < height:
            # 绘制具有一定宽度的线条
            for i in range(-width // 2, width // 2 + 1):
                for j in range(-width // 2, width // 2 + 1):
                    px, py = x1 + i, y1 + j
                    if 0 <= px < img_width and 0 <= py < height:
                        img_array[py, px] = color

        if x1 == x2 and y1 == y2:
            break

        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x1 += sx
        if e2 < dx:
            err += dx
            y1 += sy


def _blend_colors(
    color1: np.ndarray,
    color2: Tuple[int, int, int, int]
) -> np.ndarray:
    """
    混合两个颜色

    Args:
        color1: 原始颜色
        color2: 混合颜色 (包含alpha通道)

    Returns:
        混合后的颜色
    """
    alpha = color2[3] / 255.0
    result = color1[:3] * (1 - alpha) + np.array(color2[:3]) * alpha
    return np.clip(result, 0, 255).astype(np.uint8)


def _add_enhanced_waveform_legend(
    image: Image.Image,
    green_peaks: List[Tuple[int, int]],
    red_peaks: List[Tuple[int, int]],
    img_width: int,
    img_height: int
) -> None:
    """
    添加增强版波形图图例，包含标记说明

    Args:
        image: PIL图像对象
        green_peaks: 绿色波峰列表
        red_peaks: 红色波峰列表
        img_width: 图像宽度
        img_height: 图像高度
    """
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # 在右上角添加图例
    x_start = img_width - 180
    y_start = 10

    # 背景框
    draw.rectangle([x_start - 5, y_start - 5, x_start + 175, y_start + 75], fill=(255, 255, 255, 240), outline=(0, 0, 0))

    # 标题
    draw.text((x_start, y_start), "Peak Markers:", fill=(0, 0, 0), font=font)

    # 波形图上的标记
    y_offset = 20
    _draw_circle_legend(draw, x_start + 10, y_start + y_offset + 5, 4, (0, 200, 0))  # 绿色圆点
    draw.text((x_start + 20, y_start + y_offset), "Green Circle: Peak on waveform", fill=(0, 0, 0), font=font)

    y_offset += 20
    _draw_circle_legend(draw, x_start + 10, y_start + y_offset + 5, 4, (200, 0, 0))  # 红色圆点
    draw.text((x_start + 20, y_start + y_offset), "Red Circle: Peak on waveform", fill=(0, 0, 0), font=font)

    # 时间轴上的标记
    y_offset += 20
    _draw_diamond_legend(draw, x_start + 10, y_start + y_offset + 5, 4, (0, 200, 0))  # 绿色菱形
    draw.text((x_start + 20, y_start + y_offset), "Green Diamond: Peak on timeline", fill=(0, 0, 0), font=font)

    # 统计信息
    y_offset += 25
    draw.text((x_start, y_start + y_offset), f"Total: {len(green_peaks) + len(red_peaks)} peaks", fill=(0, 0, 0), font=font)


def _draw_circle_legend(draw, cx: int, cy: int, radius: int, color: Tuple[int, int, int]) -> None:
    """为图例绘制小圆点"""
    for x in range(cx - radius, cx + radius + 1):
        for y in range(cy - radius, cy + radius + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                draw.point((x, y), fill=color)


def _draw_diamond_legend(draw, cx: int, cy: int, size: int, color: Tuple[int, int, int]) -> None:
    """为图例绘制小菱形"""
    points = [
        (cx, cy - size),
        (cx + size, cy),
        (cx, cy + size),
        (cx - size, cy),
    ]
    draw.polygon(points, fill=color)


def _draw_colored_waveform_curve(
    img_array: np.ndarray,
    points: List[Tuple[int, int]],
    green_peaks: List[Tuple[int, int]],
    red_peaks: List[Tuple[int, int]]
) -> None:
    """
    绘制彩色波形曲线，在波峰段使用不同颜色

    Args:
        img_array: 图像numpy数组
        points: 波形点坐标列表
        green_peaks: 绿色波峰列表
        red_peaks: 红色波峰列表
    """
    print(f"DEBUG: Drawing colored waveform curve with {len(green_peaks)} green and {len(red_peaks)} red peaks")

    # 创建波峰标记数组
    peak_segments = []  # 0=正常, 1=绿色波峰, 2=红色波峰
    for i in range(len(points)):
        peak_segments.append(0)

    # 标记绿色波峰段
    for start, end in green_peaks:
        for i in range(start, min(end + 1, len(points))):
            peak_segments[i] = 1

    # 标记红色波峰段
    for start, end in red_peaks:
        for i in range(start, min(end + 1, len(points))):
            peak_segments[i] = 2

    # 绘制分段着色的波形曲线
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]

        segment_type = peak_segments[i]  # 当前段的类型
        next_type = peak_segments[i + 1]  # 下一段的类型

        # 如果当前段和下一段类型相同，或者这是最后一段，正常绘制
        if segment_type == next_type or i == len(points) - 2:
            color = _get_segment_color(segment_type)
            thickness = _get_line_thickness(segment_type)
            _draw_line(img_array, x1, y1, x2, y2, color, thickness)
        else:
            # 如果段类型变化，在变化点处绘制渐变
            _draw_gradient_line(img_array, x1, y1, x2, y2, segment_type, next_type)

    print(f"DEBUG: Drew colored waveform with {peak_segments.count(1)} green segments and {peak_segments.count(2)} red segments")


def _get_segment_color(segment_type: int) -> Tuple[int, int, int]:
    """
    根据段类型返回颜色
    """
    if segment_type == 1:  # 绿色波峰
        return (0, 150, 0)  # 绿色
    elif segment_type == 2:  # 红色波峰
        return (200, 50, 50)  # 红色
    else:  # 正常段
        return (0, 50, 150)  # 深蓝色


def _get_line_thickness(segment_type: int) -> int:
    """
    根据段类型返回线条粗细
    """
    if segment_type == 0:  # 正常段
        return 2
    else:  # 波峰段 - 更粗更明显
        return 4


def _draw_gradient_line(
    img_array: np.ndarray,
    x1: int, y1: int, x2: int, y2: int,
    start_type: int, end_type: int
) -> None:
    """
    绘制渐变线条（用于段过渡）
    """
    # 计算线条长度
    dx = x2 - x1
    dy = y2 - y1
    length = int(np.sqrt(dx*dx + dy*dy))

    if length == 0:
        return

    start_color = _get_segment_color(start_type)
    end_color = _get_segment_color(end_type)

    # 沿线段绘制渐变
    for i in range(length):
        t = i / length
        # 线性插值颜色
        r = int(start_color[0] * (1 - t) + end_color[0] * t)
        g = int(start_color[1] * (1 - t) + end_color[1] * t)
        b = int(start_color[2] * (1 - t) + end_color[2] * t)

        # 计算当前点位置
        px = x1 + int(dx * i / length)
        py = y1 + int(dy * i / length)

        # 绘制稍粗的线条以确保可见性
        thickness = 3
        for dx in range(-thickness//2, thickness//2 + 1):
            for dy in range(-thickness//2, thickness//2 + 1):
                if 0 <= px + dx < img_array.shape[1] and 0 <= py + dy < img_array.shape[0]:
                    img_array[py + dy, px + dx] = (r, g, b)


def _image_to_base64(image: Image.Image) -> str:
    """
    将PIL图像转换为base64字符串

    Args:
        image: PIL图像对象

    Returns:
        base64编码的图片字符串
    """
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{img_base64}"