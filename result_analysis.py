"""
Result Analysis Module (Module IV)

Features:
  - Historical result browsing
  - Chromatogram display / export
  - Overlay multi-result comparison
  - Curve alignment (injection marker, peak alignment)
  - Linear interpolation to uniform X-axis grid
  - UV curve / peak report CSV export
"""

import sys
import os
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

_app_dir = os.path.dirname(os.path.abspath(__file__))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from config_models import ProcessConfig
from visualization import ChromatogramPlotter
from peak_analysis import PeakAnalyzer
from unit_converter import UnitConverter

from styles import (
    PRIMARY_TEAL, DARK_NAVY, BG_MAIN, BG_CONTENT, BG_HEADER,
    TEXT_PRIMARY, TEXT_LIGHT, TEXT_SECONDARY,
    COMPONENT_COLORS, SALT_COLOR, TOTAL_PROTEIN_COLOR,
    FONT_TITLE, FONT_SUBTITLE, FONT_BODY, FONT_SMALL, FONT_MONO,
    TOOLBAR_BTN_BG
)
from csv_export import export_chromatogram_csv, export_peak_report_csv, export_overlay_csv


class ResultAnalysisModule(ttk.Frame):
    """Result Analysis Module"""

    def __init__(self, parent, db_manager, app_context, **kwargs):
        super().__init__(parent, **kwargs)
        self.db = db_manager
        self.ctx = app_context
        self.plotter = ChromatogramPlotter()
        self.analyzer = PeakAnalyzer()

        self._overlay_datasets = []
        self._build_ui()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ---- Top toolbar ----
        toolbar = ttk.Frame(self, style='Toolbar.TFrame')
        toolbar.grid(row=0, column=0, sticky='ew')
        lbl = tk.Label(toolbar, text="  Result Analysis", bg=DARK_NAVY,
                        fg=TEXT_LIGHT, font=FONT_SUBTITLE)
        lbl.pack(side='left', padx=10, pady=6)

        btn_f = tk.Frame(toolbar, bg=DARK_NAVY)
        btn_f.pack(side='right', padx=10)
        for text, cmd in [
            ("Refresh", self._refresh_results),
            ("Export CSV", self._on_export_csv),
            ("Export Peaks", self._on_export_peak_csv),
            ("Delete Result", self._on_delete_result),
        ]:
            tk.Button(btn_f, text=text, command=cmd,
                      bg=TOOLBAR_BTN_BG, fg=TEXT_LIGHT, relief='raised',
                      font=FONT_SMALL, padx=8, pady=2, bd=1,
                      activebackground=PRIMARY_TEAL,
                      activeforeground=TEXT_LIGHT).pack(side='left', padx=3)

        # ---- Main content ----
        main = ttk.PanedWindow(self, orient='horizontal')
        main.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        # -- Left: result list --
        left = ttk.Frame(main)
        main.add(left, weight=1)

        ttk.Label(left, text="Results:", font=FONT_SUBTITLE).pack(
            anchor='w', padx=5, pady=5)

        res_cols = ('id', 'name', 'date')
        self.result_tree = ttk.Treeview(left, columns=res_cols,
                                         show='headings', height=12)
        self.result_tree.heading('id', text='ID')
        self.result_tree.heading('name', text='Name')
        self.result_tree.heading('date', text='Created')
        self.result_tree.column('id', width=40)
        self.result_tree.column('name', width=200)
        self.result_tree.column('date', width=130)
        self.result_tree.pack(fill='both', expand=True, padx=5, pady=5)
        self.result_tree.bind('<<TreeviewSelect>>', self._on_result_select)

        sb = ttk.Scrollbar(left, orient='vertical',
                            command=self.result_tree.yview)
        sb.pack(side='right', fill='y')
        self.result_tree.configure(yscrollcommand=sb.set)

        # Overlay buttons
        overlay_frame = ttk.LabelFrame(left, text="Overlay Comparison")
        overlay_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(overlay_frame, text="Add to Overlay",
                   command=self._add_to_overlay,
                   style='Small.TButton').pack(fill='x', padx=5, pady=2)
        ttk.Button(overlay_frame, text="Show Overlay",
                   command=self._show_overlay,
                   style='Accent.TButton').pack(fill='x', padx=5, pady=2)
        ttk.Button(overlay_frame, text="Export Overlay CSV",
                   command=self._export_overlay_csv,
                   style='Small.TButton').pack(fill='x', padx=5, pady=2)
        ttk.Button(overlay_frame, text="Clear Overlay",
                   command=self._clear_overlay,
                   style='Small.TButton').pack(fill='x', padx=5, pady=2)

        self.lbl_overlay_count = ttk.Label(overlay_frame,
                                            text="Added: 0 results",
                                            font=FONT_SMALL)
        self.lbl_overlay_count.pack(padx=5, pady=3)

        # Alignment mode
        align_frame = ttk.LabelFrame(left, text="Curve Alignment")
        align_frame.pack(fill='x', padx=5, pady=5)

        self.var_align_mode = tk.StringVar(value='none')
        modes = [
            ('none', 'None'),
            ('injection', 'Injection Marker'),
            ('peak', 'Main Peak'),
        ]
        for val, text in modes:
            ttk.Radiobutton(align_frame, text=text,
                            variable=self.var_align_mode,
                            value=val).pack(anchor='w', padx=10, pady=2)

        # -- Right: charts + report --
        right = ttk.Frame(main)
        main.add(right, weight=3)

        right_nb = ttk.Notebook(right)
        right_nb.pack(fill='both', expand=True)

        # Single result chart
        chart_frame = ttk.Frame(right_nb)
        right_nb.add(chart_frame, text="Chromatogram")

        self.fig_single = plt.Figure(figsize=(10, 5), dpi=100)
        self.fig_single.patch.set_facecolor('#FFFFFF')
        self.canvas_single = FigureCanvasTkAgg(self.fig_single, master=chart_frame)
        self.canvas_single.get_tk_widget().pack(fill='both', expand=True)
        nav1 = NavigationToolbar2Tk(self.canvas_single, chart_frame)
        nav1.update()

        # Overlay chart
        overlay_chart = ttk.Frame(right_nb)
        right_nb.add(overlay_chart, text="Overlay Chart")

        self.fig_overlay = plt.Figure(figsize=(10, 5), dpi=100)
        self.fig_overlay.patch.set_facecolor('#FFFFFF')
        self.canvas_overlay = FigureCanvasTkAgg(self.fig_overlay, master=overlay_chart)
        self.canvas_overlay.get_tk_widget().pack(fill='both', expand=True)
        nav2 = NavigationToolbar2Tk(self.canvas_overlay, overlay_chart)
        nav2.update()

        # Peak report
        peak_frame = ttk.Frame(right_nb)
        right_nb.add(peak_frame, text="Peak Analysis")

        peak_cols = ('component', 'height', 'ret_time', 'fwhm', 'base_width', 'resolution')
        self.peak_tree = ttk.Treeview(peak_frame, columns=peak_cols,
                                       show='headings', height=10)
        self.peak_tree.heading('component', text='Component')
        self.peak_tree.heading('height', text='Height (mM)')
        self.peak_tree.heading('ret_time', text='Ret. Time (s)')
        self.peak_tree.heading('fwhm', text='FWHM (s)')
        self.peak_tree.heading('base_width', text='Base Width (s)')
        self.peak_tree.heading('resolution', text='Resolution Rs')
        for c in peak_cols:
            self.peak_tree.column(c, width=100)
        self.peak_tree.pack(fill='both', expand=True, padx=5, pady=5)

        self._refresh_results()

    # ============================================================
    # Result List
    # ============================================================

    def _refresh_results(self):
        """Refresh the result list"""
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        import datetime
        results = self.db.get_results()
        for r in results:
            created = ""
            if r.get('created_at'):
                created = datetime.datetime.fromtimestamp(
                    r['created_at']).strftime('%Y-%m-%d %H:%M')
            self.result_tree.insert('', 'end', iid=str(r['id']),
                                    values=(r['id'], r['result_name'], created))

    def _on_result_select(self, event):
        """Display chart and report on result selection"""
        sel = self.result_tree.selection()
        if not sel:
            return
        result_id = int(sel[0])
        result = self.db.get_result_data(result_id)
        if not result:
            return

        self._display_single_result(result)

    def _display_single_result(self, result: dict):
        """Display a single result"""
        time_data = result.get('time_data')
        conc_data = result.get('concentration_data')
        config_json = result.get('config_json')

        if time_data is None or conc_data is None or not config_json:
            return

        try:
            config = ProcessConfig._from_dict(json.loads(config_json))
        except Exception:
            return

        # Plot chromatogram
        comp_mgr = config.method_settings.component_manager
        peaks = self.analyzer.analyze(
            time_data, conc_data,
            comp_mgr.names, comp_mgr.protein_indices)

        self.plotter.plot_chromatogram(
            config=config,
            time=time_data,
            concentration=conc_data,
            save_path=None, show=False,
            peaks=peaks, fig=self.fig_single)
        self.canvas_single.draw()

        # Update peak report
        report = self.analyzer.generate_report(peaks)
        self._update_peak_report(report)

    def _update_peak_report(self, report: dict):
        """Update peak report table"""
        for item in self.peak_tree.get_children():
            self.peak_tree.delete(item)

        peaks = report.get('peaks', [])
        resolutions = report.get('resolutions', [])

        for p in peaks:
            rs_str = ""
            for r in resolutions:
                if r['pair'].startswith(p['component']):
                    rs_str = f"{r['Rs']:.3f}"
                    break

            self.peak_tree.insert('', 'end', values=(
                p['component'],
                f"{p['peak_height_mM']:.4f}",
                f"{p['retention_time']:.4f}",
                f"{p['fwhm']:.4f}",
                f"{p['baseline_width']:.4f}",
                rs_str))

    # ============================================================
    # Overlay
    # ============================================================

    def _add_to_overlay(self):
        """Add selected result to Overlay"""
        sel = self.result_tree.selection()
        if not sel:
            messagebox.showwarning("Notice", "Please select a result first")
            return

        for s in sel:
            result_id = int(s)
            if any(d['id'] == result_id for d in self._overlay_datasets):
                continue

            result = self.db.get_result_data(result_id)
            if result and result.get('time_data') is not None:
                config = None
                try:
                    config = ProcessConfig._from_dict(
                        json.loads(result['config_json']))
                except Exception:
                    pass

                ds = {
                    'id': result_id,
                    'name': result.get('result_name', f'Result #{result_id}'),
                    'time': result['time_data'],
                    'concentration': result['concentration_data'],
                    'components': config.method_settings.components if config else [],
                    'config': config,
                }
                self._overlay_datasets.append(ds)

        self.lbl_overlay_count.config(
            text=f"Added: {len(self._overlay_datasets)} results")

    def _clear_overlay(self):
        self._overlay_datasets.clear()
        self.lbl_overlay_count.config(text="Added: 0 results")
        self.fig_overlay.clear()
        self.canvas_overlay.draw()

    def _show_overlay(self):
        """Show Overlay comparison chart"""
        if not self._overlay_datasets:
            messagebox.showwarning("Notice", "Please add results to Overlay first")
            return

        align_mode = self.var_align_mode.get()

        self.fig_overlay.clear()
        ax = self.fig_overlay.add_subplot(111)
        ax.set_facecolor('#FFFFFF')

        colors_cycle = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
                        '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']

        for i, ds in enumerate(self._overlay_datasets):
            time_arr = ds['time'].copy()
            conc = ds['concentration']
            name = ds['name']
            comps = ds['components']
            color = colors_cycle[i % len(colors_cycle)]

            # Alignment
            if align_mode == 'injection' and ds.get('config'):
                config = ds['config']
                for step in config.sequence:
                    if step.step_type == 'Load':
                        offset = 0.0
                        for s in config.sequence:
                            if s is step:
                                break
                            offset += s.duration_seconds
                        time_arr = time_arr - offset
                        break

            elif align_mode == 'peak':
                protein_indices = [j for j, c in enumerate(comps)
                                   if c.lower() != 'salt']
                if protein_indices:
                    total = np.sum(conc[:, protein_indices], axis=1)
                    peak_idx = np.argmax(total)
                    time_arr = time_arr - time_arr[peak_idx]

            # Plot total protein curve
            protein_indices = [j for j, c in enumerate(comps)
                               if c.lower() != 'salt']
            if protein_indices:
                total = np.sum(conc[:, protein_indices], axis=1)
                ax.plot(time_arr, total, color=color, linewidth=1.5,
                        label=f"{name} (Total Protein)", alpha=0.9)

        ax.set_xlabel('Time / s', fontsize=11)
        ax.set_ylabel('Protein Concentration (mM)', fontsize=11)
        ax.set_title('Overlay Comparison', fontsize=13, fontweight='bold')
        ax.legend(fontsize=8, loc='upper right')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(bottom=0)

        self.fig_overlay.tight_layout()
        self.canvas_overlay.draw()

    # ============================================================
    # CSV Export
    # ============================================================

    def _on_export_csv(self):
        """Export UV data of selected result as CSV"""
        sel = self.result_tree.selection()
        if not sel:
            messagebox.showwarning("Notice", "Please select a result first")
            return

        result_id = int(sel[0])
        result = self.db.get_result_data(result_id)
        if not result or result.get('time_data') is None:
            return

        initial_dir = os.path.expanduser('~')

        path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv')],
            initialdir=initial_dir,
            initialfile=f"{result.get('result_name', 'result')}.csv")
        if not path:
            return

        try:
            config = ProcessConfig._from_dict(json.loads(result['config_json']))
            comps = config.method_settings.components
        except Exception:
            comps = [f"Comp_{i}" for i in range(result['concentration_data'].shape[1])]

        export_chromatogram_csv(
            path, result['time_data'], result['concentration_data'],
            comps, x_unit='seconds')
        messagebox.showinfo("Success", f"UV data exported:" + chr(10) + f"{path}")

    def _on_export_peak_csv(self):
        """Export peak report as CSV"""
        sel = self.result_tree.selection()
        if not sel:
            messagebox.showwarning("Notice", "Please select a result first")
            return

        result_id = int(sel[0])
        result = self.db.get_result_data(result_id)
        if not result:
            return

        peak_json = result.get('peak_report_json', '')
        if peak_json:
            report = json.loads(peak_json)
        else:
            config = ProcessConfig._from_dict(json.loads(result['config_json']))
            comp_mgr = config.method_settings.component_manager
            peaks = self.analyzer.analyze(
                result['time_data'], result['concentration_data'],
                comp_mgr.names, comp_mgr.protein_indices)
            report = self.analyzer.generate_report(peaks)

        initial_dir = os.path.expanduser('~')

        path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv')],
            initialdir=initial_dir,
            initialfile=f"{result.get('result_name', 'peaks')}_peaks.csv")
        if not path:
            return

        export_peak_report_csv(path, report)
        messagebox.showinfo("Success", f"Peak report exported:" + chr(10) + f"{path}")

    def _export_overlay_csv(self):
        """Export Overlay data as CSV"""
        if not self._overlay_datasets:
            messagebox.showwarning("Notice", "Please add results to Overlay first")
            return

        initial_dir = os.path.expanduser('~')

        path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv')],
            initialdir=initial_dir,
            initialfile='overlay_comparison.csv')
        if not path:
            return

        export_overlay_csv(path, self._overlay_datasets)
        messagebox.showinfo("Success", f"Overlay data exported:" + chr(10) + f"{path}")

    def _on_delete_result(self):
        """Delete selected result"""
        sel = self.result_tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("Confirm", "Delete selected result(s)?"):
            return

        for s in sel:
            self.db.delete_result(int(s))
        self._refresh_results()
