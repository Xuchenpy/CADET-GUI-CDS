"""
可视化模块 v6 - CADET-Process 层析模拟系统

主要升级:
  - 盐浓度曲线颜色: #CC0000 -> #555555 (深灰色)
  - 支持峰标注
  - 使用 UnitConverter 处理时间轴转换
  - X 轴标签国际化: 'Time / s', 'Column Volumes / CV', 'Volume / mL'
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator
from typing import List, Optional

from config_models import ProcessConfig
from unit_converter import UnitConverter
from peak_analysis import PeakInfo

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'KaiTi', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


# 配色方案 - 层析仪器风格
COLORS = {
    'total_protein': '#0000CC',    # 深蓝色 (UV 280nm 风格)
    'salt': '#555555',             # v6: 深灰色 (规格 §1.6)
    'components': ['#2196F3', '#4CAF50', '#FF9800', '#9C27B0', '#F44336',
                   '#00BCD4', '#795548'],
    'step_boundary': '#888888',
    'background': '#FFFFFF',
}


class ChromatogramPlotter:
    """层析图谱绘制器 v6"""

    def __init__(self, figsize=(14, 7), dpi=100, style='default'):
        self.figsize = figsize
        self.dpi = dpi
        self.style = style

    def plot_chromatogram(
        self,
        config: ProcessConfig,
        time: np.ndarray,
        concentration: np.ndarray,
        title: str = None,
        save_path: str = None,
        show: bool = True,
        x_unit: str = 'seconds',
        peaks: List[PeakInfo] = None,
        fig=None,
    ) -> plt.Figure:
        """
        绘制层析图谱

        Parameters
        ----------
        config : ProcessConfig
        time : np.ndarray
        concentration : np.ndarray
        title : str, optional
        save_path : str, optional
        show : bool
        x_unit : str
            'seconds', 'cv', 'volume_ml'
        peaks : list of PeakInfo, optional
            峰分析结果，用于标注
        fig : Figure, optional
            传入已有 Figure 用于嵌入 GUI

        Returns
        -------
        matplotlib.figure.Figure
        """
        components = config.method_settings.components
        n_comp = len(components)
        ms = config.method_settings

        # 时间轴转换 (使用 UnitConverter)
        col_vol_ml = ms.column_params.column_volume_ml
        flow_ml_min = ms.inlet_params.flow_rate_ml_min
        time_plot, x_label = UnitConverter.convert_time_array(
            time, x_unit, col_vol_ml, flow_ml_min
        )

        if fig is None:
            fig, ax1 = plt.subplots(figsize=self.figsize, dpi=self.dpi)
        else:
            fig.clear()
            ax1 = fig.add_subplot(111)
        fig.patch.set_facecolor(COLORS['background'])

        # ---- 左 Y 轴：蛋白组分浓度 ----
        ax1.set_xlabel(x_label, fontsize=12)
        ax1.set_ylabel('Protein Concentration (mM)', fontsize=12, color=COLORS['total_protein'])

        salt_idx = None
        protein_indices = []
        for i, comp in enumerate(components):
            if comp.lower() == 'salt':
                salt_idx = i
            else:
                protein_indices.append(i)

        # 绘制各蛋白组分（虚线）
        for j, idx in enumerate(protein_indices):
            color = COLORS['components'][j % len(COLORS['components'])]
            ax1.plot(
                time_plot, concentration[:, idx],
                linestyle='--', color=color, linewidth=1.2,
                alpha=0.7, label=f'{components[idx]}',
            )

        # 绘制总蛋白叠加曲线（实线）
        if protein_indices:
            total_protein = np.sum(concentration[:, protein_indices], axis=1)
            ax1.plot(
                time_plot, total_protein,
                linestyle='-', color=COLORS['total_protein'], linewidth=2.0,
                label='Total Protein',
            )

        ax1.tick_params(axis='y', labelcolor=COLORS['total_protein'])
        ax1.set_ylim(bottom=0)

        # ---- 右 Y 轴：盐浓度 (v6: #555555 深灰色) ----
        ax2 = None
        if salt_idx is not None:
            ax2 = ax1.twinx()
            ax2.set_ylabel('Salt Concentration (mM)', fontsize=12, color=COLORS['salt'])
            ax2.plot(
                time_plot, concentration[:, salt_idx],
                linestyle='-', color=COLORS['salt'], linewidth=1.5,
                alpha=0.8, label=f'{components[salt_idx]}',
            )
            ax2.tick_params(axis='y', labelcolor=COLORS['salt'])
            ax2.set_ylim(bottom=0)

        # ---- 工艺步骤边界标注 (彩色色带 + 底部标签) ----
        boundaries = config.get_step_boundaries()
        y_min_protein, y_max_protein = ax1.get_ylim()
        x_min, x_max = ax1.get_xlim()
        total_x_range = x_max - x_min

        _short_names = {
            'Equilibration': 'EQ',
            'Sample Application': 'Load',
            'Column Wash': 'Wash',
            'Elution': 'Elution',
        }

        _step_colors = ['#90CAF9', '#FFB74D', '#81C784', '#F48FB1',
                        '#CE93D8', '#80DEEA', '#FFF176']

        visible_boundaries = [b for b in boundaries if b['duration'] > 0]

        for i, boundary in enumerate(visible_boundaries):
            end_time_s = boundary['end_time']
            start_time_s = boundary['start_time']

            # 转换步骤边界时间
            if x_unit == 'cv':
                flow_ml_s = flow_ml_min / 60.0
                end_time = end_time_s * flow_ml_s / (col_vol_ml * 1e-6) if col_vol_ml > 0 else end_time_s
                start_time = start_time_s * flow_ml_s / (col_vol_ml * 1e-6) if col_vol_ml > 0 else start_time_s
                # 重新用 UnitConverter
                end_time = UnitConverter.time_s_to_cv(end_time_s, col_vol_ml, flow_ml_min)
                start_time = UnitConverter.time_s_to_cv(start_time_s, col_vol_ml, flow_ml_min)
            elif x_unit == 'volume_ml':
                end_time = UnitConverter.time_s_to_volume_ml(end_time_s, flow_ml_min)
                start_time = UnitConverter.time_s_to_volume_ml(start_time_s, flow_ml_min)
            else:
                end_time = end_time_s
                start_time = start_time_s

            step_color = _step_colors[i % len(_step_colors)]

            # 淡色背景色带
            ax1.axvspan(start_time, end_time, alpha=0.10, color=step_color, zorder=0)

            # 垂直分界线
            if i < len(visible_boundaries) - 1:
                ax1.axvline(
                    x=end_time, color=COLORS['step_boundary'],
                    linestyle='--', linewidth=1.0, alpha=0.5,
                )

            # 底部标签
            step_width = end_time - start_time
            mid_time = (start_time + end_time) / 2.0
            name = boundary['display_name']

            if step_width > total_x_range * 0.08:
                ax1.text(
                    mid_time, y_max_protein * 0.02, name,
                    ha='center', va='bottom', fontsize=9,
                    color='#555555', fontweight='bold', alpha=0.8,
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                              edgecolor='none', alpha=0.7),
                )
            else:
                short = _short_names.get(name, name)
                ax1.text(
                    mid_time, y_max_protein * 0.02, short,
                    ha='center', va='bottom', fontsize=8,
                    color='#555555', fontweight='bold', alpha=0.8,
                    rotation=90 if step_width < total_x_range * 0.02 else 0,
                    bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                              edgecolor='none', alpha=0.7),
                )

        # ---- 峰标注 ----
        if peaks:
            self._annotate_peaks(ax1, time_plot, time, peaks, x_unit, col_vol_ml, flow_ml_min)

        # ---- 图例 ----
        lines1, labels1 = ax1.get_legend_handles_labels()
        if ax2 is not None:
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2,
                       loc='upper right', fontsize=9, framealpha=0.9)
        else:
            ax1.legend(loc='upper right', fontsize=9, framealpha=0.9)

        # ---- 标题和网格 ----
        if title is None:
            title = f'Chromatogram - {config.process_name}'
        ax1.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax1.grid(True, alpha=0.3, linestyle='-')
        ax1.xaxis.set_minor_locator(AutoMinorLocator())
        ax1.yaxis.set_minor_locator(AutoMinorLocator())

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=self.dpi, bbox_inches='tight',
                        facecolor=fig.get_facecolor())

        if show:
            plt.show()

        return fig

    def _annotate_peaks(
        self, ax, time_plot, time_s, peaks: List[PeakInfo],
        x_unit: str, col_vol_ml: float, flow_ml_min: float
    ):
        """在图上标注峰位置"""
        for peak in peaks:
            # 将保留时间转为显示单位
            if x_unit == 'cv':
                rt_display = UnitConverter.time_s_to_cv(peak.retention_time_s, col_vol_ml, flow_ml_min)
            elif x_unit == 'volume_ml':
                rt_display = UnitConverter.time_s_to_volume_ml(peak.retention_time_s, flow_ml_min)
            else:
                rt_display = peak.retention_time_s

            ax.annotate(
                f'{peak.component_name}\n{peak.peak_height:.2f} mM',
                xy=(rt_display, peak.peak_height),
                xytext=(0, 15),
                textcoords='offset points',
                ha='center', va='bottom',
                fontsize=7,
                color='#333333',
                arrowprops=dict(arrowstyle='->', color='#666666', lw=0.8),
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#FFFFEE',
                          edgecolor='#CCCCCC', alpha=0.8),
            )

    def plot_comparison(
        self,
        config: ProcessConfig,
        time: np.ndarray,
        conc_sim: np.ndarray,
        time_exp: np.ndarray = None,
        conc_exp: np.ndarray = None,
        title: str = None,
        save_path: str = None,
        show: bool = True,
    ) -> plt.Figure:
        """绘制模拟与实验数据的对比图"""
        components = config.method_settings.components
        n_comp = min(conc_sim.shape[1], len(components))

        fig, axes = plt.subplots(n_comp, 1, figsize=(12, 3 * n_comp),
                                  sharex=True, dpi=self.dpi)
        if n_comp == 1:
            axes = [axes]

        for i in range(n_comp):
            ax = axes[i]
            ax.plot(time, conc_sim[:, i], 'b-', linewidth=1.5, label='Simulation')
            if time_exp is not None and conc_exp is not None:
                if conc_exp.ndim == 1:
                    if i == 0:
                        ax.plot(time_exp, conc_exp, 'ro', markersize=2,
                                alpha=0.5, label='Experiment')
                elif conc_exp.shape[1] > i:
                    ax.plot(time_exp, conc_exp[:, i], 'ro', markersize=2,
                            alpha=0.5, label='Experiment')

            ax.set_ylabel(f'{components[i]} (mM)', fontsize=10)
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3)

        axes[-1].set_xlabel('Time / s', fontsize=12)

        if title is None:
            title = 'Simulation vs Experiment'
        fig.suptitle(title, fontsize=14, fontweight='bold')
        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=self.dpi, bbox_inches='tight')

        if show:
            plt.show()

        return fig


def plot_default_chromatogram(save_path: str = None, show: bool = True):
    """使用默认配置运行模拟并绘制层析图谱"""
    from simulation_engine import run_default_simulation
    config, engine, results, data = run_default_simulation()

    plotter = ChromatogramPlotter()
    fig = plotter.plot_chromatogram(
        config=config,
        time=data['time'],
        concentration=data['concentration'],
        save_path=save_path,
        show=show,
    )
    return fig


if __name__ == '__main__':
    plot_default_chromatogram(
        save_path='D:/column/CADET LGg/IEX_simulation_v6/chromatogram_default.png',
        show=True,
    )
