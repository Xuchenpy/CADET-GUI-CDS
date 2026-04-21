"""
模块化配置数据模型 v6 - CADET-Process 层析模拟系统

主要升级:
  - 中心化 ComponentSystem 对象，所有表格列的增减严格依赖此对象
  - 动态组分管理: 添加/删除组分时自动级联更新所有关联参数
  - 所有时间相关参数统一存储为 float 秒
"""

import json
import copy
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

from unit_converter import UnitConverter


# ============================================================
# 辅助工具
# ============================================================

class NumpyEncoder(json.JSONEncoder):
    """支持 numpy 类型的 JSON 编码器"""
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        return super().default(obj)


# ============================================================
# 中心化组分管理系统
# ============================================================

class ComponentManager:
    """
    中心化组分管理器

    维护组分列表，所有 SMA 参数、浓度数组的增减严格通过此对象管理。
    Salt 组分 (索引0) 禁止删除，以保持模拟稳定性。
    """

    def __init__(self, names: List[str] = None):
        self._names = list(names) if names else ['Salt', 'A', 'B', 'C']

    @property
    def names(self) -> List[str]:
        return list(self._names)

    @property
    def n_comp(self) -> int:
        return len(self._names)

    @property
    def protein_names(self) -> List[str]:
        return [n for n in self._names if n.lower() != 'salt']

    @property
    def protein_indices(self) -> List[int]:
        return [i for i, n in enumerate(self._names) if n.lower() != 'salt']

    @property
    def salt_index(self) -> Optional[int]:
        for i, n in enumerate(self._names):
            if n.lower() == 'salt':
                return i
        return None

    def add_component(self, name: str, defaults: Dict[str, float] = None) -> int:
        """
        添加组分，返回新组分的索引。

        Parameters
        ----------
        name : str
            组分名称
        defaults : dict, optional
            各参数的默认值

        Returns
        -------
        int
            新组分索引
        """
        self._names.append(name)
        return len(self._names) - 1

    def remove_component(self, index: int) -> str:
        """
        删除组分，返回被删除的组分名。

        禁止删除 Salt 组分 (索引 0)。

        Parameters
        ----------
        index : int
            要删除的组分索引

        Returns
        -------
        str
            被删除的组分名

        Raises
        ------
        ValueError
            如果试图删除 Salt 或索引越界
        """
        if index < 0 or index >= len(self._names):
            raise ValueError(f"索引 {index} 越界 (组分数: {len(self._names)})")
        if self._names[index].lower() == 'salt':
            raise ValueError("禁止删除 Salt 组分，以保持模拟稳定性")
        if len(self._names) <= 2:
            raise ValueError("至少保留 Salt + 1 个蛋白组分")
        removed = self._names.pop(index)
        return removed

    def rename_component(self, index: int, new_name: str):
        """重命名组分"""
        if index < 0 or index >= len(self._names):
            raise ValueError(f"索引 {index} 越界")
        self._names[index] = new_name

    def pad_or_trim(self, arr: List[float], default_val: float = 0.0) -> List[float]:
        """将数组调整为当前组分数，多裁少补"""
        arr = list(arr)
        n = self.n_comp
        if len(arr) > n:
            return arr[:n]
        while len(arr) < n:
            arr.append(default_val)
        return arr

    def insert_default(self, arr: List[float], index: int, default_val: float = 0.0) -> List[float]:
        """在指定索引处插入默认值"""
        arr = list(arr)
        arr.append(default_val)
        return arr

    def remove_at(self, arr: List[float], index: int) -> List[float]:
        """从列表中移除指定索引"""
        arr = list(arr)
        if 0 <= index < len(arr):
            arr.pop(index)
        return arr


# ============================================================
# SMA 绑定模型参数
# ============================================================

@dataclass
class SMAParams:
    """Steric Mass Action 结合模型参数"""
    is_kinetic: bool = True
    adsorption_rate: List[float] = field(default_factory=lambda: [0.0, 35.5, 1.59, 7.7])
    desorption_rate: List[float] = field(default_factory=lambda: [0.0, 1000.0, 1000.0, 1000.0])
    characteristic_charge: List[float] = field(default_factory=lambda: [0.0, 4.7, 5.29, 3.7])
    steric_factor: List[float] = field(default_factory=lambda: [0.0, 11.83, 10.6, 10.0])
    capacity: float = 1200.0

    def add_component(self, defaults: Dict[str, float] = None):
        """为新组分追加默认 SMA 参数"""
        d = defaults or {}
        self.adsorption_rate.append(d.get('adsorption_rate', 0.0))
        self.desorption_rate.append(d.get('desorption_rate', 1000.0))
        self.characteristic_charge.append(d.get('characteristic_charge', 0.0))
        self.steric_factor.append(d.get('steric_factor', 0.0))

    def remove_component(self, index: int):
        """删除指定索引的 SMA 参数"""
        for arr in [self.adsorption_rate, self.desorption_rate,
                    self.characteristic_charge, self.steric_factor]:
            if 0 <= index < len(arr):
                arr.pop(index)

    def sync_to_n(self, n: int):
        """同步各数组长度为 n"""
        for attr_name in ['adsorption_rate', 'desorption_rate',
                          'characteristic_charge', 'steric_factor']:
            arr = getattr(self, attr_name)
            while len(arr) < n:
                arr.append(0.0)
            while len(arr) > n:
                arr.pop()


# ============================================================
# 色谱柱参数
# ============================================================

@dataclass
class ColumnParams:
    """色谱柱 GeneralRateModel 参数"""
    length: float = 0.014               # m
    diameter: float = 0.02              # m
    bed_porosity: float = 0.37
    particle_radius: float = 4.5e-5     # m
    particle_porosity: float = 0.75
    axial_dispersion: float = 5.75e-8   # m^2/s
    film_diffusion: List[float] = field(default_factory=lambda: [6.9e-6, 6.9e-6, 6.9e-6, 6.9e-6])
    pore_diffusion: List[float] = field(default_factory=lambda: [7e-10, 6.07e-11, 6.07e-11, 6.07e-11])
    surface_diffusion: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])

    @property
    def column_volume(self) -> float:
        """柱体积 (m³)"""
        return np.pi * (self.diameter / 2) ** 2 * self.length

    @property
    def column_volume_ml(self) -> float:
        """柱体积 (mL)"""
        return UnitConverter.m3_to_ml(self.column_volume)

    @property
    def bed_volume(self) -> float:
        """床体积 (m³)"""
        return self.column_volume * self.bed_porosity

    def add_component(self, defaults: Dict[str, float] = None):
        """为新组分追加默认传质参数"""
        d = defaults or {}
        self.film_diffusion.append(d.get('film_diffusion', 6.9e-6))
        self.pore_diffusion.append(d.get('pore_diffusion', 6.07e-11))
        self.surface_diffusion.append(d.get('surface_diffusion', 0.0))

    def remove_component(self, index: int):
        """删除指定索引的传质参数"""
        for arr in [self.film_diffusion, self.pore_diffusion, self.surface_diffusion]:
            if 0 <= index < len(arr):
                arr.pop(index)

    def sync_to_n(self, n: int):
        """同步各数组长度为 n"""
        for attr_name, default_val in [('film_diffusion', 6.9e-6),
                                        ('pore_diffusion', 6.07e-11),
                                        ('surface_diffusion', 0.0)]:
            arr = getattr(self, attr_name)
            while len(arr) < n:
                arr.append(default_val)
            while len(arr) > n:
                arr.pop()


# ============================================================
# 入口参数
# ============================================================

@dataclass
class InletParams:
    """入口单元参数 (流速以 m³/s 存储)"""
    flow_rate: float = 6.683738370512285e-8  # m³/s

    @property
    def flow_rate_ml_min(self) -> float:
        """流速 (mL/min)"""
        return UnitConverter.m3_s_to_ml_min(self.flow_rate)

    @flow_rate_ml_min.setter
    def flow_rate_ml_min(self, value: float):
        """通过 mL/min 设置流速"""
        self.flow_rate = UnitConverter.ml_min_to_m3_s(value)


# ============================================================
# 方法设置（全局参数）
# ============================================================

@dataclass
class MethodSettings:
    """Method Settings 模块 - 全局初始化参数"""
    component_manager: ComponentManager = field(default_factory=ComponentManager)
    sma_params: SMAParams = field(default_factory=SMAParams)
    column_params: ColumnParams = field(default_factory=ColumnParams)
    inlet_params: InletParams = field(default_factory=InletParams)
    initial_salt_concentration: float = 50.0  # mM

    @property
    def components(self) -> List[str]:
        return self.component_manager.names

    @property
    def n_comp(self) -> int:
        return self.component_manager.n_comp

    def add_component(self, name: str):
        """添加组分并级联更新所有关联参数"""
        self.component_manager.add_component(name)
        self.sma_params.add_component()
        self.column_params.add_component()

    def remove_component(self, index: int):
        """删除组分并级联更新所有关联参数"""
        self.component_manager.remove_component(index)
        self.sma_params.remove_component(index)
        self.column_params.remove_component(index)

    def sync_all(self):
        """同步所有参数数组到当前组分数"""
        n = self.n_comp
        self.sma_params.sync_to_n(n)
        self.column_params.sync_to_n(n)


# ============================================================
# 工艺步骤模块定义
# ============================================================

@dataclass
class StepModule:
    """工艺步骤基类"""
    step_type: str = ""
    step_id: str = ""
    duration_seconds: float = 0.0          # 统一存储为秒
    concentration: List[float] = field(default_factory=list)
    display_name: str = ""

    def get_duration_seconds(self, column_volume: float = 0, flow_rate: float = 0) -> float:
        """返回持续时间（秒）"""
        return self.duration_seconds

    def add_component(self, default_conc: float = 0.0):
        """为新组分追加默认浓度"""
        self.concentration.append(default_conc)

    def remove_component(self, index: int):
        """删除指定索引的浓度"""
        if 0 <= index < len(self.concentration):
            self.concentration.pop(index)

    def sync_conc_to_n(self, n: int, default_val: float = 0.0):
        """同步浓度列表长度为 n"""
        while len(self.concentration) < n:
            self.concentration.append(default_val)
        while len(self.concentration) > n:
            self.concentration.pop()


@dataclass
class EquilibrationStep(StepModule):
    """平衡步骤"""
    step_type: str = "Equilibration"
    display_name: str = "Equilibration"
    duration_seconds: float = 0.0
    concentration: List[float] = field(default_factory=lambda: [50.0, 0.0, 0.0, 0.0])


@dataclass
class LoadStep(StepModule):
    """上样步骤"""
    step_type: str = "Load"
    display_name: str = "Sample Application"
    duration_seconds: float = 9.0
    concentration: List[float] = field(default_factory=lambda: [50.0, 1.0, 1.0, 1.0])


@dataclass
class WashStep(StepModule):
    """洗涤步骤"""
    step_type: str = "Wash"
    display_name: str = "Column Wash"
    duration_seconds: float = 81.0
    concentration: List[float] = field(default_factory=lambda: [50.0, 0.0, 0.0, 0.0])


@dataclass
class ElutionStep(StepModule):
    """洗脱步骤"""
    step_type: str = "Elution"
    display_name: str = "Elution"
    duration_seconds: float = 1910.0
    elution_mode: str = "linear_gradient"  # "isocratic" 或 "linear_gradient"
    start_concentration: List[float] = field(default_factory=lambda: [50.0, 0.0, 0.0, 0.0])
    end_concentration: List[float] = field(default_factory=lambda: [500.0, 0.0, 0.0, 0.0])
    concentration: List[float] = field(default_factory=lambda: [500.0, 0.0, 0.0, 0.0])

    def add_component(self, default_conc: float = 0.0):
        super().add_component(default_conc)
        self.start_concentration.append(default_conc)
        self.end_concentration.append(default_conc)

    def remove_component(self, index: int):
        super().remove_component(index)
        if 0 <= index < len(self.start_concentration):
            self.start_concentration.pop(index)
        if 0 <= index < len(self.end_concentration):
            self.end_concentration.pop(index)

    def sync_conc_to_n(self, n: int, default_val: float = 0.0):
        super().sync_conc_to_n(n, default_val)
        while len(self.start_concentration) < n:
            self.start_concentration.append(default_val)
        while len(self.start_concentration) > n:
            self.start_concentration.pop()
        while len(self.end_concentration) < n:
            self.end_concentration.append(default_val)
        while len(self.end_concentration) > n:
            self.end_concentration.pop()


# ============================================================
# 完整工艺流程配置
# ============================================================

@dataclass
class ProcessConfig:
    """完整的层析工艺流程配置"""
    process_name: str = "IEX_Chromatography_Run"
    project_name: str = ""
    filler_name: str = ""
    method_settings: MethodSettings = field(default_factory=MethodSettings)
    sequence: List[StepModule] = field(default_factory=list)

    def calculate_cycle_time(self) -> float:
        """计算总循环时间（秒）"""
        total = 0.0
        for step in self.sequence:
            total += step.get_duration_seconds()
        return total

    def get_step_boundaries(self) -> List[Dict[str, Any]]:
        """获取每个步骤的时间边界信息"""
        boundaries = []
        current_time = 0.0
        for step in self.sequence:
            dur = step.get_duration_seconds()
            boundaries.append({
                "step_id": step.step_id,
                "step_type": step.step_type,
                "display_name": step.display_name,
                "start_time": current_time,
                "end_time": current_time + dur,
                "duration": dur,
            })
            current_time += dur
        return boundaries

    def add_component(self, name: str):
        """向全局添加组分，级联更新所有步骤"""
        self.method_settings.add_component(name)
        for step in self.sequence:
            step.add_component(0.0)

    def remove_component(self, index: int):
        """从全局删除组分，级联更新所有步骤"""
        self.method_settings.remove_component(index)
        for step in self.sequence:
            step.remove_component(index)

    def sync_all(self):
        """同步所有数据到当前组分数"""
        n = self.method_settings.n_comp
        self.method_settings.sync_all()
        for step in self.sequence:
            step.sync_conc_to_n(n)

    def to_dict(self) -> dict:
        """序列化为字典"""
        data = {
            'process_name': self.process_name,
            'project_name': self.project_name,
            'filler_name': self.filler_name,
            'method_settings': {
                'components': self.method_settings.components,
                'sma_params': asdict(self.method_settings.sma_params),
                'column_params': {
                    k: v for k, v in asdict(self.method_settings.column_params).items()
                },
                'inlet_params': asdict(self.method_settings.inlet_params),
                'initial_salt_concentration': self.method_settings.initial_salt_concentration,
            },
            'sequence': [asdict(s) for s in self.sequence],
        }
        return data

    def to_json(self, filepath: str = None) -> str:
        """序列化为 JSON"""
        data = self.to_dict()
        json_str = json.dumps(data, indent=2, cls=NumpyEncoder, ensure_ascii=False)
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_str)
        return json_str

    @staticmethod
    def from_json(filepath: str) -> 'ProcessConfig':
        """从 JSON 文件加载配置"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return ProcessConfig._from_dict(data)

    @staticmethod
    def _from_dict(data: dict) -> 'ProcessConfig':
        """从字典重建配置"""
        ms_data = data.get('method_settings', {})
        components = ms_data.get('components', ['Salt', 'A', 'B', 'C'])
        comp_mgr = ComponentManager(components)

        col_data = ms_data.get('column_params', {})
        col_data = {k: v for k, v in col_data.items()
                    if k not in ('column_volume', 'bed_volume', 'column_volume_ml')}

        method_settings = MethodSettings(
            component_manager=comp_mgr,
            sma_params=SMAParams(**ms_data.get('sma_params', {})),
            column_params=ColumnParams(**col_data),
            inlet_params=InletParams(**ms_data.get('inlet_params', {})),
            initial_salt_concentration=ms_data.get('initial_salt_concentration', 50.0),
        )

        step_map = {
            'Equilibration': EquilibrationStep,
            'Load': LoadStep,
            'Wash': WashStep,
            'Elution': ElutionStep,
        }

        sequence = []
        for s in data.get('sequence', []):
            step_type = s.get('step_type', '')
            cls = step_map.get(step_type, StepModule)
            known_fields = {f.name for f in cls.__dataclass_fields__.values()}
            # v5 兼容: 将 duration_value/duration_type 转为 duration_seconds
            if 'duration_value' in s and 'duration_seconds' not in s:
                s['duration_seconds'] = float(s['duration_value'])
            filtered = {k: v for k, v in s.items() if k in known_fields}
            sequence.append(cls(**filtered))

        return ProcessConfig(
            process_name=data.get('process_name', 'IEX_Run'),
            project_name=data.get('project_name', ''),
            filler_name=data.get('filler_name', ''),
            method_settings=method_settings,
            sequence=sequence,
        )


# ============================================================
# 默认配置工厂
# ============================================================

def create_default_config() -> ProcessConfig:
    """
    创建默认配置，参数来源于 CADET load wash elution.py 案例。
    流程: Load -> Wash -> Linear Gradient Elution
    """
    config = ProcessConfig(
        process_name="IEX_LWE_Default",
        method_settings=MethodSettings(),
        sequence=[
            EquilibrationStep(
                step_id="eq_1",
                duration_seconds=0.0,
                concentration=[50.0, 0.0, 0.0, 0.0],
            ),
            LoadStep(
                step_id="load_1",
                duration_seconds=9.0,
                concentration=[50.0, 1.0, 1.0, 1.0],
            ),
            WashStep(
                step_id="wash_1",
                duration_seconds=81.0,
                concentration=[50.0, 0.0, 0.0, 0.0],
            ),
            ElutionStep(
                step_id="elution_1",
                elution_mode="linear_gradient",
                duration_seconds=1910.0,
                start_concentration=[50.0, 0.0, 0.0, 0.0],
                end_concentration=[500.0, 0.0, 0.0, 0.0],
            ),
        ],
    )
    return config


# ============================================================
# Scouting V2: 参数提取与应用工具
# ============================================================

def extract_numeric_parameters(config: ProcessConfig) -> List[Dict[str, Any]]:
    """
    从 ProcessConfig 中提取所有可扫描的数值参数。

    Returns
    -------
    List[Dict] 每个字典包含:
        - path: str  参数路径 (如 "SMA.capacity", "Column.length",
                      "sequence[2].duration_seconds")
        - display_name: str  可读显示名
        - value: float  当前值
        - category: str  分类名
    """
    params = []
    ms = config.method_settings
    sma = ms.sma_params
    col = ms.column_params
    comps = ms.components
    n = ms.n_comp

    # ---- SMA 参数 ----
    params.append({
        'path': 'SMA.capacity',
        'display_name': 'SMA Capacity (Lambda)',
        'value': sma.capacity,
        'category': 'SMA',
    })
    sma_arrays = [
        ('adsorption_rate', 'Adsorption Rate (ka)'),
        ('desorption_rate', 'Desorption Rate (kd)'),
        ('characteristic_charge', 'Char. Charge (v)'),
        ('steric_factor', 'Steric Factor (sigma)'),
    ]
    for attr, label in sma_arrays:
        arr = getattr(sma, attr)
        for i in range(min(n, len(arr))):
            params.append({
                'path': f'SMA.{attr}[{i}]',
                'display_name': f'{label} [{comps[i]}]',
                'value': arr[i],
                'category': 'SMA',
            })

    # ---- Column 参数 ----
    col_scalars = [
        ('length', 'Column Length (m)'),
        ('diameter', 'Column Diameter (m)'),
        ('bed_porosity', 'Bed Porosity'),
        ('particle_radius', 'Particle Radius (m)'),
        ('particle_porosity', 'Particle Porosity'),
        ('axial_dispersion', 'Axial Dispersion (m^2/s)'),
    ]
    for attr, label in col_scalars:
        params.append({
            'path': f'Column.{attr}',
            'display_name': label,
            'value': getattr(col, attr),
            'category': 'Column',
        })
    col_arrays = [
        ('film_diffusion', 'Film Diffusion'),
        ('pore_diffusion', 'Pore Diffusion'),
        ('surface_diffusion', 'Surface Diffusion'),
    ]
    for attr, label in col_arrays:
        arr = getattr(col, attr)
        for i in range(min(n, len(arr))):
            params.append({
                'path': f'Column.{attr}[{i}]',
                'display_name': f'{label} [{comps[i]}]',
                'value': arr[i],
                'category': 'Column',
            })

    # ---- Inlet / Global 参数 ----
    params.append({
        'path': 'Inlet.flow_rate_ml_min',
        'display_name': 'Flow Rate (mL/min)',
        'value': ms.inlet_params.flow_rate_ml_min,
        'category': 'Global',
    })
    params.append({
        'path': 'Global.initial_salt_concentration',
        'display_name': 'Initial Salt Concentration (mM)',
        'value': ms.initial_salt_concentration,
        'category': 'Global',
    })

    # ---- 步骤参数 ----
    for idx, step in enumerate(config.sequence):
        cat = f'Step[{idx}] {step.display_name}'
        prefix = f'sequence[{idx}]'

        params.append({
            'path': f'{prefix}.duration_seconds',
            'display_name': f'{step.display_name} - Duration (s)',
            'value': step.duration_seconds,
            'category': cat,
        })

        # 浓度数组
        for ci in range(min(n, len(step.concentration))):
            params.append({
                'path': f'{prefix}.concentration[{ci}]',
                'display_name': f'{step.display_name} - Conc [{comps[ci]}]',
                'value': step.concentration[ci],
                'category': cat,
            })

        # ElutionStep 特有
        if isinstance(step, ElutionStep):
            for ci in range(min(n, len(step.start_concentration))):
                params.append({
                    'path': f'{prefix}.start_concentration[{ci}]',
                    'display_name': f'{step.display_name} - Start Conc [{comps[ci]}]',
                    'value': step.start_concentration[ci],
                    'category': cat,
                })
            for ci in range(min(n, len(step.end_concentration))):
                params.append({
                    'path': f'{prefix}.end_concentration[{ci}]',
                    'display_name': f'{step.display_name} - End Conc [{comps[ci]}]',
                    'value': step.end_concentration[ci],
                    'category': cat,
                })

    return params


def apply_parameter_value(config: ProcessConfig, param_path: str, value: float):
    """
    将指定的参数值应用到 ProcessConfig 中。

    Parameters
    ----------
    config : ProcessConfig
    param_path : str
        参数路径，如 "SMA.capacity", "Column.length",
        "sequence[2].duration_seconds", "Inlet.flow_rate_ml_min"
    value : float
        要设置的值
    """
    ms = config.method_settings

    # 解析数组索引: "attr[i]" -> (attr, i)
    def _parse_index(s):
        if '[' in s:
            name = s[:s.index('[')]
            idx = int(s[s.index('[') + 1:s.index(']')])
            return name, idx
        return s, None

    parts = param_path.split('.', 1)
    if len(parts) != 2:
        return

    section, attr_str = parts
    attr_name, arr_idx = _parse_index(attr_str)

    if section == 'SMA':
        sma = ms.sma_params
        if arr_idx is not None:
            arr = getattr(sma, attr_name, None)
            if arr is not None and arr_idx < len(arr):
                arr[arr_idx] = value
        else:
            setattr(sma, attr_name, value)

    elif section == 'Column':
        col = ms.column_params
        if arr_idx is not None:
            arr = getattr(col, attr_name, None)
            if arr is not None and arr_idx < len(arr):
                arr[arr_idx] = value
        else:
            setattr(col, attr_name, value)

    elif section == 'Inlet':
        if attr_name == 'flow_rate_ml_min':
            ms.inlet_params.flow_rate_ml_min = value

    elif section == 'Global':
        if attr_name == 'initial_salt_concentration':
            ms.initial_salt_concentration = value

    elif section.startswith('sequence'):
        # "sequence[2].duration_seconds" -> section="sequence[2]", attr_str="duration_seconds"
        seq_name, seq_idx = _parse_index(section)
        if seq_idx is not None and seq_idx < len(config.sequence):
            step = config.sequence[seq_idx]
            if arr_idx is not None:
                arr = getattr(step, attr_name, None)
                if arr is not None and arr_idx < len(arr):
                    arr[arr_idx] = value
            else:
                setattr(step, attr_name, value)


if __name__ == '__main__':
    cfg = create_default_config()
    print("默认配置:")
    print(cfg.to_json())
    print(f"\n总循环时间: {cfg.calculate_cycle_time():.1f} 秒")
    print(f"柱体积: {cfg.method_settings.column_params.column_volume_ml:.4f} mL")
    print(f"流速: {cfg.method_settings.inlet_params.flow_rate_ml_min:.4f} mL/min")
    print("\n步骤边界:")
    for b in cfg.get_step_boundaries():
        print(f"  {b['display_name']}: {b['start_time']:.1f}s - {b['end_time']:.1f}s")

    # 测试动态组分管理
    print("\n=== 动态组分管理测试 ===")
    cfg.add_component("D")
    print(f"添加组分 D 后: {cfg.method_settings.components}")
    print(f"SMA 吸附速率: {cfg.method_settings.sma_params.adsorption_rate}")
    cfg.remove_component(4)
    print(f"删除组分 D 后: {cfg.method_settings.components}")
