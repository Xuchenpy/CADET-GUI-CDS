# CADET CDS - 代码文档

## 概述

CADET GUI CDS (Chromatography Data System，色谱数据系统) 是一个基于 CADET-Core/CADET-Process 的离子交换色谱模拟GUI桌面应用程序。使用 Python Tkinter 构建，它提供方法编辑、模拟执行和结果分析功能。

## 架构

```
run_app.py          入口点
  |
  +-- cadet_env.py  CADET DLL 初始化
  +-- app.py        主应用窗口 (CadetCDSApp)
       |
       +-- method_editor.py   方法编辑器模块 (标签 1)
       +-- method_run.py      方法运行模块 (标签 2)
       +-- result_analysis.py 结果分析模块 (标签 3)
       |
       +-- db_manager.py      SQLite 数据库管理器
       +-- env_manager.py     Python 环境扫描器
       +-- simulation_engine.py  CADET 模拟包装器
       +-- config_models.py   数据模型 (ProcessConfig 等)
       +-- styles.py          UI 主题常量
       +-- visualization.py   色谱图绘制
       +-- peak_analysis.py   峰检测与分析
       +-- csv_export.py      CSV 导出工具
       +-- unit_converter.py  单位转换工具
```

## 模块详情

### app.py - 主应用
- 类: `CadetCDSApp`
- 创建带有菜单栏和 3 标签页的根 Tk 窗口
- 菜单: 文件 (退出)、工具 (环境、包检测)、帮助 (关于)
- 管理共享的 `app_context` 字典和 `DatabaseManager` 实例

### db_manager.py - 数据库管理器
- 类: `DatabaseManager`
- SQLite 数据库 (`cadet_cds.db`)
- 表: `methods`, `simulation_results`, `scouting_plans`, `method_queues`
- 所有方法都是用户无关的 (无 user_id 参数)
- 关键方法: `save_method()`, `get_methods()`, `save_result()`,
  `get_results()`, `create_scouting_plan()`, `create_queue()`

### method_editor.py - 方法编辑器模块
- 类: `MethodEditorModule(ttk.Frame)`
- 标签式界面: 柱、组分、梯度、SMA、 scouts (扫描)、队列
- 管理 `ProcessConfig` 编辑，具有保存/加载/删除功能
- 支持方法队列创建和 scouting (扫描) 计划定义

### method_run.py - 方法运行模块
- 类: `MethodRunModule(ttk.Frame)`
- 运行模式: 编辑器配置、保存的方法、scouting (扫描) 扫描、队列批处理
- 带进度报告的线程化模拟执行
- 结果自动保存到数据库

### result_analysis.py - 结果分析模块
- 类: `ResultAnalysisModule(ttk.Frame)`
- 带色谱图显示的历史结果浏览
- 带对齐选项的叠加比较 (无/进样/峰)
- UV 数据、峰报告和叠加比较的 CSV 导出

### simulation_engine.py - 模拟引擎
- 类: `SimulationEngine`
- 包装 CADETProcess 用于离子交换色谱模拟
- 从 ProcessConfig 构建 CADET 过程模型
- SMA (Steric Mass Action，空间质量作用) 结合模型

### config_models.py - 数据模型
- `ProcessConfig`: 完整的方法配置
- `MethodSettings`: 柱、组分、梯度参数
- `ElutionStep`: 梯度步骤定义
- `create_default_config()`: 默认配置工厂
- `apply_parameter_value()`: 用于 scouting (扫描) 的动态参数设置
- `NumpyEncoder`: numpy 类型的 JSON 序列化器

### env_manager.py - 环境管理器
- 类: `EnvironmentManager`
- 扫描系统中的 Conda 环境、venv、系统 Python
- 使用带有列表形式命令的 subprocess (防止注入)

### cadet_env.py - CADET DLL 初始化
- 将 CADET-SHOWCASE 环境目录添加到 DLL 搜索路径
- 导入时自动初始化 (在任何 CADET 导入之前调用)
- 支持 PATH 和 `os.add_dll_directory()` (Python 3.8+)

## 依赖

| 包 | 用途 |
|---------|---------|
| Python 3.8+ | 运行时 |
| tkinter | GUI 框架 (内置) |
| numpy | 数值数组 |
| matplotlib | 色谱图绘制 |
| scipy | 峰检测 (find_peaks) |
| CADET-Process | 色谱模拟 |
| CADET-Core | 模拟求解器 (通过 DLL) |

## 数据库架构

```sql
methods (id, method_name, config_json, created_at, updated_at)
simulation_results (id, result_name, config_json, time_data,
                    concentration_data, peak_report_json, created_at)
scouting_plans (id, plan_name, method_id, parameter_name,
                values_json, created_at)
method_queues (id, queue_name, method_ids_json, status, created_at)
```

## 启动

```bash
conda activate CADET-SHOWCASE
python run_app.py
# 或双击 start.bat
```