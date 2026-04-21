"""
洗脱峰分析模块 v6 - CADET-Process 层析模拟系统

模拟完成后自动分析各蛋白组分的出口浓度曲线，输出:
  - 峰高 (mM)
  - 出峰时间 (保留时间)
  - 半峰宽 (FWHM)
  - 分离度 (Rs)
"""

import numpy as np
from typing import List, Dict, Optional, Any

try:
    from scipy.signal import find_peaks, peak_widths
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from unit_converter import UnitConverter


class PeakInfo:
    """单个峰的分析结果"""

    def __init__(self):
        self.component_name: str = ""
        self.peak_height: float = 0.0          # mM
        self.retention_time_s: float = 0.0     # 保留时间 (秒)
        self.fwhm_s: float = 0.0               # 半峰宽 (秒)
        self.baseline_width_s: float = 0.0     # 基线峰宽 (秒)
        self.peak_index: int = 0               # 峰顶索引

    def to_dict(self, display_unit: str = 'seconds',
                column_volume_ml: float = 0.0,
                flow_rate_ml_min: float = 0.0) -> Dict[str, Any]:
        """转为字典，时间按指定单位"""
        if display_unit == 'cv' and column_volume_ml > 0 and flow_rate_ml_min > 0:
            rt = UnitConverter.time_s_to_cv(self.retention_time_s, column_volume_ml, flow_rate_ml_min)
            fw = UnitConverter.time_s_to_cv(self.fwhm_s, column_volume_ml, flow_rate_ml_min)
            bw = UnitConverter.time_s_to_cv(self.baseline_width_s, column_volume_ml, flow_rate_ml_min)
            unit_label = 'CV'
        elif display_unit == 'volume_ml' and flow_rate_ml_min > 0:
            rt = UnitConverter.time_s_to_volume_ml(self.retention_time_s, flow_rate_ml_min)
            fw = UnitConverter.time_s_to_volume_ml(self.fwhm_s, flow_rate_ml_min)
            bw = UnitConverter.time_s_to_volume_ml(self.baseline_width_s, flow_rate_ml_min)
            unit_label = 'mL'
        else:
            rt = self.retention_time_s
            fw = self.fwhm_s
            bw = self.baseline_width_s
            unit_label = 's'

        return {
            'component': self.component_name,
            'peak_height_mM': round(self.peak_height, 4),
            'retention_time': round(rt, 4),
            'fwhm': round(fw, 4),
            'baseline_width': round(bw, 4),
            'unit': unit_label,
        }


class PeakAnalyzer:
    """
    洗脱峰分析器

    分析各蛋白组分的出口浓度曲线，提取峰参数。
    """

    def __init__(self, min_height_fraction: float = 0.01):
        """
        Parameters
        ----------
        min_height_fraction : float
            最小峰高阈值（相对于最大峰高的比例），低于此值的峰将被忽略
        """
        self.min_height_fraction = min_height_fraction

    def analyze(
        self,
        time: np.ndarray,
        concentration: np.ndarray,
        component_names: List[str],
        protein_indices: List[int],
    ) -> List[PeakInfo]:
        """
        分析峰参数

        Parameters
        ----------
        time : np.ndarray
            时间数组 (秒)
        concentration : np.ndarray
            浓度矩阵 (n_time, n_comp)
        component_names : list
            组分名称列表
        protein_indices : list
            蛋白组分索引列表 (不含 Salt)

        Returns
        -------
        list of PeakInfo
            各蛋白组分的峰信息
        """
        peaks_list = []

        for idx in protein_indices:
            if idx >= concentration.shape[1]:
                continue

            signal = concentration[:, idx]
            peak_info = self._find_main_peak(time, signal, component_names[idx])
            if peak_info is not None:
                peaks_list.append(peak_info)

        return peaks_list

    def _find_main_peak(
        self, time: np.ndarray, signal: np.ndarray, comp_name: str
    ) -> Optional[PeakInfo]:
        """找到信号中的主峰并计算参数"""
        max_val = np.max(signal)
        if max_val <= 0:
            return None

        min_height = max_val * self.min_height_fraction

        if HAS_SCIPY:
            return self._scipy_peak_analysis(time, signal, comp_name, min_height)
        else:
            return self._simple_peak_analysis(time, signal, comp_name, min_height)

    def _scipy_peak_analysis(
        self, time: np.ndarray, signal: np.ndarray, comp_name: str, min_height: float
    ) -> Optional[PeakInfo]:
        """使用 scipy.signal 进行精确峰分析"""
        peaks, properties = find_peaks(signal, height=min_height, distance=5)

        if len(peaks) == 0:
            return self._simple_peak_analysis(time, signal, comp_name, min_height)

        # 选择最高峰
        heights = signal[peaks]
        main_idx = np.argmax(heights)
        main_peak_pos = peaks[main_idx]

        info = PeakInfo()
        info.component_name = comp_name
        info.peak_height = float(signal[main_peak_pos])
        info.retention_time_s = float(time[main_peak_pos])
        info.peak_index = int(main_peak_pos)

        # 计算半峰宽 (FWHM)
        try:
            widths, width_heights, left_ips, right_ips = peak_widths(
                signal, [main_peak_pos], rel_height=0.5
            )
            dt = np.mean(np.diff(time)) if len(time) > 1 else 1.0
            info.fwhm_s = float(widths[0] * dt)

            # 基线峰宽 (约 4 * sigma ~ 2 * FWHM / 2.355 * 4)
            info.baseline_width_s = info.fwhm_s * 4.0 / 2.355
        except Exception:
            info.fwhm_s = self._estimate_fwhm(time, signal, main_peak_pos)
            info.baseline_width_s = info.fwhm_s * 4.0 / 2.355

        return info

    def _simple_peak_analysis(
        self, time: np.ndarray, signal: np.ndarray, comp_name: str, min_height: float
    ) -> Optional[PeakInfo]:
        """简单峰分析（无 scipy 时的备用方案）"""
        main_peak_pos = np.argmax(signal)
        peak_val = signal[main_peak_pos]

        if peak_val < min_height:
            return None

        info = PeakInfo()
        info.component_name = comp_name
        info.peak_height = float(peak_val)
        info.retention_time_s = float(time[main_peak_pos])
        info.peak_index = int(main_peak_pos)
        info.fwhm_s = self._estimate_fwhm(time, signal, main_peak_pos)
        info.baseline_width_s = info.fwhm_s * 4.0 / 2.355

        return info

    @staticmethod
    def _estimate_fwhm(time: np.ndarray, signal: np.ndarray, peak_pos: int) -> float:
        """手动估算半峰宽"""
        half_max = signal[peak_pos] / 2.0

        # 左侧
        left_idx = peak_pos
        for i in range(peak_pos, -1, -1):
            if signal[i] <= half_max:
                left_idx = i
                break

        # 右侧
        right_idx = peak_pos
        for i in range(peak_pos, len(signal)):
            if signal[i] <= half_max:
                right_idx = i
                break

        if right_idx > left_idx and left_idx < peak_pos and right_idx > peak_pos:
            return float(time[right_idx] - time[left_idx])
        return 0.0

    @staticmethod
    def calculate_resolution(peak1: PeakInfo, peak2: PeakInfo) -> float:
        """
        计算两个峰之间的分离度 Rs

        Rs = 2 * (t_R2 - t_R1) / (W_b1 + W_b2)

        Parameters
        ----------
        peak1 : PeakInfo
            先出峰
        peak2 : PeakInfo
            后出峰

        Returns
        -------
        float
            分离度 Rs
        """
        dt = abs(peak2.retention_time_s - peak1.retention_time_s)
        w_sum = peak1.baseline_width_s + peak2.baseline_width_s
        if w_sum <= 0:
            return float('inf') if dt > 0 else 0.0
        return 2.0 * dt / w_sum

    def generate_report(
        self,
        peaks: List[PeakInfo],
        display_unit: str = 'seconds',
        column_volume_ml: float = 0.0,
        flow_rate_ml_min: float = 0.0,
    ) -> Dict[str, Any]:
        """
        生成峰分析报告

        Parameters
        ----------
        peaks : list of PeakInfo
        display_unit : str
            显示单位: 'seconds', 'cv', 'volume_ml'
        column_volume_ml : float
        flow_rate_ml_min : float

        Returns
        -------
        dict
            包含峰数据和分离度的报告
        """
        report = {
            'peaks': [],
            'resolutions': [],
        }

        # 按保留时间排序
        sorted_peaks = sorted(peaks, key=lambda p: p.retention_time_s)

        for p in sorted_peaks:
            report['peaks'].append(p.to_dict(display_unit, column_volume_ml, flow_rate_ml_min))

        # 计算相邻峰的分离度
        for i in range(len(sorted_peaks) - 1):
            rs = self.calculate_resolution(sorted_peaks[i], sorted_peaks[i + 1])
            report['resolutions'].append({
                'pair': f"{sorted_peaks[i].component_name} vs {sorted_peaks[i+1].component_name}",
                'Rs': round(rs, 3),
            })

        return report

    def report_to_text(self, report: Dict[str, Any]) -> str:
        """将报告转为文本表格"""
        lines = []
        lines.append("=" * 70)
        lines.append("  洗脱峰分析报告")
        lines.append("=" * 70)

        if not report['peaks']:
            lines.append("  未检测到有效峰")
            return '\n'.join(lines)

        unit = report['peaks'][0].get('unit', 's')

        # 表头
        lines.append(f"{'Component':<12} {'Height(mM)':<14} "
                      f"{'Ret.Time(' + unit + ')':<18} "
                      f"{'FWHM(' + unit + ')':<18} "
                      f"{'BaseWidth(' + unit + ')':<18}")
        lines.append("-" * 70)

        for p in report['peaks']:
            lines.append(
                f"{p['component']:<12} {p['peak_height_mM']:<14.4f} "
                f"{p['retention_time']:<18.4f} {p['fwhm']:<18.4f} "
                f"{p['baseline_width']:<18.4f}"
            )

        if report['resolutions']:
            lines.append("")
            lines.append("分离度:")
            for r in report['resolutions']:
                lines.append(f"  {r['pair']}: Rs = {r['Rs']:.3f}")

        lines.append("=" * 70)
        return '\n'.join(lines)

    def report_to_csv_rows(self, report: Dict[str, Any]) -> List[List[str]]:
        """将报告转为 CSV 行数据"""
        if not report['peaks']:
            return []

        unit = report['peaks'][0].get('unit', 's')
        header = ['Component', f'Peak Height (mM)', f'Retention Time ({unit})',
                  f'FWHM ({unit})', f'Baseline Width ({unit})', 'Resolution']

        rows = [header]
        sorted_peaks = report['peaks']

        for i, p in enumerate(sorted_peaks):
            rs_str = ""
            for r in report['resolutions']:
                if r['pair'].startswith(p['component']):
                    rs_str = f"{r['Rs']:.3f}"
                    break
            rows.append([
                p['component'],
                f"{p['peak_height_mM']:.4f}",
                f"{p['retention_time']:.4f}",
                f"{p['fwhm']:.4f}",
                f"{p['baseline_width']:.4f}",
                rs_str,
            ])

        return rows


if __name__ == '__main__':
    # 测试
    print("峰分析模块测试")
    print("需要先运行模拟获取数据")

    # 生成模拟高斯峰测试
    t = np.linspace(0, 100, 1000)
    c = np.zeros((1000, 4))
    c[:, 0] = np.linspace(50, 500, 1000)  # Salt
    c[:, 1] = 1.5 * np.exp(-((t - 40) ** 2) / (2 * 3 ** 2))  # A
    c[:, 2] = 1.2 * np.exp(-((t - 55) ** 2) / (2 * 4 ** 2))  # B
    c[:, 3] = 0.8 * np.exp(-((t - 70) ** 2) / (2 * 5 ** 2))  # C

    analyzer = PeakAnalyzer()
    peaks = analyzer.analyze(t, c, ['Salt', 'A', 'B', 'C'], [1, 2, 3])
    report = analyzer.generate_report(peaks, display_unit='seconds')
    print(analyzer.report_to_text(report))
