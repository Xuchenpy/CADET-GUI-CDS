"""
Method Run Module

Features:
  - Run current edited method / load from database
  - Async simulation (background thread)
  - Real-time progress display
  - Real-time chromatogram update
  - Peak analysis report
  - Run Scouting batch
  - Run Method Queue
  - Auto-save results to database
"""

import sys
import os
import json
import copy
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

_app_dir = os.path.dirname(os.path.abspath(__file__))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from config_models import ProcessConfig, create_default_config, NumpyEncoder, apply_parameter_value
from simulation_engine import SimulationEngine
from visualization import ChromatogramPlotter
from peak_analysis import PeakAnalyzer

from styles import (
    PRIMARY_TEAL, DARK_NAVY, BG_MAIN, BG_CONTENT, BG_HEADER,
    TEXT_PRIMARY, TEXT_LIGHT, TEXT_SECONDARY,
    FONT_TITLE, FONT_SUBTITLE, FONT_BODY, FONT_SMALL, FONT_MONO,
    COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING,
    TOOLBAR_BTN_BG
)


class MethodRunModule(ttk.Frame):

    def __init__(self, parent, db_manager, app_context,
                 get_editor_config=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.db = db_manager
        self.ctx = app_context
        self.get_editor_config = get_editor_config
        self.engine = SimulationEngine()
        self.plotter = ChromatogramPlotter()
        self.analyzer = PeakAnalyzer()
        self._is_running = False
        self._last_data = None
        self._last_config = None
        self._build_ui()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(self, style='Toolbar.TFrame')
        toolbar.grid(row=0, column=0, sticky='ew')
        lbl = tk.Label(toolbar, text="  Method Run", bg=DARK_NAVY,
                        fg=TEXT_LIGHT, font=FONT_SUBTITLE)
        lbl.pack(side='left', padx=10, pady=6)
        btn_frame = tk.Frame(toolbar, bg=DARK_NAVY)
        btn_frame.pack(side='right', padx=10)
        self.btn_run = tk.Button(
            btn_frame, text="Run Current", command=self._on_run_current,
            bg='#4CAF50', fg=TEXT_LIGHT, font=FONT_BODY,
            padx=12, pady=3, relief='raised', bd=1,
            activebackground='#66BB6A', activeforeground=TEXT_LIGHT)
        self.btn_run.pack(side='left', padx=5)
        self.btn_run_saved = tk.Button(
            btn_frame, text="Run Saved", command=self._on_run_saved,
            bg=TOOLBAR_BTN_BG, fg=TEXT_LIGHT, font=FONT_SMALL,
            padx=8, pady=3, relief='raised', bd=1,
            activebackground=PRIMARY_TEAL, activeforeground=TEXT_LIGHT)
        self.btn_run_saved.pack(side='left', padx=3)
        self.btn_stop = tk.Button(
            btn_frame, text="Stop", command=self._on_stop,
            bg='#D32F2F', fg=TEXT_LIGHT, font=FONT_SMALL,
            padx=8, pady=3, relief='raised', bd=1, state='disabled',
            activebackground='#E57373', activeforeground=TEXT_LIGHT)
        self.btn_stop.pack(side='left', padx=3)
        main = ttk.PanedWindow(self, orient='vertical')
        main.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        chart_frame = ttk.Frame(main)
        main.add(chart_frame, weight=3)
        self.fig = plt.Figure(figsize=(12, 5), dpi=100)
        self.fig.patch.set_facecolor('#FFFFFF')
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        nav_frame = ttk.Frame(chart_frame)
        nav_frame.pack(fill='x')
        self.nav_toolbar = NavigationToolbar2Tk(self.canvas, nav_frame)
        self.nav_toolbar.update()
        bottom = ttk.Notebook(main)
        main.add(bottom, weight=1)
        log_frame = ttk.Frame(bottom)
        bottom.add(log_frame, text="Run Log")
        self.log_text = tk.Text(log_frame, height=8, font=FONT_MONO,
                                 bg=BG_CONTENT, fg=TEXT_PRIMARY, wrap='word')
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)
        log_sb = ttk.Scrollbar(log_frame, orient='vertical',
                                command=self.log_text.yview)
        log_sb.pack(side='right', fill='y')
        self.log_text.configure(yscrollcommand=log_sb.set)
        peak_frame = ttk.Frame(bottom)
        bottom.add(peak_frame, text="Peak Report")
        peak_cols = ('component', 'height', 'ret_time', 'fwhm', 'resolution')
        self.peak_tree = ttk.Treeview(peak_frame, columns=peak_cols,
                                       show='headings', height=6)
        self.peak_tree.heading('component', text='Component')
        self.peak_tree.heading('height', text='Height (mM)')
        self.peak_tree.heading('ret_time', text='Ret. Time (s)')
        self.peak_tree.heading('fwhm', text='FWHM (s)')
        self.peak_tree.heading('resolution', text='Rs')
        self.peak_tree.pack(fill='both', expand=True, padx=5, pady=5)
        batch_frame = ttk.Frame(bottom)
        bottom.add(batch_frame, text="Scouting / Queue")
        batch_cols = ('run', 'variables', 'status', 'result_id')
        self.batch_tree = ttk.Treeview(batch_frame, columns=batch_cols,
                                        show='headings', height=6)
        self.batch_tree.heading('run', text='#')
        self.batch_tree.heading('variables', text='Variables')
        self.batch_tree.heading('status', text='Status')
        self.batch_tree.heading('result_id', text='Result ID')
        self.batch_tree.pack(fill='both', expand=True, padx=5, pady=5)
        status_bar = ttk.Frame(self, style='Header.TFrame')
        status_bar.grid(row=2, column=0, sticky='ew')
        self.lbl_status = ttk.Label(status_bar, text="Ready",
                                     style='Status.TLabel')
        self.lbl_status.pack(side='left', padx=10, pady=3)
        self.progress = ttk.Progressbar(status_bar, mode='indeterminate',
                                         length=200)
        self.progress.pack(side='right', padx=10, pady=3)

    def _log(self, msg: str):
        import datetime
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        self.log_text.insert('end', f"[{ts}] {msg}//n")
        self.log_text.see('end')

    def _set_running(self, running: bool):
        self._is_running = running
        state_run = 'disabled' if running else 'normal'
        state_stop = 'normal' if running else 'disabled'
        self.btn_run.config(state=state_run)
        self.btn_run_saved.config(state=state_run)
        self.btn_stop.config(state=state_stop)
        if running:
            self.progress.start(15)
        else:
            self.progress.stop()

    def _on_run_current(self):
        if self._is_running:
            return
        config = None
        if self.get_editor_config:
            config = self.get_editor_config()
        if config is None:
            config = create_default_config()
            self._log("Using default config")
        self._run_simulation(config)

    def _on_run_saved(self):
        methods = self.db.get_methods()
        if not methods:
            messagebox.showinfo("Notice", "No saved methods")
            return
        dlg = tk.Toplevel(self)
        dlg.title("Select Method to Run")
        dlg.geometry("450x300")
        dlg.transient(self)
        dlg.grab_set()
        cols = ('id', 'name')
        tree = ttk.Treeview(dlg, columns=cols, show='headings', height=8)
        tree.heading('id', text='ID')
        tree.heading('name', text='Method Name')
        tree.column('id', width=50)
        tree.column('name', width=300)
        tree.pack(fill='both', expand=True, padx=10, pady=10)
        for m in methods:
            tree.insert('', 'end', iid=str(m['id']),
                        values=(m['id'], m['method_name']))
        def do_run():
            sel = tree.selection()
            if not sel:
                return
            mid = int(sel[0])
            method = self.db.get_method(mid)
            if method:
                data = json.loads(method['config_json'])
                config = ProcessConfig._from_dict(data)
                dlg.destroy()
                self._run_simulation(config, method_id=mid)
        ttk.Button(dlg, text="Run", command=do_run,
                   style='Accent.TButton').pack(pady=5)

    def _on_stop(self):
        if self.engine.is_running:
            self.engine.stop()
            self._log("Stopping simulation...")

    def _run_simulation(self, config: ProcessConfig, method_id: int = None):
        self._set_running(True)
        self._last_config = config
        self._log(f"Starting: {config.process_name}")
        self._log(f"  Components: {config.method_settings.components}")
        self._log(f"  Steps: {len(config.sequence)}")
        self._log(f"  Cycle time: {config.calculate_cycle_time():.1f} s")
        self.lbl_status.config(text="Running...")
        def on_complete(results, data):
            self._last_data = data
            self.after(0, lambda: self._on_sim_complete(config, data, method_id))
        def on_error(e):
            self.after(0, lambda: self._on_sim_error(e))
        def on_progress(msg):
            self.after(0, lambda: self._log(msg))
        self.engine.simulate_async(
            config,
            on_complete=on_complete,
            on_error=on_error,
            on_progress=on_progress)

    def _on_sim_complete(self, config, data, method_id=None):
        self._set_running(False)
        self._log("Simulation complete!")
        self._log(f"  Data points: {len(data['time'])}")
        self._log(f"  Concentration matrix: {data['concentration'].shape}")
        self.lbl_status.config(text="Complete")
        comp_mgr = config.method_settings.component_manager
        peaks = self.analyzer.analyze(
            data['time'], data['concentration'],
            comp_mgr.names, comp_mgr.protein_indices)
        report = self.analyzer.generate_report(peaks)
        self.plotter.plot_chromatogram(
            config=config,
            time=data['time'],
            concentration=data['concentration'],
            save_path=None,
            show=False,
            peaks=peaks,
            fig=self.fig)
        self.canvas.draw()
        self._update_peak_table(report)
        try:
            result_name = f"{config.process_name}_{time.strftime('%Y%m%d_%H%M%S')}"
            config_json = config.to_json()
            peak_json = json.dumps(report, ensure_ascii=False, cls=NumpyEncoder)
            result_id = self.db.save_result(
                result_name, config_json,
                data['time'], data['concentration'],
                peak_json, method_id=method_id)
            self._log(f"Result saved (ID: {result_id})")
        except Exception as e:
            self._log(f"Save result failed: {e}")

    def _on_sim_error(self, error):
        self._set_running(False)
        self._log(f"Simulation failed: {error}")
        self.lbl_status.config(text="Failed")
        messagebox.showerror("Simulation Failed", str(error))

    def _update_peak_table(self, report):
        for item in self.peak_tree.get_children():
            self.peak_tree.delete(item)
        peaks = report.get('peaks', [])
        resolutions = report.get('resolutions', [])
        for i, p in enumerate(peaks):
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
                rs_str))

    def run_scouting(self, plan_id: int):
        plan_results = self.db.get_scouting_results(plan_id)
        if not plan_results:
            self._log("Scouting plan has no runs")
            return
        plans = self.db.get_scouting_plans()
        plan = None
        for p in plans:
            if p['id'] == plan_id:
                plan = p
                break
        if not plan:
            return
        base_method = self.db.get_method(plan['method_id'])
        if not base_method:
            self._log("Scouting base method not found")
            return
        base_data = json.loads(base_method['config_json'])
        variables_info = json.loads(plan['variables_json'])
        self._log(f"Starting Scouting: {plan.get('plan_name', '')} "
                  f"({len(plan_results)} runs)")
        self.db.update_scouting_plan_status(plan_id, 'running')
        for item in self.batch_tree.get_children():
            self.batch_tree.delete(item)
        def run_batch():
            for sr in plan_results:
                if not self._is_running:
                    break
                var_vals = json.loads(sr['variable_values_json'])
                run_idx = sr['run_index']
                self.after(0, lambda ri=run_idx, vv=str(var_vals):
                           self.batch_tree.insert('', 'end', values=(
                               ri, vv, 'Running', '')))
                config = ProcessConfig._from_dict(copy.deepcopy(base_data))
                self._apply_scouting_variables(config, var_vals)
                try:
                    results = self.engine.simulate(config)
                    data = self.engine.get_outlet_data(results)
                    comp_mgr = config.method_settings.component_manager
                    peaks = self.analyzer.analyze(
                        data['time'], data['concentration'],
                        comp_mgr.names, comp_mgr.protein_indices)
                    report = self.analyzer.generate_report(peaks)
                    result_name = f"Scout_{plan_id}_{run_idx}"
                    config_json = config.to_json()
                    peak_json = json.dumps(report, ensure_ascii=False, cls=NumpyEncoder)
                    result_id = self.db.save_result(
                        result_name, config_json,
                        data['time'], data['concentration'], peak_json)
                    self.db.update_scouting_result(sr['id'], result_id, 'completed')
                    self.after(0, lambda ri=run_idx:
                               self._log(f"  Scouting #{ri} done"))
                except Exception as e:
                    self.db.update_scouting_result(sr['id'], None, 'failed')
                    self.after(0, lambda ri=run_idx, err=str(e):
                               self._log(f"  Scouting #{ri} failed: {err}"))
            self.db.update_scouting_plan_status(plan_id, 'completed')
            self.after(0, lambda: self._log("Scouting batch complete"))
            self.after(0, lambda: self._set_running(False))
        self._set_running(True)
        threading.Thread(target=run_batch, daemon=True).start()

    def _apply_scouting_variables(self, config: ProcessConfig, var_vals: dict):
        for param_path, value in var_vals.items():
            try:
                value = float(value)
                apply_parameter_value(config, param_path, value)
            except Exception:
                pass

    def run_queue(self, queue_id: int):
        items = self.db.get_queue_items(queue_id)
        if not items:
            self._log("Queue is empty")
            return
        self._log(f"Starting method queue ({len(items)} methods)")
        self.db.update_queue_status(queue_id, 'running')
        def run_queue_worker():
            for qi in items:
                if not self._is_running:
                    break
                method = self.db.get_method(qi['method_id'])
                if not method:
                    self.after(0, lambda n=qi.get('method_name', '?'):
                               self._log(f"  Method {n} not found, skipping"))
                    self.db.update_queue_item_status(qi['id'], 'skipped')
                    continue
                self.db.update_queue_item_status(qi['id'], 'running')
                self.after(0, lambda n=method['method_name']:
                           self._log(f"  Running: {n}"))
                data = json.loads(method['config_json'])
                config = ProcessConfig._from_dict(data)
                try:
                    results = self.engine.simulate(config)
                    sim_data = self.engine.get_outlet_data(results)
                    comp_mgr = config.method_settings.component_manager
                    peaks = self.analyzer.analyze(
                        sim_data['time'], sim_data['concentration'],
                        comp_mgr.names, comp_mgr.protein_indices)
                    report = self.analyzer.generate_report(peaks)
                    result_name = f"Queue_{queue_id}_{qi['position']}"
                    config_json = config.to_json()
                    peak_json = json.dumps(report, ensure_ascii=False, cls=NumpyEncoder)
                    result_id = self.db.save_result(
                        result_name, config_json,
                        sim_data['time'], sim_data['concentration'], peak_json)
                    self.db.update_queue_item_status(qi['id'], 'completed', result_id)
                    self.after(0, lambda n=method['method_name']:
                               self._log(f"  Method {n} done"))
                except Exception as e:
                    self.db.update_queue_item_status(qi['id'], 'failed')
                    self.after(0, lambda n=method['method_name'], err=str(e):
                               self._log(f"  Method {n} failed: {err}"))
            self.db.update_queue_status(queue_id, 'completed')
            self.after(0, lambda: self._log("Queue execution complete"))
            self.after(0, lambda: self._set_running(False))
        self._set_running(True)
        threading.Thread(target=run_queue_worker, daemon=True).start()

    def get_last_data(self):
        return self._last_data, self._last_config
