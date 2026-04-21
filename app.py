"""
CADET CDS - 色谱模拟系统主应用窗口

集成三个核心模块:
  1. 方法编辑器 (Method Editor)
  2. 方法运行 (Method Run)
  3. 结果分析 (Result Analysis)

整体布局:
  - 菜单栏: 文件/环境/帮助
  - 顶部: 标题栏 (Teal #0D8070)
  - 中间: 三模块标签页
  - 底部: 状态栏
"""

import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox
import tempfile
import shutil

_app_dir = os.path.dirname(os.path.abspath(__file__))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from styles import (
    apply_cds_theme, configure_root_window,
    PRIMARY_TEAL, PRIMARY_TEAL_DARK, DARK_NAVY, BG_MAIN, BG_HEADER,
    TEXT_LIGHT, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_SUBTITLE_ON_TEAL,
    FONT_TITLE, FONT_SUBTITLE, FONT_BODY, FONT_SMALL
)
from db_manager import DatabaseManager
from method_editor import MethodEditorModule
from method_run import MethodRunModule
from result_analysis import ResultAnalysisModule


class CadetCDSApp:
    """CADET CDS 色谱模拟系统主应用"""

    def __init__(self):
        self.root = tk.Tk()
        configure_root_window(self.root, "CADET CDS - Chromatography Simulation")
        apply_cds_theme(self.root)

        # 初始化数据库
        self.db = DatabaseManager()

        # 应用上下文 (共享状态)
        self.ctx = {
            'run_scouting_callback': self._run_scouting,
            'run_queue_callback': self._run_queue,
        }

        # 关闭窗口时执行清理
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 直接构建主界面
        self._build_menu()
        self._build_ui()

    def _build_menu(self):
        """构建菜单栏"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Exit", command=self._on_close,
                             accelerator="Alt+F4")
        menubar.add_cascade(label="File", menu=file_menu)

        # 环境菜单
        env_menu = tk.Menu(menubar, tearoff=0)
        env_menu.add_command(label="Scan Python Environments...",
                            command=self._open_env_scanner)
        env_menu.add_command(label="Detect CADET Packages...",
                            command=self._check_cadet_packages)
        menubar.add_cascade(label="Tools", menu=env_menu)

        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About CADET CDS",
                             command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

    def _build_ui(self):
        """构建主界面"""
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # ---- 顶部标题栏 ----
        header = tk.Frame(self.root, bg=PRIMARY_TEAL, height=50)
        header.grid(row=0, column=0, sticky='ew')
        header.grid_propagate(False)

        tk.Label(header, text="CADET CDS - Chromatography Simulation",
                 bg=PRIMARY_TEAL, fg=TEXT_LIGHT,
                 font=('Microsoft YaHei', 14, 'bold')).pack(
            side='left', padx=15, pady=10)

        # ---- 主标签页 (三个模块) ----
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        # 方法编辑器
        self.method_editor = MethodEditorModule(
            self.notebook, self.db, self.ctx)
        self.notebook.add(self.method_editor, text="  Method Editor  ")
        # 方法运行
        self.method_run = MethodRunModule(
            self.notebook, self.db, self.ctx,
            get_editor_config=self._get_editor_config)
        self.notebook.add(self.method_run, text="  Method Run  ")
        # 结果分析
        self.result_analysis = ResultAnalysisModule(
            self.notebook, self.db, self.ctx)
        self.notebook.add(self.result_analysis, text="  Result Analysis  ")
        # 标签页切换时刷新
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)

        # ---- 底部状态栏 ----
        status = tk.Frame(self.root, bg=BG_HEADER, height=28)
        status.grid(row=2, column=0, sticky='ew')
        status.grid_propagate(False)
        tk.Label(status, text="CADET CDS | IEX Chromatography Simulation",
                 bg=BG_HEADER, fg=TEXT_SECONDARY,
                 font=FONT_SMALL).pack(side='left', padx=10, pady=4)

        self.lbl_db_status = tk.Label(
            status, text=f"DB: {os.path.basename(self.db.db_path)}",
            bg=BG_HEADER, fg=TEXT_SECONDARY, font=FONT_SMALL)
        self.lbl_db_status.pack(side='right', padx=10)

    def _get_editor_config(self):
        """获取当前编辑器的配置"""
        return self.method_editor.get_current_config()

    def _on_tab_changed(self, event):
        """标签页切换时刷新数据"""
        tab_idx = self.notebook.index(self.notebook.select())
        if tab_idx == 2:  # 结果分析
            self.result_analysis._refresh_results()

    def _run_scouting(self, plan_id: int):
        """从方法编辑器触发 Scouting 运行"""
        self.notebook.select(1)  # 切到方法运行
        self.method_run.run_scouting(plan_id)

    def _run_queue(self, queue_id: int):
        """从方法编辑器触发队列运行"""
        self.notebook.select(1)
        self.method_run.run_queue(queue_id)

    def _on_close(self):
        """关闭应用时执行清理"""
        try:
            # 清除运行时数据
            self.db.clear_runtime_data()
            # 清理临时文件目录
            tmp_dir = os.path.join(_app_dir, 'tmp')
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
        finally:
            self.root.destroy()

    def _open_env_scanner(self):
        """打开环境扫描对话框"""
        try:
            from env_manager import EnvironmentManager
            env_mgr = EnvironmentManager()
            envs = env_mgr.get_all_environments()

            # 构建信息文本
            info_lines = ["Detected Python environments:\n"]
            for env in envs:
                info_lines.append(
                    f"  [{env['type']}] {env['name']}: {env['path']}")
            if not envs:
                info_lines.append("  未检测到任何Python环境")

            messagebox.showinfo(
                "Python Environment Scan",
                "\n".join(info_lines),
                parent=self.root)
        except ImportError:
            messagebox.showwarning(
                "Module Not Ready",
                "Environment manager module (env_manager.py) not available.",
                parent=self.root)
        except Exception as e:
            messagebox.showerror(
                "扫描失败", f"Environment scan error:\n{e}", parent=self.root)

    def _check_cadet_packages(self):
        """检测当前环境的CADET包"""
        try:
            from env_manager import EnvironmentManager
            env_mgr = EnvironmentManager()
            result = env_mgr.check_packages(sys.executable)

            info_lines = [f"Current Python: {sys.executable}\n",
                         "CADET package status:\n"]
            for pkg, status in result.items():
                mark = "OK" if status['installed'] else "Missing"
                ver = status.get('version', '')
                info_lines.append(f"  [{mark}] {pkg} {ver}")

            messagebox.showinfo(
                "CADET Package Detection",
                "\n".join(info_lines),
                parent=self.root)
        except ImportError:
            messagebox.showwarning(
                "Module Not Ready",
                "Environment manager module (env_manager.py) not available.",
                parent=self.root)
        except Exception as e:
            messagebox.showerror(
                "Detection Failed", f"Package detection error:\n{e}", parent=self.root)
    def _show_about(self):
        """Show about dialog"""
        about_text = (
            "CADET CDS\n"
            "Chromatography Data System\n\n"
            "Ion Exchange Chromatography Simulation\n"
            "Based on CADET-Core\n\n"
            "Features:\n"
            "  - Method parameter editing & management\n"
            "  - SMA model simulation\n"
            "  - Chromatogram result analysis & export\n"
            "  - Scouting parameter sweep\n"
            "  - Method queue batch run\n\n"
            "Dependencies: CADET-Core, CADET-Process"
        )
        messagebox.showinfo("About CADET CDS", about_text, parent=self.root)
    def run(self):
        """Run main loop"""
        if self.root.winfo_exists():
            self.root.mainloop()


def main():
    """Application entry point"""
    app = CadetCDSApp()
    app.run()


if __name__ == '__main__':
    main()
