"""
Method Editor Module v9

Features:
  - Method tab: left params panel + right inline step cards
  - Inline step editing via StepCard widgets
  - Scouting: batch parameter sweep
  - Method Queue: sequential run management
  - Method save / load (database + JSON)
"""

import sys
import os
import json
import copy
import math
from typing import Optional, List, Dict
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from itertools import product as itertools_product

_app_dir = os.path.dirname(os.path.abspath(__file__))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from config_models import (
    ProcessConfig, MethodSettings, ComponentManager, SMAParams,
    ColumnParams, InletParams, EquilibrationStep, LoadStep,
    WashStep, ElutionStep, StepModule, NumpyEncoder,
    create_default_config, extract_numeric_parameters, apply_parameter_value
)
from unit_converter import UnitConverter
from styles import (
    PRIMARY_TEAL, DARK_NAVY, BG_MAIN, BG_CONTENT, BG_HEADER,
    BG_SIDEBAR, BORDER_COLOR, TEXT_PRIMARY, TEXT_LIGHT, TEXT_SECONDARY,
    STEP_COLORS, STEP_HOVER_COLORS, FONT_TITLE, FONT_SUBTITLE, FONT_BODY,
    FONT_SMALL, FONT_MONO, FONT_TABLE, FONT_BUTTON, COLOR_SUCCESS,
    COLOR_WARNING,
    TOOLBAR_BTN_BG
)


STEP_FACTORY = {
    'Equilibration': EquilibrationStep,
    'Load': LoadStep,
    'Wash': WashStep,
    'Elution': ElutionStep,
}

STEP_DISPLAY_NAMES = {
    'Equilibration': 'Equilibration',
    'Load': 'Sample Application',
    'Wash': 'Column Wash',
    'Elution': 'Elution',
}


class MethodEditorModule(ttk.Frame):

    def __init__(self, parent, db_manager, app_context, **kwargs):
        super().__init__(parent, **kwargs)
        self.db = db_manager
        self.ctx = app_context
        self.config = create_default_config()
        self._current_method_id = None
        self._step_card_vars = []
        self._step_cards_frame = None
        self._cards_canvas = None
        self._cards_canvas_window = None
        self._display_unit = tk.StringVar(value='seconds')
        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(self, style='Toolbar.TFrame')
        toolbar.grid(row=0, column=0, sticky='ew')
        self._build_toolbar(toolbar)
        self._notebook = ttk.Notebook(self)
        self._notebook.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        self._build_method_tab(self._notebook)
        self._build_scouting_tab(self._notebook)
        self._build_queue_tab(self._notebook)

    def _build_toolbar(self, parent):
        lbl = tk.Label(parent, text="  Method Editor", bg=DARK_NAVY,
                        fg=TEXT_LIGHT, font=FONT_SUBTITLE)
        lbl.pack(side='left', padx=10, pady=6)
        btn_frame = tk.Frame(parent, bg=DARK_NAVY)
        btn_frame.pack(side='right', padx=10)
        btns = [
            ("New", self._on_new_method),
            ("Open", self._on_load_method),
            ("Save", self._on_save_method),
            ("Save As", self._on_save_as_method),
            ("Delete", self._on_delete_method),
        ]
        for text, cmd in btns:
            b = tk.Button(btn_frame, text=text, command=cmd,
                          bg=TOOLBAR_BTN_BG, fg=TEXT_LIGHT, relief='raised',
                          font=FONT_SMALL, padx=8, pady=2, bd=1,
                          activebackground=PRIMARY_TEAL, activeforeground=TEXT_LIGHT)
            b.pack(side='left', padx=3)

    def _build_method_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Method")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        pw = ttk.PanedWindow(frame, orient='horizontal')
        pw.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        left_frame = ttk.Frame(pw)
        self._build_params_panel(left_frame)
        pw.add(left_frame, weight=2)
        right_frame = ttk.Frame(pw)
        self._build_steps_panel(right_frame)
        pw.add(right_frame, weight=3)

    def _build_params_panel(self, parent):
        canvas = tk.Canvas(parent, bg=BG_CONTENT, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind('<Configure>',
                          lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        self._params_cw = canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        def _mw(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind('<MouseWheel>', _mw)
        scroll_frame.bind('<MouseWheel>', _mw)
        canvas.bind('<Configure>',
                    lambda e: canvas.itemconfigure(self._params_cw, width=e.width))
        pf = ttk.LabelFrame(scroll_frame, text="Process Info")
        pf.pack(fill='x', padx=10, pady=5)
        pf.columnconfigure(1, weight=1)
        ttk.Label(pf, text='Method Name:').grid(row=0, column=0, sticky='e', padx=5, pady=3)
        self.var_process_name = tk.StringVar(value=self.config.process_name)
        ttk.Entry(pf, textvariable=self.var_process_name).grid(
            row=0, column=1, sticky='ew', padx=5, pady=3)
        ttk.Label(pf, text='Project:').grid(row=1, column=0, sticky='e', padx=5, pady=3)
        self.var_project_name = tk.StringVar(value=self.config.project_name)
        ttk.Entry(pf, textvariable=self.var_project_name).grid(
            row=1, column=1, sticky='ew', padx=5, pady=3)
        ttk.Label(pf, text='Resin:').grid(row=2, column=0, sticky='e', padx=5, pady=3)
        self.var_filler_name = tk.StringVar(value=self.config.filler_name)
        ttk.Entry(pf, textvariable=self.var_filler_name).grid(
            row=2, column=1, sticky='ew', padx=5, pady=3)
        self._build_component_system(scroll_frame)
        col_f = ttk.LabelFrame(scroll_frame, text='Column Parameters')
        col_f.pack(fill='x', padx=10, pady=5)
        col_f.columnconfigure(1, weight=1)
        self.col_vars = {}
        col_params = [
            ('length', 'Length (m):', '0.014'),
            ('diameter', 'Diameter (m):', '0.02'),
            ('bed_porosity', 'Bed Porosity:', '0.37'),
            ('particle_radius', 'Particle Radius (m):', '4.5e-5'),
            ('particle_porosity', 'Particle Porosity:', '0.75'),
            ('axial_dispersion', 'Axial Dispersion:', '5.75e-8'),
        ]
        for i, (key, label, default) in enumerate(col_params):
            ttk.Label(col_f, text=label).grid(row=i, column=0, sticky='e', padx=5, pady=2)
            var = tk.StringVar(value=default)
            self.col_vars[key] = var
            ttk.Entry(col_f, textvariable=var, font=FONT_MONO).grid(
                row=i, column=1, sticky='ew', padx=5, pady=2)
        self.lbl_col_vol = ttk.Label(col_f, text='Column Volume: -- mL', font=FONT_BODY)
        self.lbl_col_vol.grid(row=len(col_params), column=0, columnspan=2,
                               sticky='w', padx=10, pady=5)
        flow_f = ttk.LabelFrame(scroll_frame, text='Flow Rate')
        flow_f.pack(fill='x', padx=10, pady=5)
        flow_f.columnconfigure(1, weight=1)
        ttk.Label(flow_f, text='Flow Rate (mL/min):').grid(
            row=0, column=0, sticky='e', padx=5, pady=3)
        self.var_flow_rate = tk.StringVar(value="4.01")
        ttk.Entry(flow_f, textvariable=self.var_flow_rate, font=FONT_MONO).grid(
            row=0, column=1, sticky='ew', padx=5, pady=3)
        ttk.Label(flow_f, text='Initial Salt (mM):').grid(
            row=1, column=0, sticky='e', padx=5, pady=3)
        self.var_init_salt = tk.StringVar(value="50.0")
        ttk.Entry(flow_f, textvariable=self.var_init_salt, font=FONT_MONO).grid(
            row=1, column=1, sticky='ew', padx=5, pady=3)
        self._build_sma_table(scroll_frame)

    def _build_component_system(self, parent):
        cf = ttk.LabelFrame(parent, text='Component System')
        cf.pack(fill='x', padx=10, pady=5)
        cf.columnconfigure(0, weight=1)
        btn_frame = ttk.Frame(cf)
        btn_frame.pack(fill='x', padx=5, pady=3)
        ttk.Button(btn_frame, text='+', command=self._add_component,
                   style='Small.TButton', width=3).pack(side='left', padx=2)
        ttk.Button(btn_frame, text='-', command=self._remove_component,
                   style='Small.TButton', width=3).pack(side='left', padx=2)
        ttk.Button(btn_frame, text='Rename', command=self._rename_component,
                   style='Small.TButton').pack(side='left', padx=2)
        list_frame = ttk.Frame(cf)
        list_frame.pack(fill='x', padx=5, pady=3)
        self.comp_listbox = tk.Listbox(list_frame, height=5, font=FONT_BODY,
                                        selectmode='single')
        self.comp_listbox.pack(side='left', fill='x', expand=True)
        sb = ttk.Scrollbar(list_frame, orient='vertical',
                           command=self.comp_listbox.yview)
        sb.pack(side='right', fill='y')
        self.comp_listbox.configure(yscrollcommand=sb.set)

    def _build_sma_table(self, parent):
        sma_f = ttk.LabelFrame(parent, text='SMA Binding Model')
        sma_f.pack(fill='x', padx=10, pady=5)
        sma_f.columnconfigure(0, weight=1)
        self._sma_frame = sma_f
        cap_frame = ttk.Frame(sma_f)
        cap_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(cap_frame, text='Capacity (Lambda):').pack(side='left')
        self.var_sma_capacity = tk.StringVar(value="1200.0")
        ttk.Entry(cap_frame, textvariable=self.var_sma_capacity,
                  font=FONT_MONO, width=12).pack(side='left', padx=5)
        self._sma_table_container = ttk.Frame(sma_f)
        self._sma_table_container.pack(fill='x', padx=5, pady=3)
        self.sma_tree = None

    def _build_steps_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        unit_f = ttk.LabelFrame(parent, text='Display Units')
        unit_f.grid(row=0, column=0, sticky='ew', padx=5, pady=5)
        for val, text in [('seconds', 'Time (s)'), ('mL', 'Volume (mL)'), ('CV', 'Column Volumes (CV)')]:
            ttk.Radiobutton(unit_f, text=text, variable=self._display_unit,
                           value=val, command=self._on_unit_change).pack(
                side='left', padx=10, pady=5)
        seq_f = ttk.LabelFrame(parent, text='Process Sequence')
        seq_f.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        seq_f.columnconfigure(0, weight=1)
        seq_f.rowconfigure(1, weight=1)
        top_bar = ttk.Frame(seq_f)
        top_bar.grid(row=0, column=0, sticky='ew', padx=5, pady=5)
        self._btn_add_step = ttk.Button(top_bar, text='+ Add Step',
                                         command=self._on_add_step_menu,
                                         style='Accent.TButton')
        self._btn_add_step.pack(side='left', padx=5)
        self.lbl_total_time = ttk.Label(top_bar, text='Total: 0 s', font=FONT_BODY)
        self.lbl_total_time.pack(side='right', padx=10)
        self.lbl_method_name = ttk.Label(top_bar, text='', font=FONT_SMALL,
                                          foreground=TEXT_SECONDARY)
        self.lbl_method_name.pack(side='right', padx=5)
        card_container = ttk.Frame(seq_f)
        card_container.grid(row=1, column=0, sticky='nsew')
        card_container.columnconfigure(0, weight=1)
        card_container.rowconfigure(0, weight=1)
        self._cards_canvas = tk.Canvas(card_container, bg=BG_CONTENT,
                                        highlightthickness=0)
        cards_sb = ttk.Scrollbar(card_container, orient='vertical',
                                  command=self._cards_canvas.yview)
        self._step_cards_frame = ttk.Frame(self._cards_canvas)
        self._step_cards_frame.bind('<Configure>',
            lambda e: self._cards_canvas.configure(scrollregion=self._cards_canvas.bbox('all')))
        self._cards_canvas_window = self._cards_canvas.create_window(
            (0, 0), window=self._step_cards_frame, anchor='nw')
        self._cards_canvas.configure(yscrollcommand=cards_sb.set)
        self._cards_canvas.grid(row=0, column=0, sticky='nsew')
        cards_sb.grid(row=0, column=1, sticky='ns')
        def _mw(event):
            self._cards_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._cards_canvas.bind('<MouseWheel>', _mw)
        self._step_cards_frame.bind('<MouseWheel>', _mw)
        self._cards_canvas.bind('<Configure>',
            lambda e: self._cards_canvas.itemconfigure(
                self._cards_canvas_window, width=e.width))

    def _rebuild_step_cards(self):
        for w in self._step_cards_frame.winfo_children():
            w.destroy()
        self._step_card_vars.clear()
        for i, step in enumerate(self.config.sequence):
            self._create_step_card(self._step_cards_frame, i, step)
        total = self.config.calculate_cycle_time()
        unit = self._display_unit.get()
        if unit == 'seconds':
            self.lbl_total_time.config(text=f"Total: {total:.1f} s")
        elif unit == 'mL':
            flow = self.config.method_settings.inlet_params.flow_rate_ml_min
            vol = total * flow / 60.0
            self.lbl_total_time.config(text=f"Total: {vol:.2f} mL")
        elif unit == 'CV':
            flow = self.config.method_settings.inlet_params.flow_rate_ml_min
            cv_vol = self.config.method_settings.column_params.column_volume_ml
            if cv_vol > 0:
                cv = (total * flow / 60.0) / cv_vol
                self.lbl_total_time.config(text=f"Total: {cv:.2f} CV")
            else:
                self.lbl_total_time.config(text="Total: -- CV")
        self.lbl_method_name.config(text=self.config.process_name)

    def _create_step_card(self, parent, idx, step):
        step_type = step.step_type
        color = STEP_COLORS.get(step_type, '#CCCCCC')
        card = tk.Frame(parent, bd=1, relief='groove', bg=BG_CONTENT)
        card.pack(fill='x', padx=5, pady=3)
        header = tk.Frame(card, bg=color)
        header.pack(fill='x')
        lbl_title = tk.Label(header, text=f"[{idx+1}] {step.display_name}",
                              bg=color, fg=TEXT_PRIMARY, font=FONT_SUBTITLE, anchor='w')
        lbl_title.pack(side='left', padx=8, pady=4)
        btn_del = tk.Button(header, text="X", bg=color, fg=TEXT_PRIMARY,
                             relief='flat', font=FONT_SMALL, cursor='hand2',
                             command=lambda i=idx: self._delete_step_by_index(i))
        btn_del.pack(side='right', padx=5, pady=2)
        body = ttk.Frame(card)
        body.pack(fill='x', padx=8, pady=5)
        body.columnconfigure(1, weight=1)
        vars_dict = {}
        row = 0
        ttk.Label(body, text='Duration:').grid(row=row, column=0, sticky='e', padx=5, pady=2)
        dur_display = self._seconds_to_display(step.duration_seconds)
        var_dur = tk.StringVar(value=dur_display)
        vars_dict['duration'] = var_dur
        dur_frame = ttk.Frame(body)
        dur_frame.grid(row=row, column=1, sticky='ew', padx=5, pady=2)
        ttk.Entry(dur_frame, textvariable=var_dur, font=FONT_MONO, width=12).pack(side='left')
        ttk.Label(dur_frame, text=self._unit_suffix(), font=FONT_SMALL,
                  foreground=TEXT_SECONDARY).pack(side='left', padx=3)
        row += 1
        comps = self.config.method_settings.components
        conc_vals = []
        for ci in range(len(comps)):
            conc_vals.append(f"{step.concentration[ci]:.2f}" if ci < len(step.concentration) else '0.0')
        conc_str = ', '.join(conc_vals)
        var_conc = tk.StringVar(value=conc_str)
        vars_dict['concentration'] = var_conc
        conc_label = 'Conc [' + ','.join(comps) + ']:'
        ttk.Label(body, text=conc_label).grid(row=row, column=0, sticky='e', padx=5, pady=2)
        ttk.Entry(body, textvariable=var_conc, font=FONT_MONO).grid(
            row=row, column=1, sticky='ew', padx=5, pady=2)
        row += 1
        if isinstance(step, ElutionStep):
            var_mode = tk.StringVar(value=step.elution_mode)
            vars_dict['elution_mode'] = var_mode
            ttk.Label(body, text='Mode:').grid(row=row, column=0, sticky='e', padx=5, pady=2)
            ttk.Combobox(body, textvariable=var_mode,
                         values=['linear_gradient', 'isocratic'],
                         state='readonly', width=15).grid(
                row=row, column=1, sticky='w', padx=5, pady=2)
            row += 1
            start_str = ', '.join(f"{x:.2f}" for x in step.start_concentration)
            var_start = tk.StringVar(value=start_str)
            vars_dict['start_conc'] = var_start
            ttk.Label(body, text='Start Conc:').grid(row=row, column=0, sticky='e', padx=5, pady=2)
            ttk.Entry(body, textvariable=var_start, font=FONT_MONO).grid(
                row=row, column=1, sticky='ew', padx=5, pady=2)
            row += 1
            end_str = ', '.join(f"{x:.2f}" for x in step.end_concentration)
            var_end = tk.StringVar(value=end_str)
            vars_dict['end_conc'] = var_end
            ttk.Label(body, text='End Conc:').grid(row=row, column=0, sticky='e', padx=5, pady=2)
            ttk.Entry(body, textvariable=var_end, font=FONT_MONO).grid(
                row=row, column=1, sticky='ew', padx=5, pady=2)
        self._step_card_vars.append(vars_dict)

    def _seconds_to_display(self, seconds):
        unit = self._display_unit.get()
        if unit == 'seconds':
            return f"{seconds:.1f}"
        elif unit == 'mL':
            flow = self.config.method_settings.inlet_params.flow_rate_ml_min
            return f"{seconds * flow / 60.0:.2f}"
        elif unit == 'CV':
            flow = self.config.method_settings.inlet_params.flow_rate_ml_min
            cv_vol = self.config.method_settings.column_params.column_volume_ml
            if cv_vol > 0:
                return f"{(seconds * flow / 60.0) / cv_vol:.3f}"
            return '0.000'
        return f"{seconds:.1f}"

    def _display_to_seconds(self, display_val):
        try:
            val = float(display_val)
        except ValueError:
            return 0.0
        unit = self._display_unit.get()
        if unit == 'seconds':
            return val
        elif unit == 'mL':
            flow = self.config.method_settings.inlet_params.flow_rate_ml_min
            if flow > 0:
                return val * 60.0 / flow
            return 0.0
        elif unit == 'CV':
            flow = self.config.method_settings.inlet_params.flow_rate_ml_min
            cv_vol = self.config.method_settings.column_params.column_volume_ml
            if flow > 0 and cv_vol > 0:
                return val * cv_vol * 60.0 / flow
            return 0.0
        return val

    def _unit_suffix(self):
        unit = self._display_unit.get()
        if unit == 'seconds': return 's'
        if unit == 'mL': return 'mL'
        return 'CV'

    def _on_unit_change(self, *args):
        self._sync_cards_to_config()
        self._rebuild_step_cards()

    def _sync_cards_to_config(self):
        for i, vars_dict in enumerate(self._step_card_vars):
            if i >= len(self.config.sequence):
                break
            step = self.config.sequence[i]
            dur_var = vars_dict.get('duration')
            if dur_var:
                step.duration_seconds = self._display_to_seconds(dur_var.get())
            conc_var = vars_dict.get('concentration')
            if conc_var:
                try:
                    step.concentration = [float(x.strip()) for x in conc_var.get().split(',')]
                except ValueError:
                    pass
            if isinstance(step, ElutionStep):
                mode_var = vars_dict.get('elution_mode')
                if mode_var:
                    step.elution_mode = mode_var.get()
                start_var = vars_dict.get('start_conc')
                if start_var:
                    try:
                        step.start_concentration = [float(x.strip()) for x in start_var.get().split(',')]
                    except ValueError:
                        pass
                end_var = vars_dict.get('end_conc')
                if end_var:
                    try:
                        step.end_concentration = [float(x.strip()) for x in end_var.get().split(',')]
                    except ValueError:
                        pass

    def _on_add_step_menu(self):
        menu = tk.Menu(self, tearoff=0)
        for step_type, display in STEP_DISPLAY_NAMES.items():
            menu.add_command(label=display,
                           command=lambda st=step_type: self._add_step(st))
        btn = self._btn_add_step
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        menu.post(x, y)

    def _add_step(self, step_type):
        self._sync_cards_to_config()
        n = self.config.method_settings.n_comp
        cls = STEP_FACTORY.get(step_type)
        if cls is None:
            return
        idx = len(self.config.sequence) + 1
        step = cls(step_id=f"{step_type.lower()}_{idx}")
        step.sync_conc_to_n(n)
        if isinstance(step, ElutionStep):
            while len(step.start_concentration) < n:
                step.start_concentration.append(0.0)
            while len(step.end_concentration) < n:
                step.end_concentration.append(0.0)
        self.config.sequence.append(step)
        self._rebuild_step_cards()

    def _delete_step_by_index(self, idx):
        self._sync_cards_to_config()
        if 0 <= idx < len(self.config.sequence):
            self.config.sequence.pop(idx)
            self._rebuild_step_cards()

    def _refresh_component_listbox(self):
        self.comp_listbox.delete(0, tk.END)
        for name in self.config.method_settings.components:
            self.comp_listbox.insert(tk.END, name)

    def _add_component(self):
        name = simpledialog.askstring('Add Component', 'Component name:', parent=self)
        if name:
            self._sync_cards_to_config()
            self.config.add_component(name)
            self._refresh_all()

    def _remove_component(self):
        sel = self.comp_listbox.curselection()
        if not sel:
            messagebox.showwarning('Notice', 'Please select a component first')
            return
        idx = sel[0]
        try:
            self._sync_cards_to_config()
            self.config.remove_component(idx)
            self._refresh_all()
        except ValueError as e:
            messagebox.showerror('Error', str(e))

    def _rename_component(self):
        sel = self.comp_listbox.curselection()
        if not sel:
            messagebox.showwarning('Notice', 'Please select a component first')
            return
        idx = sel[0]
        old_name = self.config.method_settings.components[idx]
        new_name = simpledialog.askstring('Rename Component', 'New name:',
                                            initialvalue=old_name, parent=self)
        if new_name and new_name != old_name:
            self.config.method_settings.components[idx] = new_name
            self._refresh_all()

    def _on_sma_edit(self, event):
        if self.sma_tree is None:
            return
        item = self.sma_tree.selection()
        if not item:
            return
        item = item[0]
        row_idx = self.sma_tree.index(item)
        col_id = self.sma_tree.identify_column(event.x)
        col_num = int(col_id.replace('#', '')) - 1
        if col_num <= 0:
            return
        comp_idx = col_num - 1
        comps = self.config.method_settings.components
        if comp_idx >= len(comps):
            return
        param_labels = ['Adsorption (ka)', 'Desorption (kd)',
                        'Char. Charge (v)', 'Steric (sigma)']
        if row_idx >= len(param_labels):
            return
        sma = self.config.method_settings.sma_params
        param_arrays = [sma.adsorption_rate, sma.desorption_rate,
                        sma.characteristic_charge, sma.steric_factor]
        old_val = param_arrays[row_idx][comp_idx] if comp_idx < len(param_arrays[row_idx]) else 0.0
        dlg = tk.Toplevel(self)
        dlg.title(f"Edit {param_labels[row_idx]} - {comps[comp_idx]}")
        dlg.geometry('300x100')
        dlg.transient(self)
        dlg.grab_set()
        ttk.Label(dlg, text=f"{param_labels[row_idx]} [{comps[comp_idx]}]:").pack(pady=5)
        var = tk.StringVar(value=f"{old_val:.6g}")
        ent = ttk.Entry(dlg, textvariable=var, font=FONT_MONO)
        ent.pack(padx=20, fill='x')
        ent.select_range(0, 'end')
        ent.focus_set()
        def apply():
            try:
                new_val = float(var.get())
                param_arrays[row_idx][comp_idx] = new_val
                self._refresh_sma_table()
                dlg.destroy()
            except (ValueError, IndexError) as e:
                messagebox.showerror('Error', str(e), parent=dlg)
        ent.bind('<Return>', lambda e: apply())
        ttk.Button(dlg, text='OK', command=apply).pack(pady=5)

    def _apply_global_params_silent(self):
        try:
            self.config.process_name = self.var_process_name.get()
            self.config.project_name = self.var_project_name.get()
            self.config.filler_name = self.var_filler_name.get()
            cp = self.config.method_settings.column_params
            cp.length = float(self.col_vars['length'].get())
            cp.diameter = float(self.col_vars['diameter'].get())
            cp.bed_porosity = float(self.col_vars['bed_porosity'].get())
            cp.particle_radius = float(self.col_vars['particle_radius'].get())
            cp.particle_porosity = float(self.col_vars['particle_porosity'].get())
            cp.axial_dispersion = float(self.col_vars['axial_dispersion'].get())
            self.config.method_settings.inlet_params.flow_rate_ml_min = float(self.var_flow_rate.get())
            self.config.method_settings.initial_salt_concentration = float(self.var_init_salt.get())
            self.config.method_settings.sma_params.capacity = float(self.var_sma_capacity.get())
        except (ValueError, AttributeError):
            pass

    def _refresh_global_params(self):
        ms = self.config.method_settings
        self.var_process_name.set(self.config.process_name)
        self.var_project_name.set(self.config.project_name)
        self.var_filler_name.set(self.config.filler_name)
        cp = ms.column_params
        self.col_vars['length'].set(str(cp.length))
        self.col_vars['diameter'].set(str(cp.diameter))
        self.col_vars['bed_porosity'].set(str(cp.bed_porosity))
        self.col_vars['particle_radius'].set(str(cp.particle_radius))
        self.col_vars['particle_porosity'].set(str(cp.particle_porosity))
        self.col_vars['axial_dispersion'].set(str(cp.axial_dispersion))
        self.var_flow_rate.set(f"{ms.inlet_params.flow_rate_ml_min:.4f}")
        self.var_init_salt.set(str(ms.initial_salt_concentration))
        self.var_sma_capacity.set(str(ms.sma_params.capacity))
        self.lbl_col_vol.config(text=f"Column Volume: {cp.column_volume_ml:.4f} mL")

    def _build_scouting_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Scouting")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self._scouting_param_vars = {}
        self._scouting_all_params = []
        self._scouting_checked_params = []
        self._scouting_rows = []
        self.scout_table = None
        pw = ttk.PanedWindow(frame, orient='horizontal')
        pw.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        left = ttk.LabelFrame(pw, text='Scan Parameters')
        pw.add(left, weight=1)
        ttk.Button(left, text='Refresh Parameters',
                   command=self._refresh_scouting_params,
                   style='Small.TButton').pack(fill='x', padx=5, pady=3)
        canvas = tk.Canvas(left, highlightthickness=0, bg=BG_CONTENT)
        vsb = ttk.Scrollbar(left, orient='vertical', command=canvas.yview)
        self._scout_check_frame = ttk.Frame(canvas)
        self._scout_check_frame.bind('<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=self._scout_check_frame, anchor='nw')
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        def _on_mw(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind('<MouseWheel>', _on_mw)
        self._scout_check_frame.bind('<MouseWheel>', _on_mw)
        right = ttk.LabelFrame(pw, text='Batch Run Table')
        pw.add(right, weight=3)
        btn_bar = ttk.Frame(right)
        btn_bar.pack(fill='x', padx=5, pady=3)
        ttk.Button(btn_bar, text='Update Columns',
                   command=self._update_scouting_table,
                   style='Small.TButton').pack(side='left', padx=2)
        ttk.Button(btn_bar, text='Add Row',
                   command=self._add_scouting_row,
                   style='Small.TButton').pack(side='left', padx=2)
        ttk.Button(btn_bar, text='Delete Row',
                   command=self._delete_scouting_row,
                   style='Small.TButton').pack(side='left', padx=2)
        ttk.Button(btn_bar, text='Clear',
                   command=self._clear_scouting_table,
                   style='Small.TButton').pack(side='left', padx=2)
        ttk.Button(btn_bar, text='Run Scouting',
                   command=self._run_scouting,
                   style='Accent.TButton').pack(side='right', padx=2)
        self.lbl_scout_info = ttk.Label(btn_bar, text='0 params, 0 runs',
                                        font=FONT_SMALL, foreground=TEXT_SECONDARY)
        self.lbl_scout_info.pack(side='right', padx=10)
        self._scout_table_frame = ttk.Frame(right)
        self._scout_table_frame.pack(fill='both', expand=True, padx=5, pady=5)
        try:
            self._refresh_scouting_params()
        except Exception:
            pass

    def _refresh_scouting_params(self):
        self._apply_global_params_silent()
        self._scouting_all_params = extract_numeric_parameters(self.config)
        for w in self._scout_check_frame.winfo_children():
            w.destroy()
        old_checked = {p for p, v in self._scouting_param_vars.items() if v.get()}
        self._scouting_param_vars.clear()
        categories = {}
        for p in self._scouting_all_params:
            cat = p['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(p)
        row = 0
        for cat, params in categories.items():
            lbl = ttk.Label(self._scout_check_frame, text=cat,
                            font=FONT_SUBTITLE, foreground=PRIMARY_TEAL)
            lbl.grid(row=row, column=0, columnspan=2, sticky='w', padx=5, pady=(8, 2))
            row += 1
            for p in params:
                var = tk.BooleanVar(value=(p['path'] in old_checked))
                self._scouting_param_vars[p['path']] = var
                cb = ttk.Checkbutton(self._scout_check_frame,
                    text=f"{p['display_name']}", variable=var)
                cb.grid(row=row, column=0, sticky='w', padx=15, pady=1)
                val_lbl = ttk.Label(self._scout_check_frame,
                    text=f"= {p['value']:.6g}", font=FONT_SMALL, foreground=TEXT_SECONDARY)
                val_lbl.grid(row=row, column=1, sticky='w', padx=5, pady=1)
                row += 1

    def _get_checked_params(self):
        checked = []
        for p in self._scouting_all_params:
            var = self._scouting_param_vars.get(p['path'])
            if var and var.get():
                checked.append(p)
        return checked

    def _update_scouting_table(self):
        self._scouting_checked_params = self._get_checked_params()
        n_params = len(self._scouting_checked_params)
        if n_params == 0:
            messagebox.showwarning('Notice', 'Please check at least one parameter')
            return
        for w in self._scout_table_frame.winfo_children():
            w.destroy()
        col_ids = ['run_idx'] + [p['path'] for p in self._scouting_checked_params]
        self.scout_table = ttk.Treeview(self._scout_table_frame, columns=col_ids,
            show='headings', height=12)
        self.scout_table.heading('run_idx', text='#')
        self.scout_table.column('run_idx', width=40, anchor='center')
        for p in self._scouting_checked_params:
            self.scout_table.heading(p['path'], text=p['display_name'])
            self.scout_table.column(p['path'], width=120, anchor='center')
        hsb = ttk.Scrollbar(self._scout_table_frame, orient='horizontal',
                             command=self.scout_table.xview)
        self.scout_table.configure(xscrollcommand=hsb.set)
        self.scout_table.pack(fill='both', expand=True)
        hsb.pack(fill='x')
        self.scout_table.bind('<Double-1>', self._on_scout_cell_edit)
        self._rebuild_scouting_rows_display()
        self._update_scout_info_label()

    def _rebuild_scouting_rows_display(self):
        if self.scout_table is None:
            return
        for item in self.scout_table.get_children():
            self.scout_table.delete(item)
        for i, row_data in enumerate(self._scouting_rows):
            vals = [str(i + 1)]
            for p in self._scouting_checked_params:
                v = row_data.get(p['path'], p['value'])
                vals.append(f"{v:.6g}")
            self.scout_table.insert('', 'end', values=vals)

    def _add_scouting_row(self):
        if not self._scouting_checked_params:
            messagebox.showwarning('Notice', 'Check params and click Update Columns first')
            return
        row_data = {}
        for p in self._scouting_checked_params:
            row_data[p['path']] = p['value']
        self._scouting_rows.append(row_data)
        self._rebuild_scouting_rows_display()
        self._update_scout_info_label()

    def _delete_scouting_row(self):
        if self.scout_table is None:
            return
        sel = self.scout_table.selection()
        if not sel:
            return
        indices = sorted([self.scout_table.index(s) for s in sel], reverse=True)
        for idx in indices:
            if 0 <= idx < len(self._scouting_rows):
                self._scouting_rows.pop(idx)
        self._rebuild_scouting_rows_display()
        self._update_scout_info_label()

    def _clear_scouting_table(self):
        self._scouting_rows.clear()
        if self.scout_table is not None:
            for item in self.scout_table.get_children():
                self.scout_table.delete(item)
        self._update_scout_info_label()

    def _on_scout_cell_edit(self, event):
        if self.scout_table is None:
            return
        sel = self.scout_table.selection()
        if not sel:
            return
        item = sel[0]
        row_idx = self.scout_table.index(item)
        col_id = self.scout_table.identify_column(event.x)
        col_num = int(col_id.replace('#', '')) - 1
        if col_num <= 0:
            return
        param_idx = col_num - 1
        if param_idx >= len(self._scouting_checked_params):
            return
        param = self._scouting_checked_params[param_idx]
        path = param['path']
        old_val = self._scouting_rows[row_idx].get(path, param['value'])
        dlg = tk.Toplevel(self)
        dlg.title(f"Edit: {param['display_name']}")
        dlg.geometry('300x100')
        dlg.transient(self)
        dlg.grab_set()
        ttk.Label(dlg, text=f"{param['display_name']}:").pack(pady=5)
        var = tk.StringVar(value=f"{old_val:.6g}")
        ent = ttk.Entry(dlg, textvariable=var, font=FONT_MONO)
        ent.pack(padx=20, fill='x')
        ent.select_range(0, 'end')
        ent.focus_set()
        def apply():
            try:
                new_val = float(var.get())
                self._scouting_rows[row_idx][path] = new_val
                self._rebuild_scouting_rows_display()
                dlg.destroy()
            except ValueError:
                messagebox.showerror('Error', 'Please enter a valid number', parent=dlg)
        ent.bind('<Return>', lambda e: apply())
        ttk.Button(dlg, text='OK', command=apply).pack(pady=5)

    def _update_scout_info_label(self):
        n_params = len(self._scouting_checked_params)
        n_runs = len(self._scouting_rows)
        self.lbl_scout_info.config(text=f"{n_params} params, {n_runs} runs")

    def _run_scouting(self):
        if not self._scouting_checked_params:
            messagebox.showwarning('Notice', 'Check params and update table first')
            return
        if not self._scouting_rows:
            messagebox.showwarning('Notice', 'Add at least one run row')
            return
        n_runs = len(self._scouting_rows)
        if n_runs > 100:
            if not messagebox.askyesno('Confirm', f"{n_runs} runs will be generated. Continue?"):
                return
        self._apply_global_params_silent()
        self._sync_cards_to_config()
        config_json = self.config.to_json()
        method_id = self._current_method_id
        if method_id is None:
            method_id = self.db.save_method(
                self.config.process_name, config_json,
                description="Scouting base method",
                project_name=self.config.project_name,
                filler_name=self.config.filler_name)
            self._current_method_id = method_id
        variables_json = json.dumps({
            'version': 2,
            'parameters': [{'path': p['path'], 'display_name': p['display_name']}
                           for p in self._scouting_checked_params],
            'runs': self._scouting_rows,
            'n_runs': n_runs,
        }, ensure_ascii=False)
        plan_id = self.db.create_scouting_plan(
            method_id,
            f"Scouting_{self.config.process_name}",
            variables_json)
        for run_idx, row_data in enumerate(self._scouting_rows):
            self.db.add_scouting_result(
                plan_id, run_idx,
                json.dumps(row_data, ensure_ascii=False))
        if hasattr(self.ctx, 'get') and 'run_scouting_callback' in self.ctx:
            self.ctx['run_scouting_callback'](plan_id)
        else:
            messagebox.showinfo('Scouting Plan Created',
                f"Total {n_runs} runs, Plan ID: {plan_id}. "
                'Switch to Method Run module to execute')

    def _build_queue_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Method Queue")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        btn_bar = ttk.Frame(frame)
        btn_bar.grid(row=0, column=0, sticky='ew', padx=10, pady=5)
        ttk.Button(btn_bar, text='New Queue', command=self._create_queue,
                   style='Small.TButton').pack(side='left', padx=2)
        ttk.Button(btn_bar, text='Add Current Method', command=self._add_to_queue,
                   style='Small.TButton').pack(side='left', padx=2)
        ttk.Button(btn_bar, text='Run Queue', command=self._run_queue,
                   style='Accent.TButton').pack(side='left', padx=2)
        ttk.Button(btn_bar, text='Refresh', command=self._refresh_queues,
                   style='Small.TButton').pack(side='left', padx=2)
        ttk.Button(btn_bar, text='Delete Queue', command=self._delete_queue,
                   style='Small.TButton').pack(side='left', padx=2)
        q_cols = ('queue_name', 'status', 'items')
        self.queue_tree = ttk.Treeview(frame, columns=q_cols, show='headings', height=8)
        self.queue_tree.heading('queue_name', text='Queue Name')
        self.queue_tree.heading('status', text='Status')
        self.queue_tree.heading('items', text='Methods')
        self.queue_tree.column('queue_name', width=200)
        self.queue_tree.column('status', width=100)
        self.queue_tree.column('items', width=80)
        self.queue_tree.grid(row=1, column=0, sticky='nsew', padx=10, pady=5)
        detail_frame = ttk.LabelFrame(frame, text='Queue Details')
        detail_frame.grid(row=2, column=0, sticky='ew', padx=10, pady=5)
        qi_cols = ('position', 'method_name', 'start_condition', 'status')
        self.qi_tree = ttk.Treeview(detail_frame, columns=qi_cols,
                                     show='headings', height=5)
        self.qi_tree.heading('position', text='#')
        self.qi_tree.heading('method_name', text='Method')
        self.qi_tree.heading('start_condition', text='Start Condition')
        self.qi_tree.heading('status', text='Status')
        self.qi_tree.pack(fill='both', expand=True, padx=5, pady=5)
        self.queue_tree.bind('<<TreeviewSelect>>', self._on_queue_select)

    def _create_queue(self):
        name = simpledialog.askstring('New Queue', 'Queue name:', parent=self)
        if name:
            self.db.create_queue(name)
            self._refresh_queues()

    def _add_to_queue(self):
        sel = self.queue_tree.selection()
        if not sel:
            messagebox.showwarning('Notice', 'Please select a queue first')
            return
        queue_id = int(sel[0])
        if self._current_method_id is None:
            self._on_save_method()
        if self._current_method_id is None:
            return
        items = self.db.get_queue_items(queue_id)
        pos = len(items) + 1
        self.db.add_queue_item(queue_id, self._current_method_id, pos)
        self._on_queue_select(None)
        messagebox.showinfo('Success', 'Method added to queue')

    def _run_queue(self):
        sel = self.queue_tree.selection()
        if not sel:
            messagebox.showwarning('Notice', 'Please select a queue first')
            return
        queue_id = int(sel[0])
        if 'run_queue_callback' in self.ctx:
            self.ctx['run_queue_callback'](queue_id)
        else:
            messagebox.showinfo('Notice', 'Switch to Method Run module to execute queue')

    def _delete_queue(self):
        sel = self.queue_tree.selection()
        if not sel:
            messagebox.showwarning('Notice', 'Please select a queue first')
            return
        queue_id = int(sel[0])
        if not messagebox.askyesno('Confirm Delete', 'Delete selected queue?'):
            return
        self.db.delete_queue(queue_id)
        self._refresh_queues()

    def _on_queue_select(self, event):
        sel = self.queue_tree.selection()
        if not sel:
            return
        queue_id = int(sel[0])
        items = self.db.get_queue_items(queue_id)
        for item in self.qi_tree.get_children():
            self.qi_tree.delete(item)
        for qi in items:
            self.qi_tree.insert('', 'end', values=(
                qi['position'],
                qi.get('method_name', f"Method #{qi['method_id']}"),
                qi['start_condition'],
                qi['status']))

    def _refresh_queues(self):
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)
        queues = self.db.get_queues()
        for q in queues:
            items = self.db.get_queue_items(q['id'])
            self.queue_tree.insert('', 'end', iid=str(q['id']),
                                    values=(q['queue_name'], q['status'], len(items)))

    def _on_new_method(self):
        self.config = create_default_config()
        self._current_method_id = None
        self._refresh_all()

    def _on_load_method(self):
        methods = self.db.get_methods()
        if not methods:
            messagebox.showinfo('Notice', 'No saved methods')
            return
        dlg = tk.Toplevel(self)
        dlg.title('Open Method')
        dlg.geometry('500x350')
        dlg.transient(self)
        dlg.grab_set()
        cols = ('id', 'name', 'updated')
        tree = ttk.Treeview(dlg, columns=cols, show='headings', height=10)
        tree.heading('id', text='ID')
        tree.heading('name', text='Method Name')
        tree.heading('updated', text='Updated')
        tree.column('id', width=50)
        tree.column('name', width=200)
        tree.column('updated', width=150)
        tree.pack(fill='both', expand=True, padx=10, pady=10)
        import datetime
        for m in methods:
            updated = ''
            if m.get('updated_at'):
                updated = datetime.datetime.fromtimestamp(
                    m['updated_at']).strftime('%Y-%m-%d %H:%M')
            tree.insert('', 'end', iid=str(m['id']),
                        values=(m['id'], m['method_name'], updated))
        def do_load():
            sel = tree.selection()
            if not sel:
                return
            mid = int(sel[0])
            method = self.db.get_method(mid)
            if method:
                try:
                    data = json.loads(method['config_json'])
                    self.config = ProcessConfig._from_dict(data)
                    self._current_method_id = mid
                    self._refresh_all()
                    dlg.destroy()
                except Exception as e:
                    messagebox.showerror('Load Failed', str(e), parent=dlg)
        ttk.Button(dlg, text='Load', command=do_load,
                   style='Accent.TButton').pack(pady=5)

    def _on_save_method(self):
        self._apply_global_params_silent()
        self._sync_cards_to_config()
        config_json = self.config.to_json()
        mid = self.db.save_method(
            self.config.process_name, config_json,
            method_id=self._current_method_id)
        self._current_method_id = mid
        messagebox.showinfo('Success', f"Method saved (ID: {mid})")

    def _on_save_as_method(self):
        name = simpledialog.askstring('Save As', 'Method name:',
                                          initialvalue=self.config.process_name,
                                          parent=self)
        if name:
            self.config.process_name = name
            self._apply_global_params_silent()
            self._sync_cards_to_config()
            config_json = self.config.to_json()
            mid = self.db.save_method(name, config_json)
            self._current_method_id = mid
            self._refresh_all()
            messagebox.showinfo('Success', f"Method saved as '{name}' (ID: {mid})")



    def _on_delete_method(self):
        if self._current_method_id is None:
            messagebox.showwarning('Notice', 'No method loaded to delete')
            return
        msg = f"Delete method (ID: {self._current_method_id})?"
        if not messagebox.askyesno('Confirm Delete', msg):
            return
        self.db.delete_method(self._current_method_id)
        self._current_method_id = None
        self.config = create_default_config()
        self._refresh_all()
        messagebox.showinfo('Deleted', 'Method deleted successfully')

    def _refresh_all(self):
        self._refresh_global_params()
        self._refresh_sma_table()
        self._refresh_component_listbox()
        self._rebuild_step_cards()
        self._refresh_queues()

    def _refresh_sma_table(self):
        for w in self._sma_table_container.winfo_children():
            w.destroy()
        sma = self.config.method_settings.sma_params
        comps = self.config.method_settings.components
        n = min(len(comps), len(sma.adsorption_rate))
        col_ids = ['param'] + [f"comp_{i}" for i in range(n)]
        self.sma_tree = ttk.Treeview(self._sma_table_container,
                                      columns=col_ids, show='headings', height=4)
        self.sma_tree.heading('param', text='Parameter')
        self.sma_tree.column('param', width=120)
        for i in range(n):
            self.sma_tree.heading(f"comp_{i}", text=comps[i])
            self.sma_tree.column(f"comp_{i}", width=80, anchor='center')
        params_data = [
            ('Adsorption (ka)', sma.adsorption_rate),
            ('Desorption (kd)', sma.desorption_rate),
            ('Char. Charge (v)', sma.characteristic_charge),
            ('Steric (sigma)', sma.steric_factor),
        ]
        for name, arr in params_data:
            vals = [name] + [f"{arr[i]:.4f}" if i < len(arr) else '0.0' for i in range(n)]
            self.sma_tree.insert('', 'end', values=vals)
        self.sma_tree.pack(fill='x')
        self.sma_tree.bind('<Double-1>', self._on_sma_edit)

    def get_current_config(self) -> ProcessConfig:
        self._apply_global_params_silent()
        self._sync_cards_to_config()
        return self.config

    def get_current_method_id(self) -> Optional[int]:
        return self._current_method_id
