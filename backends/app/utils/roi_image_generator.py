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
    width: int = 400,
    height: int = 200
) -> str:
    """
    生成带有波峰标注的波形图像

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
        img_array = np.zeros((height, width), dtype=np.uint8)
        image = Image.fromarray(img_array, mode='L')

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

    # 创建RGB图像（支持彩色标注）
    img_array = np.ones((height, width, 3), dtype=np.uint8) * 240  # 浅灰色背景

    # 绘制波形曲线
    _draw_waveform_curve(img_array, curve_data)

    # 添加波峰标注
    _draw_peak_annotations(img_array, green_peaks, red_peaks, len(curve_data), width, height)

    # 转换为PIL图像
    image = Image.fromarray(img_array, mode='RGB')

    # 添加图例和标签
    _add_waveform_legend(image, green_peaks, red_peaks)

    return _image_to_base64(image)


def _draw_waveform_curve(img_array: np.ndarray, curve_data: List[float]) -> None:
    """
    在图像数组上绘制波形曲线

    Args:
        img_array: 图像numpy数组 (height, width, 3)
        curve_data: 波形数据
    """
    height, width = img_array.shape[:2]
    num_points = len(curve_data)

    if num_points < 2:
        return

    # 计算数据范围
    min_val = min(curve_data)
    max_val = max(curve_data)
    range_val = max_val - min_val

    if range_val == 0:
        range_val = 1

    # 计算点的坐标
    points = []
    for i, value in enumerate(curve_data):
        x = int((i / (num_points - 1)) * (width - 1))
        y = int(height - 20 - ((value - min_val) / range_val) * (height - 40))
        points.append((x, y))

    # 绘制曲线（深蓝色）
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        _draw_line(img_array, x1, y1, x2, y2, (0, 0, 139), 2)  # 深蓝色


def _draw_peak_annotations(
    img_array: np.ndarray,
    green_peaks: List[Tuple[int, int]],
    red_peaks: List[Tuple[int, int]],
    total_points: int,
    img_width: int,
    img_height: int
) -> None:
    """
    在波形图上绘制波峰标注

    Args:
        img_array: 图像numpy数组
        green_peaks: 绿色波峰列表
        red_peaks: 红色波峰列表
        total_points: 波形总点数
        img_width: 图像宽度
        img_height: 图像高度
    """
    height = img_array.shape[0]
    margin_top = 20
    margin_bottom = 40

    # 绘制绿色波峰标注
    for start, end in green_peaks:
        _draw_peak_region(img_array, start, end, total_points, img_width, height, margin_top, margin_bottom, (0, 255, 0), "Green")

    # 绘制红色波峰标注
    for start, end in red_peaks:
        _draw_peak_region(img_array, start, end, total_points, img_width, height, margin_top, margin_bottom, (255, 0, 0), "Red")


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


def _add_waveform_legend(
    image: Image.Image,
    green_peaks: List[Tuple[int, int]],
    red_peaks: List[Tuple[int, int]]
) -> None:
    """
    添加波形图图例

    Args:
        image: PIL图像对象
        green_peaks: 绿色波峰列表
        red_peaks: 红色波峰列表
    """
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # 在右上角添加图例
    x_start = image.width - 150
    y_start = 10

    # 背景框
    draw.rectangle([x_start - 5, y_start - 5, x_start + 145, y_start + 45], fill=(255, 255, 255, 200), outline=(0, 0, 0))

    # 绿色波峰图例
    draw.rectangle([x_start, y_start, x_start + 15, y_start + 10], fill=(0, 255, 0))
    draw.text((x_start + 20, y_start), f"Green Peaks: {len(green_peaks)}", fill=(0, 0, 0), font=font)

    # 红色波峰图例
    draw.rectangle([x_start, y_start + 20, x_start + 15, y_start + 30], fill=(255, 0, 0))
    draw.text((x_start + 20, y_start + 20), f"Red Peaks: {len(red_peaks)}", fill=(0, 0, 0), font=font)


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