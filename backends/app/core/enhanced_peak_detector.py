"""
增强型波峰检测器
实现基于三参数的医疗级波峰检测算法
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime

from ..models import TimeSeriesPoint


@dataclass
class PeakRegion:
    """波峰区域数据结构"""
    start_frame: int
    end_frame: int
    peak_frame: int
    max_value: float
    color: str  # 'green' or 'red'
    confidence: float
    difference: float


@dataclass
class PeakDetectionConfig:
    """波峰检测配置"""
    threshold: float = 105.0           # 绝对阈值
    margin_frames: int = 5            # 边界扩展帧数
    difference_threshold: float = 2.1  # 颜色分类阈值
    min_region_length: int = 3        # 最小波峰区域长度

    # 滑动窗口检测参数
    window_size: int = 100           # 滑动窗口大小
    slope_threshold: float = 0.5     # 坡度阈值
    min_slope_frames: int = 3        # 最小坡度帧数
    fall_threshold: float = 100.0    # 下降阈值

    # 动态阈值系统参数
    adaptive_threshold: bool = True     # 启用自适应阈值
    baseline_window: int = 50          # 基线计算窗口大小
    baseline_multiplier: float = 1.2   # 基线倍数阈值
    min_dynamic_threshold: float = 80.0 # 最小动态阈值
    max_dynamic_threshold: float = 150.0 # 最大动态阈值
    noise_tolerance: float = 0.1       # 噪声容忍度
    trend_compensation: bool = True    # 趋势补偿


class EnhancedPeakDetector:
    """增强型波峰检测器"""

    def __init__(self, config: PeakDetectionConfig = None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._config = config or PeakDetectionConfig()
        self._frame_buffer: List[float] = []
        self._peak_regions: List[PeakRegion] = []
        self._current_region: Optional[Tuple[int, int]] = None  # (start_frame, end_frame)

    def update_config(self, config: PeakDetectionConfig) -> None:
        """更新波峰检测配置"""
        self._config = config
        self._logger.info(f"Peak detection config updated: threshold={config.threshold}, "
                         f"margin_frames={config.margin_frames}, "
                         f"difference_threshold={config.difference_threshold}")

    def _calculate_slope(self, frame_data: List[float], index: int, method: str = "central_3point") -> float:
        """
        计算指定帧的坡度 - 支持多种计算方法

        Args:
            frame_data: 帧数据列表
            index: 要计算坡度的帧索引
            method: 坡度计算方法
                - "central_3point": 3点中心差分法 (默认)
                - "central_5point": 5点中心差分法
                - "forward_2point": 前向2点差分法
                - "backward_2point": 后向2点差分法
                - "adaptive": 自适应选择最佳方法

        Returns:
            float: 坡度值
        """
        n = len(frame_data)
        if index < 0 or index >= n:
            return 0.0

        if method == "adaptive":
            # 自适应选择坡度计算方法
            if index >= 2 and index < n - 2:
                method = "central_5point"  # 中心位置使用5点法
            elif index >= 1 and index < n - 1:
                method = "central_3point"  # 边缘位置使用3点法
            elif index < n - 1:
                method = "forward_2point"  # 开始位置使用前向差分
            else:
                method = "backward_2point"  # 结束位置使用后向差分

        try:
            if method == "central_3point":
                # 3点中心差分法: slope = (f[i+1] - f[i-1]) / 2
                if index < 1 or index >= n - 1:
                    return 0.0
                return (frame_data[index + 1] - frame_data[index - 1]) / 2.0

            elif method == "central_5point":
                # 5点中心差分法: slope = (-f[i+2] + 8f[i+1] - 8f[i-1] + f[i-2]) / 12
                if index < 2 or index >= n - 2:
                    return self._calculate_slope(frame_data, index, "central_3point")
                return (-frame_data[index + 2] + 8 * frame_data[index + 1] -
                       8 * frame_data[index - 1] + frame_data[index - 2]) / 12.0

            elif method == "forward_2point":
                # 前向2点差分法: slope = f[i+1] - f[i]
                if index >= n - 1:
                    return 0.0
                return frame_data[index + 1] - frame_data[index]

            elif method == "backward_2point":
                # 后向2点差分法: slope = f[i] - f[i-1]
                if index < 1:
                    return 0.0
                return frame_data[index] - frame_data[index - 1]

            else:
                # 默认使用3点中心差分
                return self._calculate_slope(frame_data, index, "central_3point")

        except (IndexError, ZeroDivisionError) as e:
            self._logger.warning(f"Slope calculation error at index {index}: {e}")
            return 0.0

    def _calculate_smoothed_slope(self, frame_data: List[float], index: int, window_size: int = 3) -> float:
        """
        计算平滑后的坡度 - 使用移动平均减少噪声影响

        Args:
            frame_data: 帧数据列表
            index: 要计算坡度的帧索引
            window_size: 平滑窗口大小

        Returns:
            float: 平滑后的坡度值
        """
        if index < 0 or index >= len(frame_data):
            return 0.0

        # 计算窗口内所有点的坡度
        slopes = []
        for i in range(max(0, index - window_size // 2), min(len(frame_data), index + window_size // 2 + 1)):
            if i != index:
                slope = self._calculate_slope(frame_data, i, "central_3point")
                slopes.append(slope)

        if not slopes:
            return 0.0

        # 使用加权平均，中心点权重更高
        weighted_sum = 0.0
        total_weight = 0.0
        center = len(slopes) / 2.0

        for i, slope in enumerate(slopes):
            weight = 1.0 - abs(i - center) / (center + 1.0)  # 距离中心越远权重越小
            weighted_sum += slope * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _calculate_robust_slope(self, frame_data: List[float], index: int) -> float:
        """
        计算鲁棒性坡度 - 使用中位数滤波减少异常值影响

        Args:
            frame_data: 帧数据列表
            index: 要计算坡度的帧索引

        Returns:
            float: 鲁棒性坡度值
        """
        slopes = []

        # 收集多个坡度估计
        if index >= 1 and index < len(frame_data) - 1:
            slopes.append(self._calculate_slope(frame_data, index, "central_3point"))

        if index >= 2 and index < len(frame_data) - 2:
            slopes.append(self._calculate_slope(frame_data, index, "central_5point"))

        if index < len(frame_data) - 1:
            slopes.append(self._calculate_slope(frame_data, index, "forward_2point"))

        if index >= 1:
            slopes.append(self._calculate_slope(frame_data, index, "backward_2point"))

        if not slopes:
            return 0.0

        # 使用中位数作为鲁棒估计
        slopes.sort()
        median_slope = slopes[len(slopes) // 2]

        # 计算与中位数的绝对偏差中位数 (MAD)
        mad = sum(abs(s - median_slope) for s in slopes) / len(slopes)

        # 使用加权平均，权重基于与中位数的偏差
        weighted_sum = 0.0
        total_weight = 0.0
        for slope in slopes:
            weight = 1.0 / (1.0 + abs(slope - median_slope) / (mad + 1e-6))
            weighted_sum += slope * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else median_slope

    def _calculate_dynamic_threshold(self, frame_data: List[float], index: int = None) -> float:
        """
        计算动态阈值 - 基于历史基线和自适应调整

        Args:
            frame_data: 帧数据列表
            index: 当前帧索引（用于趋势补偿）

        Returns:
            float: 动态阈值
        """
        if not self._config.adaptive_threshold:
            return self._config.threshold

        if len(frame_data) < self._config.baseline_window:
            return self._config.threshold

        # 提取基线计算窗口数据
        if index is None:
            # 使用最近的窗口数据计算基线
            baseline_data = frame_data[-self._config.baseline_window:]
        else:
            # 使用指定帧周围的数据计算基线
            start_idx = max(0, index - self._config.baseline_window // 2)
            end_idx = min(len(frame_data), index + self._config.baseline_window // 2)
            baseline_data = frame_data[start_idx:end_idx]

        if not baseline_data:
            return self._config.threshold

        # 计算统计基线
        baseline_values = sorted(baseline_data)
        q1_index = len(baseline_values) // 4
        q3_index = 3 * len(baseline_values) // 4
        q1 = baseline_values[q1_index]
        q3 = baseline_values[q3_index]
        median = baseline_values[len(baseline_values) // 2]

        # 使用IQR方法计算稳健的基线和标准差
        iqr = q3 - q1
        baseline = median
        noise_std = iqr / 1.35  # IQR转换为标准差的近似

        # 趋势补偿
        trend_compensation = 0.0
        if self._config.trend_compensation and index is not None and len(frame_data) > 10:
            # 计算线性趋势
            recent_data = frame_data[-min(20, len(frame_data)):]
            if len(recent_data) >= 5:
                n = len(recent_data)
                x_sum = sum(range(n))
                y_sum = sum(recent_data)
                xy_sum = sum(i * recent_data[i] for i in range(n))
                x2_sum = sum(i * i for i in range(n))

                # 线性回归: y = ax + b
                denominator = n * x2_sum - x_sum * x_sum
                if denominator != 0:
                    slope = (n * xy_sum - x_sum * y_sum) / denominator
                    # 预测当前值的趋势
                    trend_compensation = slope * (n - 1)

        # 计算动态阈值
        # 基础阈值 = 基线 + 噪声容忍度 + 趋势补偿
        base_threshold = baseline + (noise_std * self._config.noise_tolerance) + trend_compensation

        # 应用倍数因子
        dynamic_threshold = base_threshold * self._config.baseline_multiplier

        # 限制在最小/最大阈值范围内
        dynamic_threshold = max(self._config.min_dynamic_threshold,
                               min(self._config.max_dynamic_threshold, dynamic_threshold))

        self._logger.debug(f"🎛️ [DYNAMIC THRESHOLD] baseline={baseline:.2f}, "
                         f"noise_std={noise_std:.2f}, trend={trend_compensation:.2f}, "
                         f"final_threshold={dynamic_threshold:.2f}")

        return dynamic_threshold

    def _get_adaptive_slope_threshold(self, frame_data: List[float]) -> float:
        """
        获取自适应坡度阈值 - 基于信号特性动态调整

        Args:
            frame_data: 帧数据列表

        Returns:
            float: 自适应坡度阈值
        """
        if len(frame_data) < 10:
            return self._config.slope_threshold

        # 计算最近的坡度变化
        recent_slopes = []
        for i in range(len(frame_data) - 10, len(frame_data) - 1):
            slope = self._calculate_slope(frame_data, i)
            recent_slopes.append(abs(slope))

        if not recent_slopes:
            return self._config.slope_threshold

        # 基于坡度分布的自适应调整
        avg_slope = sum(recent_slopes) / len(recent_slopes)
        slope_std = (sum((s - avg_slope) ** 2 for s in recent_slopes) / len(recent_slopes)) ** 0.5

        # 如果信号变化剧烈，降低坡度阈值；如果信号平稳，提高坡度阈值
        adaptive_factor = 1.0
        if slope_std > 2.0:  # 高波动信号
            adaptive_factor = 0.7  # 降低阈值
        elif slope_std < 0.5:  # 低波动信号
            adaptive_factor = 1.3  # 提高阈值

        adaptive_threshold = self._config.slope_threshold * adaptive_factor
        self._logger.debug(f"📐 [ADAPTIVE SLOPE] slope_std={slope_std:.3f}, "
                         f"adaptive_factor={adaptive_factor:.2f}, "
                         f"adaptive_threshold={adaptive_threshold:.3f}")

        return adaptive_threshold

    def _detect_rising_slope(self, frame_data: List[float]) -> Optional[int]:
        """
        检测窗口内的上升波形 - 使用增强的坡度检测算法

        Args:
            frame_data: 帧数据列表

        Returns:
            Optional[int]: 上升开始位置，未找到返回None
        """
        if len(frame_data) < self._config.min_slope_frames + 2:
            return None

        best_candidate = None
        best_score = 0.0

        # 计算动态阈值和自适应坡度阈值
        dynamic_threshold = self._calculate_dynamic_threshold(frame_data)
        adaptive_slope_threshold = self._get_adaptive_slope_threshold(frame_data)

        for i in range(len(frame_data) - self._config.min_slope_frames - 1):
            # 检查当前值是否超过动态阈值
            if frame_data[i] > dynamic_threshold:
                # 使用多种方法计算坡度并综合评分
                rising_count = 0
                total_slope = 0.0
                robust_slopes = []

                for j in range(i, min(i + self._config.min_slope_frames, len(frame_data))):
                    # 使用鲁棒坡度计算
                    robust_slope = self._calculate_robust_slope(frame_data, j)
                    adaptive_slope = self._calculate_slope(frame_data, j, "adaptive")
                    smoothed_slope = self._calculate_smoothed_slope(frame_data, j)

                    # 综合评分：结合多种方法的坡度估计
                    combined_slope = (robust_slope * 0.5 + adaptive_slope * 0.3 + smoothed_slope * 0.2)
                    robust_slopes.append(combined_slope)

                    if combined_slope > adaptive_slope_threshold:
                        rising_count += 1
                    total_slope += combined_slope

                # 计算候选得分：考虑连续上升帧数和总体坡度强度
                if rising_count >= self._config.min_slope_frames:
                    avg_slope = total_slope / len(robust_slopes)
                    consistency = 1.0 - (max(robust_slopes) - min(robust_slopes)) / (abs(avg_slope) + 1e-6)
                    score = rising_count * avg_slope * consistency

                    if score > best_score:
                        best_score = score
                        best_candidate = i

                    self._logger.debug(f"Rising slope candidate at frame {i}, "
                                     f"rising_count={rising_count}, avg_slope={avg_slope:.3f}, "
                                     f"score={score:.3f}")

        if best_candidate is not None:
            self._logger.debug(f"Best rising slope detected at frame {best_candidate}, score={best_score:.3f}")
            return best_candidate

        return None

    def _detect_falling_slope(self, frame_data: List[float]) -> Optional[int]:
        """
        检测窗口内的下降波形 - 使用增强的坡度检测算法

        Args:
            frame_data: 帧数据列表

        Returns:
            Optional[int]: 下降开始位置，未找到返回None
        """
        if len(frame_data) < self._config.min_slope_frames + 2:
            return None

        best_candidate = None
        best_score = 0.0

        # 计算自适应坡度阈值
        adaptive_slope_threshold = self._get_adaptive_slope_threshold(frame_data)

        # 从窗口后向前搜索下降波形
        for i in range(len(frame_data) - 1, self._config.min_slope_frames, -1):
            # 检查当前值是否低于下降阈值（使用动态下降阈值）
            dynamic_fall_threshold = self._calculate_dynamic_threshold(frame_data, i) * 0.9  # 下降阈值略低于上升阈值

            if frame_data[i] < dynamic_fall_threshold:
                # 使用多种方法计算坡度并综合评分
                falling_count = 0
                total_slope = 0.0
                robust_slopes = []

                for j in range(i, max(i - self._config.min_slope_frames, 0), -1):
                    # 使用鲁棒坡度计算
                    robust_slope = self._calculate_robust_slope(frame_data, j)
                    adaptive_slope = self._calculate_slope(frame_data, j, "adaptive")
                    smoothed_slope = self._calculate_smoothed_slope(frame_data, j)

                    # 综合评分：结合多种方法的坡度估计
                    combined_slope = (robust_slope * 0.5 + adaptive_slope * 0.3 + smoothed_slope * 0.2)
                    robust_slopes.append(combined_slope)

                    if combined_slope < -adaptive_slope_threshold:
                        falling_count += 1
                    total_slope += abs(combined_slope)  # 使用绝对值，因为都是负坡度

                # 计算候选得分：考虑连续下降帧数和总体坡度强度
                if falling_count >= self._config.min_slope_frames:
                    avg_slope = total_slope / len(robust_slopes)
                    consistency = 1.0 - (max(robust_slopes) - min(robust_slopes)) / (abs(avg_slope) + 1e-6)
                    score = falling_count * avg_slope * consistency

                    if score > best_score:
                        best_score = score
                        best_candidate = i

                    self._logger.debug(f"Falling slope candidate at frame {i}, "
                                     f"falling_count={falling_count}, avg_slope={avg_slope:.3f}, "
                                     f"score={score:.3f}")

        if best_candidate is not None:
            self._logger.debug(f"Best falling slope detected at frame {best_candidate}, score={best_score:.3f}")
            return best_candidate

        return None

    def _detect_complete_waveform(self, frame_data: List[float]) -> Optional[Tuple[int, int]]:
        """
        检测完整的上升-下降波形对

        Args:
            frame_data: 帧数据列表

        Returns:
            Optional[Tuple[int, int]]: (上升位置, 下降位置)，未找到返回None
        """
        # 检测上升波形
        rise_position = self._detect_rising_slope(frame_data)
        if rise_position is None:
            return None

        # 检测下降波形
        fall_position = self._detect_falling_slope(frame_data)
        if fall_position is None:
            return None

        # 验证波形顺序：上升必须在下降之前
        if rise_position >= fall_position:
            return None

        # 验证时间间隔：上升和下降之间应该有合理的间隔
        min_interval = self._config.min_slope_frames
        max_interval = len(frame_data) // 2  # 最大间隔不超过窗口一半

        interval = fall_position - rise_position
        if interval < min_interval or interval > max_interval:
            return None

        self._logger.debug(f"Complete waveform detected: rise={rise_position}, fall={fall_position}, interval={interval}")
        return (rise_position, fall_position)

    def process_frame(self, roi_gray_value: float, frame_count: int) -> dict:
        """
        处理单帧数据进行滑动窗口波峰检测

        Args:
            roi_gray_value: ROI灰度值
            frame_count: 当前帧计数

        Returns:
            dict: 包含波峰检测结果的字典
        """
        # 详细的帧处理日志
        self._logger.debug(f"🔄 [FRAME-{frame_count}] Processing ROI value: {roi_gray_value:.3f}")

        # 添加到帧缓冲区
        self._frame_buffer.append(roi_gray_value)
        self._logger.debug(f"📊 [BUFFER] Size: {len(self._frame_buffer)}, Latest values: {self._frame_buffer[-5:]}")

        # 限制缓冲区大小，保留最近window_size帧
        max_buffer_size = self._config.window_size
        if len(self._frame_buffer) > max_buffer_size:
            self._frame_buffer = self._frame_buffer[-max_buffer_size:]
            self._logger.debug(f"✂️ [BUFFER] Trimmed to max size: {max_buffer_size}")

        # 初始化返回值
        peak_signal = None
        peak_color = None
        peak_confidence = 0.0
        in_peak_region = False

        # 诊断信息收集
        diagnostic_info = {
            'frame_count': frame_count,
            'roi_value': roi_gray_value,
            'buffer_size': len(self._frame_buffer),
            'threshold_check': roi_gray_value > self._config.threshold,
            'slope_analysis': {},
            'waveform_detection': {},
            'failure_reasons': []
        }

        # 滑动窗口检测：检查前window_size帧是否有完整波形
        if len(self._frame_buffer) >= self._config.min_slope_frames + 2:
            # 提取窗口数据（最近的window_size帧）
            window_data = self._frame_buffer[-self._config.window_size:] if len(self._frame_buffer) >= self._config.window_size else self._frame_buffer
            self._logger.debug(f"🔍 [WINDOW] Analyzing {len(window_data)} frames: {[f'{v:.1f}' for v in window_data[-10:]]}")

            # 详细的坡度分析 - 使用多种方法
            for i in range(2, min(len(window_data) - 1, 15)):  # 分析最近15帧的坡度
                # 使用多种方法计算坡度
                basic_slope = self._calculate_slope(window_data, i)
                adaptive_slope = self._calculate_slope(window_data, i, "adaptive")
                robust_slope = self._calculate_robust_slope(window_data, i)
                smoothed_slope = self._calculate_smoothed_slope(window_data, i)
                value = window_data[i]

                # 综合坡度评估
                combined_slope = (robust_slope * 0.5 + adaptive_slope * 0.3 + smoothed_slope * 0.2)

                diagnostic_info['slope_analysis'][f'frame_{i}'] = {
                    'value': value,
                    'slope': basic_slope,
                    'adaptive_slope': adaptive_slope,
                    'robust_slope': robust_slope,
                    'smoothed_slope': smoothed_slope,
                    'combined_slope': combined_slope,
                    'above_threshold': value > self._config.threshold,
                    'rising_slope': combined_slope > self._config.slope_threshold,
                    'falling_slope': combined_slope < -self._config.slope_threshold,
                    'slope_consistency': 1.0 - abs(robust_slope - adaptive_slope) / (abs(combined_slope) + 1e-6)
                }

                self._logger.debug(f"📈 [SLOPE] Frame {i}: value={value:.2f}, "
                                 f"slopes[basic={basic_slope:.3f}, adaptive={adaptive_slope:.3f}, "
                                 f"robust={robust_slope:.3f}, combined={combined_slope:.3f}], "
                                 f"threshold_check={value > self._config.threshold}, "
                                 f"rising={combined_slope > self._config.slope_threshold}")

            # 增强的多峰检测
            all_peaks = self._detect_multiple_peaks(window_data)
            diagnostic_info['waveform_detection']['result'] = len(all_peaks) > 0
            diagnostic_info['waveform_detection']['peak_count'] = len(all_peaks)

            if all_peaks:
                # 选择最佳波峰（最高置信度）
                best_peak = max(all_peaks, key=lambda p: p['confidence'])
                rise_pos, fall_pos = best_peak['rise_pos'], best_peak['fall_pos']

                self._logger.info(f"🎯 [MULTI-PEAK] Detected {len(all_peaks)} peaks, "
                                f"selected best at rise={rise_pos}, fall={fall_pos}")

                # 在窗口内找到最大值位置
                max_value = max(window_data[rise_pos:fall_pos + 1])
                peak_pos_in_window = rise_pos + window_data[rise_pos:fall_pos + 1].index(max_value)

                # 计算实际的帧位置
                actual_peak_frame = frame_count - (len(window_data) - peak_pos_in_window)

                # 验证波峰质量
                peak_quality = self._validate_peak_quality(window_data, rise_pos, fall_pos, max_value)
                if peak_quality['is_valid']:
                    # 分析颜色分类
                    color, confidence = self._classify_waveform_color(window_data, rise_pos, fall_pos)
                    self._logger.debug(f"🎨 [CLASSIFICATION] Color: {color}, Confidence: {confidence:.2f}")

                    # 创建波峰区域
                    peak_region = PeakRegion(
                        start_frame=max(0, actual_peak_frame - self._config.margin_frames),
                        end_frame=actual_peak_frame + self._config.margin_frames,
                        peak_frame=actual_peak_frame,
                        max_value=max_value,
                        color=color,
                        confidence=confidence,
                        difference=max_value - min(window_data[rise_pos], window_data[fall_pos])
                    )

                    self._peak_regions.append(peak_region)
                    peak_signal = 1
                    peak_color = color
                    peak_confidence = confidence
                    in_peak_region = True

                    # 详细的成功检测日志
                    self._logger.info(f"🟢 [PEAK DETECTED] Frame={actual_peak_frame}, "
                                    f"Value={max_value:.2f}, Color={color}, Confidence={confidence:.2f}, "
                                    f"Rise={rise_pos}, Fall={fall_pos}, Quality={peak_quality['score']:.2f}, "
                                    f"Window_Size={len(window_data)}")
                else:
                    # 波峰质量不合格
                    diagnostic_info['failure_reasons'].append(f"Peak quality too low: {peak_quality['reasons']}")
                    self._logger.debug(f"❌ [PEAK QUALITY] Peak rejected: {peak_quality['reasons']}")

            else:
                # 分析为什么没有检测到波峰
                self._analyze_detection_failure(window_data, diagnostic_info, frame_count)

        else:
            reason = f"Insufficient buffer size: {len(self._frame_buffer)} < {self._config.min_slope_frames + 2}"
            diagnostic_info['failure_reasons'].append(reason)
            self._logger.debug(f"⏳ [SKIP] {reason}")

        # 返回结果包含诊断信息
        result = {
            'peak_signal': peak_signal,
            'peak_color': peak_color,
            'peak_confidence': peak_confidence,
            'threshold': self._config.threshold,
            'in_peak_region': in_peak_region,
            'frame_count': frame_count,
            'diagnostic_info': diagnostic_info
        }

        # 如果没有检测到波峰，记录摘要
        if peak_signal is None:
            failure_summary = ", ".join(diagnostic_info['failure_reasons']) if diagnostic_info['failure_reasons'] else "No obvious failure reason"
            self._logger.debug(f"❌ [NO PEAK] Frame={frame_count}, Value={roi_gray_value:.2f}, Reasons: {failure_summary}")

        return result

    def _analyze_detection_failure(self, window_data: List[float], diagnostic_info: dict, frame_count: int) -> None:
        """分析检测失败的具体原因"""

        # 检查是否有值超过阈值
        max_value = max(window_data)
        if max_value <= self._config.threshold:
            diagnostic_info['failure_reasons'].append(f"All values below threshold: max={max_value:.2f} <= {self._config.threshold}")
            self._logger.debug(f"📉 [FAILURE] All values below threshold")
            return

        # 检查上升波形检测
        rise_result = self._detect_rising_slope(window_data)
        if rise_result is None:
            diagnostic_info['failure_reasons'].append("No valid rising slope detected")
            self._logger.debug(f"📉 [FAILURE] No rising slope - values may be too gradual or noisy")

        # 检查下降波形检测
        fall_result = self._detect_falling_slope(window_data)
        if fall_result is None:
            diagnostic_info['failure_reasons'].append("No valid falling slope detected")
            self._logger.debug(f"📉 [FAILURE] No falling slope - values may not fall properly")

        # 检查波形顺序和间隔
        if rise_result is not None and fall_result is not None:
            rise_pos, fall_pos = rise_result, fall_result
            if rise_pos >= fall_pos:
                diagnostic_info['failure_reasons'].append(f"Invalid waveform order: rise({rise_pos}) >= fall({fall_pos})")
                self._logger.debug(f"📉 [FAILURE] Invalid waveform order")

            elif fall_pos - rise_pos < self._config.min_slope_frames:
                diagnostic_info['failure_reasons'].append(f"Interval too short: {fall_pos - rise_pos} < {self._config.min_slope_frames}")
                self._logger.debug(f"📉 [FAILURE] Peak interval too short")

            elif fall_pos - rise_pos > len(window_data) // 2:
                diagnostic_info['failure_reasons'].append(f"Interval too long: {fall_pos - rise_pos} > {len(window_data) // 2}")
                self._logger.debug(f"📉 [FAILURE] Peak interval too long")

        # 检查坡度计算
        slope_failures = []
        for i, slope_data in diagnostic_info['slope_analysis'].items():
            if slope_data['above_threshold'] and not slope_data['rising_slope']:
                slope_failures.append(f"{i}:value={slope_data['value']:.2f},slope={slope_data['slope']:.3f}")

        if slope_failures:
            diagnostic_info['failure_reasons'].append(f"Slope too shallow: {', '.join(slope_failures[:3])}")
            self._logger.debug(f"📉 [FAILURE] Slopes too gradual for rising detection")

    def _detect_multiple_peaks(self, frame_data: List[float]) -> List[dict]:
        """
        检测窗口内的多个波峰 - 支持复杂波形分析

        Args:
            frame_data: 帧数据列表

        Returns:
            List[dict]: 检测到的所有波峰信息，每个包含rise_pos, fall_pos, confidence等
        """
        peaks = []
        processed_ranges = []  # 记录已处理的范围，避免重复检测

        # 计算动态阈值和自适应坡度阈值
        dynamic_threshold = self._calculate_dynamic_threshold(frame_data)
        adaptive_slope_threshold = self._get_adaptive_slope_threshold(frame_data)

        # 使用滑动窗口方法检测多个潜在的波峰
        search_window = self._config.min_slope_frames * 2

        for start in range(0, len(frame_data) - search_window, search_window // 2):
            end = min(start + search_window, len(frame_data))
            search_segment = frame_data[start:end]

            # 检查这个搜索段是否已经被处理过
            if any(self._ranges_overlap((start, end), processed) for processed in processed_ranges):
                continue

            # 在这个搜索段中检测波峰
            rise_result = self._detect_rising_slope_in_segment(search_segment, start, dynamic_threshold, adaptive_slope_threshold)
            if rise_result is not None:
                rise_pos = start + rise_result

                # 从上升位置开始寻找下降位置
                remaining_data = frame_data[rise_pos:]
                fall_result = self._detect_falling_slope_in_segment(remaining_data, 0, adaptive_slope_threshold)

                if fall_result is not None:
                    fall_pos = rise_pos + fall_result

                    # 验证波形的基本有效性
                    if rise_pos < fall_pos and (fall_pos - rise_pos) >= self._config.min_slope_frames:
                        # 计算波峰质量评分
                        peak_quality = self._calculate_peak_quality(frame_data, rise_pos, fall_pos)

                        if peak_quality['score'] > 0.3:  # 最低质量阈值
                            peak_info = {
                                'rise_pos': rise_pos,
                                'fall_pos': fall_pos,
                                'confidence': peak_quality['score'],
                                'quality_metrics': peak_quality['metrics']
                            }
                            peaks.append(peak_info)
                            processed_ranges.append((rise_pos, fall_pos))

                            self._logger.debug(f"🏔️ [MULTI-PEAK] Found peak at rise={rise_pos}, fall={fall_pos}, "
                                             f"quality={peak_quality['score']:.3f}")

        # 对波峰进行去重和排序（按置信度）
        peaks = self._deduplicate_peaks(peaks)
        peaks.sort(key=lambda p: p['confidence'], reverse=True)

        # 限制最大波峰数量
        max_peaks = 5
        if len(peaks) > max_peaks:
            peaks = peaks[:max_peaks]

        self._logger.debug(f"🔍 [MULTI-PEAK] Total peaks detected: {len(peaks)}")
        return peaks

    def _detect_rising_slope_in_segment(self, segment_data: List[float], offset: int, threshold: float, slope_threshold: float) -> Optional[int]:
        """在指定段内检测上升坡度"""
        for i in range(len(segment_data) - self._config.min_slope_frames):
            if segment_data[i] > threshold:
                rising_count = 0
                total_slope = 0.0

                for j in range(i, min(i + self._config.min_slope_frames, len(segment_data))):
                    combined_slope = self._calculate_robust_slope(segment_data, j)
                    if combined_slope > slope_threshold:
                        rising_count += 1
                    total_slope += combined_slope

                if rising_count >= self._config.min_slope_frames and total_slope > 0:
                    return i
        return None

    def _detect_falling_slope_in_segment(self, segment_data: List[float], offset: int, slope_threshold: float) -> Optional[int]:
        """在指定段内检测下降坡度"""
        for i in range(len(segment_data) - 1, self._config.min_slope_frames, -1):
            falling_count = 0
            total_slope = 0.0

            for j in range(i, max(i - self._config.min_slope_frames, 0), -1):
                combined_slope = self._calculate_robust_slope(segment_data, j)
                if combined_slope < -slope_threshold:
                    falling_count += 1
                    total_slope += abs(combined_slope)

            if falling_count >= self._config.min_slope_frames and total_slope > 0:
                return i
        return None

    def _calculate_peak_quality(self, frame_data: List[float], rise_pos: int, fall_pos: int) -> dict:
        """
        计算波峰质量评分

        Args:
            frame_data: 帧数据列表
            rise_pos: 上升位置
            fall_pos: 下降位置

        Returns:
            dict: 包含score和详细metrics的质量评估
        """
        if rise_pos >= fall_pos or fall_pos >= len(frame_data):
            return {'score': 0.0, 'metrics': {}}

        peak_data = frame_data[rise_pos:fall_pos + 1]
        if not peak_data:
            return {'score': 0.0, 'metrics': {}}

        # 提取波峰特征
        max_value = max(peak_data)
        min_value = min(frame_data[max(0, rise_pos - 5):fall_pos + 6])  # 包含前后区域
        peak_amplitude = max_value - min_value
        peak_width = fall_pos - rise_pos
        peak_symmetry = abs((peak_data.index(max_value) - peak_width / 2) / (peak_width / 2 + 1))

        # 计算波形质量指标
        metrics = {
            'amplitude': peak_amplitude,
            'width': peak_width,
            'symmetry': peak_symmetry,  # 0为完全对称
            'sharpness': peak_amplitude / (peak_width + 1),  # 幅宽比
            'signal_noise': 1.0,  # 将在下面计算
            'trend_consistency': 1.0  # 将在下面计算
        }

        # 计算信噪比
        baseline_noise = 0.0
        if len(frame_data) > 20:
            baseline_region = frame_data[-20:]  # 使用最后20帧作为基线
            baseline_mean = sum(baseline_region) / len(baseline_region)
            baseline_variance = sum((x - baseline_mean) ** 2 for x in baseline_region) / len(baseline_region)
            baseline_noise = baseline_variance ** 0.5 if baseline_variance > 0 else 1.0
            metrics['signal_noise'] = peak_amplitude / (baseline_noise + 1e-6)

        # 计算趋势一致性
        slopes_in_peak = []
        for i in range(rise_pos, min(fall_pos, len(frame_data) - 1)):
            slopes_in_peak.append(self._calculate_slope(frame_data, i))

        if slopes_in_peak:
            slope_consistency = 1.0 - (max(slopes_in_peak) - min(slopes_in_peak)) / (abs(sum(slopes_in_peak) / len(slopes_in_peak)) + 1e-6)
            metrics['trend_consistency'] = max(0.0, slope_consistency)

        # 综合质量评分
        score_components = [
            min(1.0, metrics['amplitude'] / 20.0),  # 幅度评分 (归一化到20)
            min(1.0, metrics['width'] / 10.0),      # 宽度评分 (归一化到10)
            max(0.0, 1.0 - metrics['symmetry']),    # 对称性评分
            min(1.0, metrics['sharpness'] / 2.0),    # 尖锐度评分
            min(1.0, metrics['signal_noise'] / 5.0), # 信噪比评分
            metrics['trend_consistency']            # 趋势一致性评分
        ]

        # 加权平均
        weights = [0.2, 0.15, 0.15, 0.2, 0.2, 0.1]
        score = sum(comp * weight for comp, weight in zip(score_components, weights))

        return {
            'score': min(1.0, max(0.0, score)),
            'metrics': metrics
        }

    def _validate_peak_quality(self, frame_data: List[float], rise_pos: int, fall_pos: int, max_value: float) -> dict:
        """
        验证波峰质量是否符合要求

        Args:
            frame_data: 帧数据列表
            rise_pos: 上升位置
            fall_pos: 下降位置
            max_value: 最大值

        Returns:
            dict: 包含is_valid和reasons的验证结果
        """
        quality = self._calculate_peak_quality(frame_data, rise_pos, fall_pos)
        score = quality['score']
        metrics = quality['metrics']

        reasons = []
        is_valid = True

        # 质量阈值检查
        if score < 0.4:
            is_valid = False
            reasons.append(f"Quality score too low: {score:.3f}")

        # 具体指标检查
        if metrics.get('amplitude', 0) < 5.0:
            is_valid = False
            reasons.append(f"Amplitude too small: {metrics.get('amplitude', 0):.2f}")

        if metrics.get('width', 0) < 2:
            is_valid = False
            reasons.append(f"Peak too narrow: {metrics.get('width', 0)} frames")

        if metrics.get('symmetry', 1.0) > 0.8:
            reasons.append(f"Poor symmetry: {metrics.get('symmetry', 1.0):.3f}")

        if metrics.get('signal_noise', 0) < 2.0:
            reasons.append(f"Low signal-to-noise ratio: {metrics.get('signal_noise', 0):.2f}")

        # 波形形状检查
        if fall_pos - rise_pos > len(frame_data) // 3:
            is_valid = False
            reasons.append(f"Peak too wide: {fall_pos - rise_pos} frames")

        return {
            'is_valid': is_valid,
            'score': score,
            'reasons': reasons,
            'metrics': metrics
        }

    def _ranges_overlap(self, range1: Tuple[int, int], range2: Tuple[int, int]) -> bool:
        """检查两个范围是否重叠"""
        return not (range1[1] < range2[0] or range2[1] < range1[0])

    def _deduplicate_peaks(self, peaks: List[dict]) -> List[dict]:
        """去除重复或过于接近的波峰"""
        if len(peaks) <= 1:
            return peaks

        # 按位置排序
        peaks.sort(key=lambda p: p['rise_pos'])
        deduplicated = [peaks[0]]

        for peak in peaks[1:]:
            last_peak = deduplicated[-1]
            distance = peak['rise_pos'] - last_peak['fall_pos']

            # 如果距离太小，选择置信度更高的那个
            if distance < self._config.min_slope_frames:
                if peak['confidence'] > last_peak['confidence']:
                    deduplicated[-1] = peak
            else:
                deduplicated.append(peak)

        return deduplicated

    def _classify_waveform_color(self, frame_data: List[float], rise_pos: int, fall_pos: int) -> Tuple[str, float]:
        """
        基于波形前后差值进行颜色分类

        Args:
            frame_data: 帧数据
            rise_pos: 上升位置
            fall_pos: 下降位置

        Returns:
            Tuple[str, float]: (颜色, 置信度)
        """
        try:
            # 计算上升前的平均值（前5帧或可用帧）
            before_frames = max(3, min(5, rise_pos))
            before_start = max(0, rise_pos - before_frames)
            before_values = frame_data[before_start:rise_pos]
            before_avg = sum(before_values) / len(before_values) if before_values else frame_data[rise_pos]

            # 计算下降后的平均值（后5帧或可用帧）
            after_frames = max(3, min(5, len(frame_data) - fall_pos - 1))
            after_end = min(len(frame_data), fall_pos + after_frames + 1)
            after_values = frame_data[fall_pos + 1:after_end]
            after_avg = sum(after_values) / len(after_values) if after_values else frame_data[fall_pos]

            # 计算差值
            difference = after_avg - before_avg

            # 颜色分类
            if difference > self._config.difference_threshold:
                # 绿色波峰：稳定事件
                confidence = min(1.0, difference / (self._config.difference_threshold * 2))
                return 'green', confidence
            else:
                # 红色波峰：可能不稳定
                confidence = max(0.0, difference / self._config.difference_threshold)
                return 'red', confidence

        except Exception as e:
            self._logger.warning(f"Error in waveform color classification: {e}")
            return 'red', 0.0

    def _analyze_peak_region(self, start_frame: int, end_frame: int) -> Optional[PeakRegion]:
        """
        分析波峰区域，确定波峰特征和颜色分类

        Args:
            start_frame: 波峰区域开始帧
            end_frame: 波峰区域结束帧

        Returns:
            PeakRegion: 波峰区域分析结果
        """
        if start_frame >= len(self._frame_buffer) or end_frame >= len(self._frame_buffer):
            return None

        # 提取波峰区域的数据
        region_values = self._frame_buffer[start_frame:end_frame + 1]

        if not region_values:
            return None

        # 找到最大值和对应帧
        max_value = max(region_values)
        peak_frame_offset = region_values.index(max_value)
        peak_frame = start_frame + peak_frame_offset

        # 应用边界扩展
        extended_start = max(0, start_frame - self._config.margin_frames)
        extended_end = min(len(self._frame_buffer) - 1, end_frame + self._config.margin_frames)

        # 计算颜色分类（前后差值）
        difference = self._calculate_frame_difference(peak_frame, extended_start, extended_end)

        # 确定颜色分类
        if difference > self._config.difference_threshold:
            color = 'green'  # 稳定事件
            confidence = min(1.0, difference / (self._config.difference_threshold * 2))
        else:
            color = 'red'    # 可能不稳定
            confidence = max(0.0, difference / self._config.difference_threshold)

        return PeakRegion(
            start_frame=extended_start,
            end_frame=extended_end,
            peak_frame=peak_frame,
            max_value=max_value,
            color=color,
            confidence=confidence,
            difference=difference
        )

    def _calculate_frame_difference(self, peak_frame: int, extended_start: int, extended_end: int) -> float:
        """
        计算波峰前后的灰度值差值

        Args:
            peak_frame: 波峰帧位置
            extended_start: 扩展区域开始帧
            extended_end: 扩展区域结束帧

        Returns:
            float: 帧差值
        """
        # 计算波峰前5帧平均值
        before_start = max(extended_start, peak_frame - 5)
        before_end = peak_frame - 1

        before_avg = 0.0
        before_count = 0
        if before_end >= before_start and before_start >= 0:
            before_values = self._frame_buffer[before_start:before_end + 1]
            before_avg = sum(before_values) / len(before_values)
            before_count = len(before_values)

        # 计算波峰后5帧平均值
        after_start = peak_frame + 1
        after_end = min(extended_end, peak_frame + 5)

        after_avg = 0.0
        after_count = 0
        if after_end >= after_start and after_end < len(self._frame_buffer):
            after_values = self._frame_buffer[after_start:after_end + 1]
            after_avg = sum(after_values) / len(after_values)
            after_count = len(after_values)

        # 计算差值
        if before_count > 0 and after_count > 0:
            difference = after_avg - before_avg
        else:
            difference = 0.0

        self._logger.debug(f"Frame difference calculation: "
                         f"before_avg={before_avg:.2f} ({before_count} frames), "
                         f"after_avg={after_avg:.2f} ({after_count} frames), "
                         f"difference={difference:.2f}")

        return difference

    def get_current_config(self) -> PeakDetectionConfig:
        """获取当前波峰检测配置"""
        return self._config

    def get_recent_peaks(self, max_count: int = 10) -> List[PeakRegion]:
        """获取最近的波峰检测结果"""
        return self._peak_regions[-max_count:]

    def clear_peak_history(self) -> None:
        """清除波峰历史记录"""
        self._peak_regions.clear()
        self._current_region = None
        self._logger.info("Peak detection history cleared")

    def get_status(self) -> dict:
        """获取检测器状态信息"""
        return {
            'config': {
                'threshold': self._config.threshold,
                'margin_frames': self._config.margin_frames,
                'difference_threshold': self._config.difference_threshold,
                'min_region_length': self._config.min_region_length
            },
            'current_region': self._current_region,
            'total_peaks_detected': len(self._peak_regions),
            'frame_buffer_size': len(self._frame_buffer),
            'in_peak_region': self._current_region is not None
        }