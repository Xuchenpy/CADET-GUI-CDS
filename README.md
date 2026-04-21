# CADET GUI CDS

CADET GUI CDS (Chromatography Data System，色谱数据系统) 是一个基于 CADET-Core/CADET-Process 的离子交换色谱模拟GUI桌面应用程序。使用 Python Tkinter 构建，它提供方法编辑、模拟执行和结果分析功能；用于层析纯化过程演示与数据拟合。

## 功能

### 方法编辑器
- 柱参数配置（长度、直径、颗粒大小、孔隙率）
- 动态组分管理（添加/删除/重命名蛋白质组分）
- 带可视化步骤卡片的梯度洗脱步骤设计
- SMA（Steric Mass Action）结合模型参数编辑
- Scouting/Method Queue

### 模拟引擎
- CADET-Core 驱动的 IEX 色谱模拟
- 支持多组分的 SMA 结合模型
- 通用速率模型（GRM）柱模型
- 带实时进度的异步执行

### 结果分析
- 带色谱图显示的历史结果浏览
- 带缩放/平移的交互式 matplotlib 图表
- 自动峰检测（高度、保留时间、半峰宽、分辨率）
- 带对齐选项的叠加比较
  - 无对齐 / 进样标记 / 主峰对齐
- UV 数据、峰报告和叠加比较的 CSV 导出

### 其他
- 用于持久存储的 SQLite 本地数据库（无需服务器）
- 单位转换支持（min/s/cv）
- 用于 Conda、venv 和系统 Python 的 Python 环境扫描器
- CADET 包检测和验证

## 先决条件

- **Python** 3.8 或更高版本
- **Anaconda**（推荐）或任何 Python 发行版
- **CADET-Core** 求解器（DLL/共享库）

## 安装

### 1. 创建 Conda 环境

```bash
conda create -n CADET-SHOWCASE python=3.10
conda activate CADET-SHOWCASE
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

或手动安装：

```bash
pip install cadet-process numpy scipy matplotlib
```

### 3. 安装 CADET-Core

CADET-Core 是求解器后端。请按照[官方安装指南](https://cadet.github.io/master/getting_started/installation.html)进行安装。

在 Windows 上使用 Anaconda：

```bash
conda install -c conda-forge cadet
```

## 使用

### 选项 A：双击启动器

运行 `start.bat`（Windows）- 它会自动检测 Python 环境，检查依赖项，并启动应用程序。

### 选项 B：命令行（推荐）

```bash
#前提是创建一个名为“CADET-SHOWCASE”的虚拟环境
conda activate CADET-SHOWCASE 
python run_app.py
```

### 快速开始

1. **方法编辑器** 标签：配置柱参数、组分和梯度步骤
2. 点击 **保存** 将方法存储到数据库
3. **方法运行** 标签：选择"从编辑器运行"或"运行保存的方法"
4. 实时查看色谱图和峰分析
5. **结果分析** 标签：浏览保存的结果，叠加比较，导出 CSV

## 项目结构

```
akta_chromsim_app/
  run_app.py              应用程序入口点
  start.bat               带环境检测的 Windows 启动器
  app.py                  主应用程序窗口和标签管理
  cadet_env.py            CADET DLL 路径初始化
  
  # 核心 GUI 模块
  method_editor.py        方法编辑器（柱、组分、梯度、SMA）
  method_run.py           方法运行（模拟执行和可视化）
  result_analysis.py      结果分析（浏览、叠加、导出）
  
  # 业务逻辑
  config_models.py        数据模型（ProcessConfig、MethodSettings 等）
  simulation_engine.py    CADET 模拟包装器
  peak_analysis.py        峰检测和分辨率计算
  visualization.py        Matplotlib 色谱图绘制
  unit_converter.py       单位转换工具
  
  # 数据和持久化
  db_manager.py           SQLite 数据库管理器
  csv_export.py           CSV 导出工具
  
  # 配置和主题
  styles.py               Tkinter 主题和样式定义
  env_manager.py          Python 环境扫描器
  
  # 生成的数据
  cadet_cds.db            SQLite 数据库（自动创建）
  tmp/                    临时模拟文件
```

## 架构

应用程序遵循分层架构：

| 层 | 模块 | 职责 |
|-------|---------|----------------|
| **入口** | `run_app.py`, `start.bat` | 启动和环境设置 |
| **GUI** | `app.py`, `method_editor.py`, `method_run.py`, `result_analysis.py` | 用户界面 |
| **逻辑** | `config_models.py`, `simulation_engine.py`, `peak_analysis.py` | 核心算法 |
| **可视化** | `visualization.py`, `styles.py` | 绘图和主题 |
| **持久化** | `db_manager.py`, `csv_export.py` | 数据存储和导出 |
| **工具** | `unit_converter.py`, `env_manager.py`, `cadet_env.py` | 支持函数 |

## 关键技术

| 技术 | 用途 |
|------------|---------|
| [CADET-Core](https://cadet.github.io/) | 色谱模拟求解器 |
| [CADET-Process](https://cadet-process.readthedocs.io/) | 过程建模框架 |
| Python Tkinter | 桌面 GUI 框架 |
| Matplotlib | 科学绘图 |
| NumPy / SciPy | 数值计算和峰检测 |
| SQLite | 本地数据持久化 |

## 数据库架构

| 表 | 描述 |
|-------|-------------|
| `methods` | 保存的方法配置（JSON） |
| `simulation_results` | 模拟输出（时间/浓度数组） |
| `scouting_plans` | 参数扫描定义 |
| `scouting_results` | 单个扫描运行结果 |
| `method_queues` | 批处理执行队列定义 |
| `queue_items` | 队列中的单个项目 |

## 配置

### CADET 环境路径

编辑 `cadet_env.py` 设置正确的 CADET-Core 安装路径：

```python
CADET_ENV_ROOT = r"D:\anaconda\envs\cadet-showcase"#前提是创建一个名为“CADET-SHOWCASE”的虚拟环境
```

### 数据库位置

SQLite 数据库 (`cadet_cds.db`) 在首次运行时会自动在应用程序目录中创建。不需要外部数据库服务器。

## 故障排除

| 问题 | 解决方案 |
|-------|----------|
| CADET DLL not found | 验证 CADET-Core 是否已安装；编辑 `cadet_env.py` 路径 |
| 应用程序窗口闪烁并关闭 | 从命令行运行以查看错误输出 |
| 模拟失败 | 检查 CADET-Process 安装：`pip install cadet-process` |
| 结果分析中无结果 | 点击"刷新"按钮从数据库重新加载 |
| 启动时导入错误 | 验证所有依赖项：`pip install -r requirements.txt` |

## 贡献



### 代码风格

- 遵循 PEP 8 约定
- 适当使用类型提示
- 配置模型使用数据类
- 模拟执行的线程安全设计
- 所有 GUI 更新必须在主线程上进行

## 许可证

此项目按原样提供，用于研究和教育目的。