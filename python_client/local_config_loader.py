#!/usr/bin/env python3
"""
本地配置加载器
用于从本地fem_config.json文件加载配置参数
"""

import json
import os
import logging
from typing import Dict, Any, Optional, Tuple


class LocalConfigLoader:
    """本地配置文件加载器"""

    def __init__(self, config_file_path: Optional[str] = None):
        """
        初始化本地配置加载器

        Args:
            config_file_path: 配置文件路径，如果为None则自动检测
        """
        self.config_file_path = config_file_path
        self.config_data = None
        self.logger = logging.getLogger(__name__)

        # 设置默认配置文件路径
        if not config_file_path:
            self.config_file_path = self._detect_config_path()

    def _detect_config_path(self) -> str:
        """
        自动检测配置文件路径

        Returns:
            str: 检测到的配置文件路径
        """
        # 尝试多个可能的路径
        possible_paths = [
            # 相对于python_client目录
            os.path.join("..", "backends", "app", "fem_config.json"),
            os.path.join("..", "..", "backends", "app", "fem_config.json"),
            # 绝对路径
            "D:\\ProjectPackage\\NewFEM\\backends\\app\\fem_config.json",
            "D:/ProjectPackage/NewFEM/backends/app/fem_config.json",
            # 相对于项目根目录
            "backends/app/fem_config.json",
            "./backends/app/fem_config.json",
            # 当前目录
            "fem_config.json",
            "./fem_config.json"
        ]

        for path in possible_paths:
            if os.path.exists(path):
                self.logger.info(f"找到配置文件: {path}")
                return os.path.abspath(path)

        # 如果没有找到，返回默认路径
        default_path = possible_paths[0]
        self.logger.warning(f"未找到配置文件，使用默认路径: {default_path}")
        return os.path.abspath(default_path)

    def load_config(self) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        加载配置文件

        Returns:
            Tuple[bool, str, Optional[Dict]]:
                (是否成功, 状态消息, 配置数据)
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(self.config_file_path):
                error_msg = f"配置文件不存在: {self.config_file_path}"
                self.logger.error(error_msg)
                return False, error_msg, None

            # 读取配置文件
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)

            # 验证配置文件结构
            if not self._validate_config():
                error_msg = "配置文件格式不正确"
                self.logger.error(error_msg)
                return False, error_msg, None

            success_msg = f"成功加载配置文件: {self.config_file_path}"
            self.logger.info(success_msg)
            return True, success_msg, self.config_data

        except json.JSONDecodeError as e:
            error_msg = f"JSON解析错误: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg, None

        except FileNotFoundError as e:
            error_msg = f"文件未找到: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg, None

        except PermissionError as e:
            error_msg = f"文件权限错误: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg, None

        except Exception as e:
            error_msg = f"加载配置时发生未知错误: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg, None

    def _validate_config(self) -> bool:
        """
        验证配置文件结构

        Returns:
            bool: 配置是否有效
        """
        if not self.config_data:
            return False

        required_sections = ["roi_capture", "peak_detection"]

        for section in required_sections:
            if section not in self.config_data:
                self.logger.warning(f"缺少配置节: {section}")
                # 不返回False，允许部分配置缺失

        # 验证ROI配置结构
        if "roi_capture" in self.config_data:
            roi_config = self.config_data["roi_capture"]
            if "default_config" not in roi_config:
                self.logger.warning("ROI配置中缺少default_config")

        return True

    def get_roi_config(self) -> Dict[str, Any]:
        """
        获取ROI配置

        Returns:
            Dict: ROI配置数据
        """
        if not self.config_data:
            return {}

        roi_config = self.config_data.get("roi_capture", {})
        default_config = roi_config.get("default_config", {})

        # 返回默认配置和其他ROI参数
        result = default_config.copy()
        result.update({
            "frame_rate": roi_config.get("frame_rate", 5.0),
            "update_interval": roi_config.get("update_interval", 0.5)
        })

        return result

    def get_peak_detection_config(self) -> Dict[str, Any]:
        """
        获取波峰检测配置

        Returns:
            Dict: 波峰检测配置数据
        """
        if not self.config_data:
            return {}

        return self.config_data.get("peak_detection", {})

    def get_server_config(self) -> Dict[str, Any]:
        """
        获取服务器配置

        Returns:
            Dict: 服务器配置数据
        """
        if not self.config_data:
            return {}

        return self.config_data.get("server", {})

    def get_full_config(self) -> Dict[str, Any]:
        """
        获取完整配置数据

        Returns:
            Dict: 完整配置数据
        """
        return self.config_data or {}

    def get_config_path(self) -> str:
        """
        获取当前配置文件路径

        Returns:
            str: 配置文件路径
        """
        return self.config_file_path

    def set_config_path(self, path: str) -> Tuple[bool, str]:
        """
        设置配置文件路径

        Args:
            path: 新的配置文件路径

        Returns:
            Tuple[bool, str]: (是否成功, 状态消息)
        """
        if not os.path.exists(path):
            return False, f"指定的文件不存在: {path}"

        self.config_file_path = os.path.abspath(path)
        self.config_data = None  # 重置配置数据，强制重新加载

        return True, f"配置文件路径已更新为: {self.config_file_path}"

    def reload_config(self) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        重新加载配置文件

        Returns:
            Tuple[bool, str, Optional[Dict]]:
                (是否成功, 状态消息, 配置数据)
        """
        self.config_data = None  # 重置配置数据
        return self.load_config()


# 便捷函数
def load_local_config(config_path: Optional[str] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    便捷函数：加载本地配置

    Args:
        config_path: 配置文件路径

    Returns:
        Tuple[bool, str, Optional[Dict]]:
            (是否成功, 状态消息, 配置数据)
    """
    loader = LocalConfigLoader(config_path)
    return loader.load_config()


def get_config_summary(config_path: Optional[str] = None) -> str:
    """
    获取配置摘要信息

    Args:
        config_path: 配置文件路径

    Returns:
        str: 配置摘要
    """
    success, message, config_data = load_local_config(config_path)

    if not success:
        return f"配置加载失败: {message}"

    if not config_data:
        return "配置数据为空"

    # 提取关键配置信息
    summary_lines = ["配置摘要信息:"]

    # ROI配置
    roi_config = config_data.get("roi_capture", {})
    if "default_config" in roi_config:
        roi_default = roi_config["default_config"]
        summary_lines.append(f"  ROI区域: ({roi_default.get('x1', 0)}, {roi_default.get('y1', 0)}) -> ({roi_default.get('x2', 200)}, {roi_default.get('y2', 150)})")
        summary_lines.append(f"  ROI帧率: {roi_config.get('frame_rate', 'N/A')} FPS")

    # 波峰检测配置
    peak_config = config_data.get("peak_detection", {})
    summary_lines.append(f"  波峰阈值: {peak_config.get('threshold', 'N/A')}")
    summary_lines.append(f"  边界帧数: {peak_config.get('margin_frames', 'N/A')}")

    # 服务器配置
    server_config = config_data.get("server", {})
    summary_lines.append(f"  服务器端口: {server_config.get('api_port', 'N/A')}")

    return "\n".join(summary_lines)


if __name__ == "__main__":
    # 测试代码
    print("测试本地配置加载器...")

    # 测试加载配置
    success, message, config_data = load_local_config()
    print(f"加载结果: {success}")
    print(f"消息: {message}")

    if success:
        print("\n配置摘要:")
        print(get_config_summary())

        loader = LocalConfigLoader()
        print(f"\n配置文件路径: {loader.get_config_path()}")
        print(f"ROI配置: {loader.get_roi_config()}")
        print(f"波峰检测配置: {loader.get_peak_detection_config()}")