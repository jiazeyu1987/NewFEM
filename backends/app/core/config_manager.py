"""
JSON配置管理器
负责处理配置文件的读取、写入、验证和重新加载
"""

import json
import threading
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from copy import deepcopy
import traceback

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器类 - 线程安全的JSON配置管理"""

    def __init__(self, config_file_path: Union[str, Path]):
        """
        初始化配置管理器

        Args:
            config_file_path: JSON配置文件路径
        """
        self.config_file_path = Path(config_file_path)
        self._config: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._config_schema = self._get_config_schema()

        # 确保配置目录存在
        self.config_file_path.parent.mkdir(parents=True, exist_ok=True)

        # 加载配置
        self.load_config()

    def _get_config_schema(self) -> Dict[str, Any]:
        """获取配置文件的JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "server": {
                    "type": "object",
                    "properties": {
                        "host": {"type": "string", "default": "0.0.0.0"},
                        "api_port": {"type": "integer", "minimum": 1, "maximum": 65535, "default": 8421},
                        "socket_port": {"type": "integer", "minimum": 1, "maximum": 65535, "default": 30415},
                        "max_clients": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
                        "enable_cors": {"type": "boolean", "default": True},
                        "allowed_origins": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": ["*"]
                        }
                    }
                },
                "data_processing": {
                    "type": "object",
                    "properties": {
                        "fps": {"type": "integer", "minimum": 1, "maximum": 120, "default": 60},
                        "buffer_size": {"type": "integer", "minimum": 10, "maximum": 1000, "default": 100},
                        "max_frame_count": {"type": "integer", "minimum": 100, "maximum": 100000, "default": 10000}
                    }
                },
                "roi_capture": {
                    "type": "object",
                    "properties": {
                        "frame_rate": {"type": "number", "minimum": 0.1, "maximum": 30.0, "default": 2},
                        "update_interval": {"type": "number", "minimum": 0.1, "maximum": 10.0, "default": 0.5},
                        "default_config": {
                            "type": "object",
                            "properties": {
                                "x1": {"type": "integer", "minimum": 0, "default": 0},
                                "y1": {"type": "integer", "minimum": 0, "default": 0},
                                "x2": {"type": "integer", "minimum": 1, "default": 200},
                                "y2": {"type": "integer", "minimum": 1, "default": 150}
                            }
                        }
                    }
                },
                "peak_detection": {
                    "type": "object",
                    "properties": {
                        "threshold": {"type": "number", "minimum": 0, "maximum": 255, "default": 105.0},
                        "margin_frames": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                        "difference_threshold": {"type": "number", "minimum": 0, "maximum": 10.0, "default": 2.1},
                        "min_region_length": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3}
                    }
                },
                "security": {
                    "type": "object",
                    "properties": {
                        "password": {"type": "string", "default": "31415"}
                    }
                },
                "logging": {
                    "type": "object",
                    "properties": {
                        "level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], "default": "INFO"}
                    }
                }
            }
        }

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        schema = self._config_schema
        default_config = {}

        def get_default_from_schema(schema_part):
            if isinstance(schema_part, dict):
                if "default" in schema_part:
                    return schema_part["default"]
                elif "properties" in schema_part:
                    result = {}
                    for key, value in schema_part["properties"].items():
                        result[key] = get_default_from_schema(value)
                    return result
                elif "items" in schema_part:
                    return []
            return None

        return get_default_from_schema(schema) or {}

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置是否符合Schema"""
        try:
            self._validate_recursive(config, self._config_schema)
            return True
        except Exception as e:
            logger.error(f"配置验证失败: {e}")
            return False

    def _validate_recursive(self, data: Any, schema: Dict[str, Any], path: str = "") -> None:
        """递归验证配置"""
        if "type" in schema:
            expected_type = schema["type"]

            if expected_type == "object" and isinstance(data, dict):
                if "properties" in schema:
                    for key, value in schema["properties"].items():
                        if key in data:
                            self._validate_recursive(data[key], value, f"{path}.{key}" if path else key)
                        elif "default" in value:
                            # 可选字段，使用默认值
                            pass
                        else:
                            raise ValueError(f"缺少必需字段: {path}.{key}" if path else key)

            elif expected_type == "array" and isinstance(data, list):
                if "items" in schema:
                    for i, item in enumerate(data):
                        self._validate_recursive(item, schema["items"], f"{path}[{i}]")

            elif expected_type == "string" and not isinstance(data, str):
                raise ValueError(f"{path} 应为字符串，实际为 {type(data).__name__}")

            elif expected_type == "integer" and not isinstance(data, int):
                raise ValueError(f"{path} 应为整数，实际为 {type(data).__name__}")

            elif expected_type == "number" and not isinstance(data, (int, float)):
                raise ValueError(f"{path} 应为数字，实际为 {type(data).__name__}")

            elif expected_type == "boolean" and not isinstance(data, bool):
                raise ValueError(f"{path} 应为布尔值，实际为 {type(data).__name__}")

        # 检查数值范围
        if isinstance(data, (int, float)):
            if "minimum" in schema and data < schema["minimum"]:
                raise ValueError(f"{path} 值 {data} 小于最小值 {schema['minimum']}")
            if "maximum" in schema and data > schema["maximum"]:
                raise ValueError(f"{path} 值 {data} 大于最大值 {schema['maximum']}")

        # 检查枚举值
        if "enum" in schema and data not in schema["enum"]:
            raise ValueError(f"{path} 值 {data} 不在允许的枚举值中: {schema['enum']}")

    def load_config(self) -> bool:
        """
        从文件加载配置

        Returns:
            bool: 加载是否成功
        """
        with self._lock:
            try:
                if self.config_file_path.exists():
                    logger.info(f"正在加载配置文件: {self.config_file_path}")
                    with open(self.config_file_path, 'r', encoding='utf-8') as f:
                        loaded_config = json.load(f)

                    if self._validate_config(loaded_config):
                        self._config = loaded_config
                        logger.info("配置文件加载并验证成功")
                        return True
                    else:
                        logger.warning("配置文件验证失败，使用默认配置")
                        self._config = self._get_default_config()
                        return False
                else:
                    logger.info(f"配置文件不存在，创建默认配置: {self.config_file_path}")
                    self._config = self._get_default_config()
                    self.save_config()
                    return True

            except json.JSONDecodeError as e:
                logger.error(f"配置文件JSON格式错误: {e}")
                # 备份损坏的配置文件
                if self.config_file_path.exists():
                    backup_path = self.config_file_path.with_suffix('.json.corrupted')
                    self.config_file_path.rename(backup_path)
                    logger.info(f"已将损坏的配置文件备份到: {backup_path}")

                self._config = self._get_default_config()
                self.save_config()
                return False

            except Exception as e:
                logger.error(f"加载配置文件时发生错误: {e}")
                logger.debug(f"详细错误信息: {traceback.format_exc()}")
                self._config = self._get_default_config()
                return False

    def save_config(self) -> bool:
        """
        保存配置到文件

        Returns:
            bool: 保存是否成功
        """
        with self._lock:
            try:
                # 验证配置
                if not self._validate_config(self._config):
                    logger.error("配置验证失败，拒绝保存")
                    return False

                # 原子写入：先写入临时文件，然后重命名
                temp_file = self.config_file_path.with_suffix('.json.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self._config, f, indent=2, ensure_ascii=False)

                # 原子重命名 (Windows兼容处理)
                if self.config_file_path.exists():
                    self.config_file_path.unlink()  # Windows下先删除现有文件
                temp_file.rename(self.config_file_path)
                logger.info(f"配置已保存到: {self.config_file_path}")
                return True

            except Exception as e:
                logger.error(f"保存配置文件时发生错误: {e}")
                logger.debug(f"详细错误信息: {traceback.format_exc()}")
                return False

    def get_config(self, section: Optional[str] = None, key: Optional[str] = None) -> Any:
        """
        获取配置值

        Args:
            section: 配置节名称，如 'server', 'roi_capture' 等
            key: 配置键名称

        Returns:
            配置值
        """
        with self._lock:
            config_copy = deepcopy(self._config)

            if section is None:
                return config_copy

            if section not in config_copy:
                logger.warning(f"配置节不存在: {section}")
                return None

            section_config = config_copy[section]

            if key is None:
                return section_config

            if key not in section_config:
                logger.warning(f"配置键不存在: {section}.{key}")
                return None

            return section_config[key]

    def set_config(self, value: Any, section: Optional[str] = None, key: Optional[str] = None) -> bool:
        """
        设置配置值

        Args:
            value: 要设置的值
            section: 配置节名称
            key: 配置键名称

        Returns:
            bool: 设置是否成功
        """
        with self._lock:
            try:
                if section is None:
                    # 设置整个配置
                    if isinstance(value, dict):
                        self._config = deepcopy(value)
                    else:
                        logger.error("设置整个配置时，值必须为字典类型")
                        return False
                elif key is None:
                    # 设置整个配置节
                    if isinstance(value, dict):
                        self._config[section] = deepcopy(value)
                    else:
                        logger.error("设置配置节时，值必须为字典类型")
                        return False
                else:
                    # 设置特定配置键
                    if section not in self._config:
                        self._config[section] = {}

                    self._config[section][key] = value

                return True

            except Exception as e:
                logger.error(f"设置配置时发生错误: {e}")
                return False

    def update_config(self, updates: Dict[str, Any], section: Optional[str] = None) -> bool:
        """
        批量更新配置

        Args:
            updates: 要更新的配置字典
            section: 配置节名称（可选）

        Returns:
            bool: 更新是否成功
        """
        with self._lock:
            try:
                if section is None:
                    # 更新多个配置节
                    for sec_key, sec_value in updates.items():
                        if isinstance(sec_value, dict):
                            if sec_key not in self._config:
                                self._config[sec_key] = {}
                            self._config[sec_key].update(sec_value)
                        else:
                            logger.warning(f"跳过非字典类型的配置节: {sec_key}")
                else:
                    # 更新单个配置节
                    if section not in self._config:
                        self._config[section] = {}

                    if isinstance(updates, dict):
                        self._config[section].update(updates)
                    else:
                        logger.error("更新配置时，值必须为字典类型")
                        return False

                return True

            except Exception as e:
                logger.error(f"更新配置时发生错误: {e}")
                return False

    def reload_config(self) -> bool:
        """
        重新加载配置文件

        Returns:
            bool: 重新加载是否成功
        """
        logger.info("正在重新加载配置文件...")
        return self.load_config()

    def get_full_config(self) -> Dict[str, Any]:
        """
        获取完整配置的深拷贝

        Returns:
            完整配置字典
        """
        return self.get_config()

    def export_config(self) -> str:
        """
        导出配置为JSON字符串

        Returns:
            JSON格式的配置字符串
        """
        with self._lock:
            return json.dumps(self._config, indent=2, ensure_ascii=False)

    def import_config(self, config_json: str) -> bool:
        """
        从JSON字符串导入配置

        Args:
            config_json: JSON格式的配置字符串

        Returns:
            bool: 导入是否成功
        """
        try:
            config_data = json.loads(config_json)
            if self._validate_config(config_data):
                self._config = config_data
                return self.save_config()
            else:
                logger.error("导入的配置验证失败")
                return False

        except json.JSONDecodeError as e:
            logger.error(f"导入配置时JSON解析错误: {e}")
            return False
        except Exception as e:
            logger.error(f"导入配置时发生错误: {e}")
            return False


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        # 默认配置文件路径
        config_path = Path(__file__).parent.parent / "fem_config.json"
        _config_manager = ConfigManager(config_path)
    return _config_manager


def init_config_manager(config_file_path: Union[str, Path]) -> ConfigManager:
    """
    初始化全局配置管理器

    Args:
        config_file_path: 配置文件路径

    Returns:
        配置管理器实例
    """
    global _config_manager
    _config_manager = ConfigManager(config_file_path)
    return _config_manager