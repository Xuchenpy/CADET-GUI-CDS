"""
CSV 导出工具模块

支持:
  - UV 曲线数据导出 (时间 + 各组分浓度)
  - 峰分析报告导出
  - 用户自定义保存路径
"""

import csv
import os
import numpy as np
from typing import List, Dict, Optional


def export_chromatogram_csv(filepath: str,
                            time_array: np.ndarray,
                            concentration_array: np.ndarray,
                            component_names: List[str],
                            x_unit: str = 'seconds',
                            encoding: str = 'utf-8-sig'):
    """
    导出色谱数据为 CSV 文件

    Parameters
    ----------
    filepath : str
        输出文件路径
    time_array : np.ndarray
        时间/体积/CV 数组
    concentration_array : np.ndarray
        浓度矩阵 (n_points, n_components)
    component_names : list
        组分名称列表
    x_unit : str
        X 轴单位标签
    encoding : str
        文件编码 (默认 utf-8-sig 以兼容 Excel)
    """
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)

    unit_labels = {
        'seconds': 'Time(s)',
        'cv': 'Column Volumes(CV)',
        'volume_ml': 'Volume(mL)',
    }
    x_header = unit_labels.get(x_unit, 'Time(s)')

    n_comp = min(concentration_array.shape[1], len(component_names))
    headers = [x_header] + [f"{component_names[i]}(mM)" for i in range(n_comp)]

    with open(filepath, 'w', newline='', encoding=encoding) as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for i in range(len(time_array)):
            row = [f"{time_array[i]:.6f}"]
            for j in range(n_comp):
                row.append(f"{concentration_array[i, j]:.6f}")
            writer.writerow(row)


def export_peak_report_csv(filepath: str,
                           peak_report: Dict,
                           encoding: str = 'utf-8-sig'):
    """
    导出峰分析报告为 CSV

    Parameters
    ----------
    filepath : str
    peak_report : dict
        来自 PeakAnalyzer.generate_report()
    encoding : str
    """
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)

    if not peak_report.get('peaks'):
        return

    unit = peak_report['peaks'][0].get('unit', 's')
    headers = ['Component', f'Peak Height(mM)',
               f'Retention Time({unit})', f'FWHM({unit})',
               f'Baseline Width({unit})']

    with open(filepath, 'w', newline='', encoding=encoding) as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for p in peak_report['peaks']:
            writer.writerow([
                p['component'],
                f"{p['peak_height_mM']:.4f}",
                f"{p['retention_time']:.4f}",
                f"{p['fwhm']:.4f}",
                f"{p['baseline_width']:.4f}",
            ])

        if peak_report.get('resolutions'):
            writer.writerow([])
            writer.writerow(['Resolution Analysis'])
            writer.writerow(['Peak Pair', 'Rs'])
            for r in peak_report['resolutions']:
                writer.writerow([r['pair'], f"{r['Rs']:.3f}"])


def export_overlay_csv(filepath: str,
                       datasets: List[Dict],
                       encoding: str = 'utf-8-sig'):
    """
    导出 Overlay 比较数据为 CSV

    Parameters
    ----------
    filepath : str
    datasets : list of dict
        每个 dict 包含 'name', 'time', 'concentration', 'components'
    encoding : str
    """
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)

    if not datasets:
        return

    # 找到统一的时间网格 (使用最密集的时间轴)
    max_points = max(len(d['time']) for d in datasets)
    ref_time = None
    for d in datasets:
        if len(d['time']) == max_points:
            ref_time = d['time']
            break

    headers = ['Time(s)']
    all_data = [ref_time]

    for ds in datasets:
        name = ds['name']
        comps = ds['components']
        conc = ds['concentration']
        t = ds['time']

        for j, comp_name in enumerate(comps):
            if j < conc.shape[1]:
                # 线性插值到统一时间网格
                interp_conc = np.interp(ref_time, t, conc[:, j])
                headers.append(f"{name}_{comp_name}(mM)")
                all_data.append(interp_conc)

    with open(filepath, 'w', newline='', encoding=encoding) as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for i in range(len(ref_time)):
            row = [f"{all_data[0][i]:.6f}"]
            for col in all_data[1:]:
                row.append(f"{col[i]:.6f}")
            writer.writerow(row)
