"""
ROI图片生成工具模块

为ROI监控生成基于信号值的模拟灰度图片
"""

from __future__ import annotations

import io
import base64
from typing import Tuple

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