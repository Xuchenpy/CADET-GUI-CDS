"""
CADET CDS Visual Style Definitions (v9)

Color Scheme:
  - Primary Teal: #0D8070 (brand accent / headers / selected tabs)
  - Toolbar Gray: #5A5A5A (module toolbars)
  - Gray backgrounds: #F0F0F0 (panel), #E0E0E0 (border)
  - White content area: #FFFFFF
  - Warning/Error: #D32F2F
"""

import tkinter as tk
from tkinter import ttk


# ============================================================
# Color Constants (v9 Teal + Gray)
# ============================================================

# 新标准名称
ACCENT_GRAY = "#4A4A4A"
ACCENT_GRAY_LIGHT = "#6A6A6A"
ACCENT_GRAY_DARK = "#333333"

TOOLBAR_GRAY = "#5A5A5A"
TOOLBAR_GRAY_LIGHT = "#6E6E6E"
TOOLBAR_BTN_BG = "#6A6A6A"
TOOLBAR_BTN_HOVER = "#7A7A7A"

# Primary Teal brand colors (restored)
PRIMARY_TEAL = "#0D8070"
PRIMARY_TEAL_LIGHT = "#4DB6A9"
PRIMARY_TEAL_DARK = "#095E54"

DARK_NAVY = TOOLBAR_GRAY
DARK_NAVY_LIGHT = TOOLBAR_GRAY_LIGHT

BG_MAIN = "#F0F0F0"
BG_PANEL = "#F5F5F5"
BG_CONTENT = "#FFFFFF"
BG_HEADER = "#E8E8E8"
BG_SIDEBAR = "#E0E0E0"

BORDER_COLOR = "#CCCCCC"
BORDER_DARK = "#999999"

TEXT_PRIMARY = "#333333"
TEXT_SECONDARY = "#555555"
TEXT_LIGHT = "#FFFFFF"
TEXT_LINK = PRIMARY_TEAL
TEXT_SUBTITLE_ON_TEAL = "#B2DFDB"

COLOR_SUCCESS = "#4CAF50"
COLOR_WARNING = "#FF9800"
COLOR_ERROR = "#D32F2F"
COLOR_INFO = "#2196F3"

# 工艺步骤色带
STEP_COLORS = {
    'Equilibration': '#D6D6D6',
    'Load':          '#C4C4C4',
    'Wash':          '#B5B5B5',
    'Elution':       '#A3A3A3',
    'CIP':           '#949494',
    'Regeneration':  '#878787',
}

# 工艺步骤按钮悬停色 (深一档)
STEP_HOVER_COLORS = {
    'Equilibration': '#C0C0C0',
    'Load':          '#AEAEAE',
    'Wash':          '#9F9F9F',
    'Elution':       '#8D8D8D',
    'CIP':           '#7E7E7E',
    'Regeneration':  '#717171',
}

# 组分曲线配色
COMPONENT_COLORS = ['#2196F3', '#4CAF50', '#FF9800', '#9C27B0',
                    '#F44336', '#00BCD4', '#795548']
SALT_COLOR = '#555555'
TOTAL_PROTEIN_COLOR = '#0000CC'

# 字体定义
FONT_TITLE = ('Microsoft YaHei', 14, 'bold')
FONT_SUBTITLE = ('Microsoft YaHei', 11, 'bold')
FONT_BODY = ('Microsoft YaHei', 10)
FONT_SMALL = ('Microsoft YaHei', 9)
FONT_MONO = ('Consolas', 10)
FONT_TABLE = ('Microsoft YaHei', 9)
FONT_BUTTON = ('Microsoft YaHei', 10)
FONT_MENU = ('Microsoft YaHei', 10)


# ============================================================
# ttk 主题配置
# ============================================================

def apply_cds_theme(root: tk.Tk):
    """应用 CDS 主题到 tkinter 窗口"""
    style = ttk.Style(root)

    # 尝试使用 clam 作为基础主题
    try:
        style.theme_use('clam')
    except tk.TclError:
        pass

    # -- 全局背景 --
    style.configure('.', background=BG_MAIN, foreground=TEXT_PRIMARY,
                    font=FONT_BODY)

    # -- TNotebook (主模块标签页) --
    style.configure('TNotebook', background=BG_MAIN, borderwidth=0)
    style.configure('TNotebook.Tab',
                    background=BG_HEADER,
                    foreground=TEXT_PRIMARY,
                    font=FONT_BUTTON,
                    padding=[16, 8])
    style.map('TNotebook.Tab',
              background=[('selected', PRIMARY_TEAL), ('active', PRIMARY_TEAL_LIGHT)],
              foreground=[('selected', TEXT_LIGHT), ('active', TEXT_LIGHT)])

    # -- TFrame --
    style.configure('TFrame', background=BG_MAIN)
    style.configure('Panel.TFrame', background=BG_CONTENT, relief='solid',
                    borderwidth=1)
    style.configure('Sidebar.TFrame', background=BG_SIDEBAR)
    style.configure('Header.TFrame', background=PRIMARY_TEAL)
    style.configure('Toolbar.TFrame', background=DARK_NAVY)

    # -- TLabel --
    style.configure('TLabel', background=BG_MAIN, foreground=TEXT_PRIMARY,
                    font=FONT_BODY)
    style.configure('Title.TLabel', font=FONT_TITLE, foreground=PRIMARY_TEAL_DARK)
    style.configure('Subtitle.TLabel', font=FONT_SUBTITLE, foreground=TEXT_PRIMARY)
    style.configure('Header.TLabel', background=PRIMARY_TEAL, foreground=TEXT_LIGHT,
                    font=FONT_SUBTITLE, padding=[10, 5])
    style.configure('Toolbar.TLabel', background=DARK_NAVY, foreground=TEXT_LIGHT,
                    font=FONT_BODY)
    style.configure('Status.TLabel', background=BG_HEADER, foreground=TEXT_SECONDARY,
                    font=FONT_SMALL, padding=[5, 2])
    style.configure('Small.TLabel', font=FONT_SMALL, foreground=TEXT_SECONDARY)

    # -- TButton --
    style.configure('TButton',
                    background=BG_HEADER,
                    foreground=TEXT_PRIMARY,
                    font=FONT_BUTTON,
                    padding=[12, 6])
    style.map('TButton',
              background=[('active', BORDER_COLOR), ('pressed', BORDER_DARK)])

    style.configure('Accent.TButton',
                    background=PRIMARY_TEAL,
                    foreground=TEXT_LIGHT,
                    font=FONT_BUTTON,
                    padding=[12, 6])
    style.map('Accent.TButton',
              background=[('active', PRIMARY_TEAL_LIGHT), ('pressed', PRIMARY_TEAL_DARK)])

    style.configure('Navy.TButton',
                    background=DARK_NAVY,
                    foreground=TEXT_LIGHT,
                    font=FONT_BUTTON,
                    padding=[12, 6])
    style.map('Navy.TButton',
              background=[('active', DARK_NAVY_LIGHT), ('pressed', '#4A4A4A')])

    style.configure('Danger.TButton',
                    background=COLOR_ERROR,
                    foreground=TEXT_LIGHT,
                    font=FONT_BUTTON,
                    padding=[12, 6])
    style.map('Danger.TButton',
              background=[('active', '#E57373'), ('pressed', '#B71C1C')])

    style.configure('Small.TButton',
                    font=FONT_SMALL,
                    padding=[8, 3])

    # -- TEntry --
    style.configure('TEntry',
                    fieldbackground=BG_CONTENT,
                    foreground=TEXT_PRIMARY,
                    font=FONT_BODY,
                    padding=[4, 4])

    # -- TCombobox --
    style.configure('TCombobox',
                    fieldbackground=BG_CONTENT,
                    foreground=TEXT_PRIMARY,
                    font=FONT_BODY)

    # -- Treeview --
    style.configure('Treeview',
                    background=BG_CONTENT,
                    foreground=TEXT_PRIMARY,
                    fieldbackground=BG_CONTENT,
                    font=FONT_TABLE,
                    rowheight=26)
    style.configure('Treeview.Heading',
                    background=BG_HEADER,
                    foreground=TEXT_PRIMARY,
                    font=('Microsoft YaHei', 9, 'bold'))
    style.map('Treeview',
              background=[('selected', PRIMARY_TEAL)],
              foreground=[('selected', TEXT_LIGHT)])

    # -- TLabelframe --
    style.configure('TLabelframe',
                    background=BG_MAIN,
                    foreground=TEXT_PRIMARY,
                    font=FONT_SUBTITLE)
    style.configure('TLabelframe.Label',
                    background=BG_MAIN,
                    foreground=PRIMARY_TEAL_DARK,
                    font=FONT_SUBTITLE)

    # -- TProgressbar --
    style.configure('TProgressbar',
                    background=PRIMARY_TEAL,
                    troughcolor=BG_HEADER)

    # -- Separator --
    style.configure('TSeparator', background=BORDER_COLOR)

    # -- Scrollbar --
    style.configure('TScrollbar',
                    background=BG_HEADER,
                    troughcolor=BG_MAIN,
                    arrowcolor=TEXT_SECONDARY)

    return style


def configure_root_window(root: tk.Tk, title: str = "CADET CDS - Chromatography Simulation"):
    """配置主窗口基本属性"""
    root.title(title)
    root.geometry("1400x900")
    root.minsize(1100, 700)
    root.resizable(True, True)
    root.configure(bg=BG_MAIN)

    # 窗口图标和位置
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"+{x}+{y}")
