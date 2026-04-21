"""
模拟执行引擎 v6 - CADET-Process 层析模拟系统

主要升级:
  - 线程安全: CADET 模拟在后台线程运行
  - 停止功能: 支持通过 stop_event 终止模拟
  - 代码生成器: 生成 CADETProcess.processModel.Process 对象，所有时间参数为 float 秒
"""

import cadet_env  # 初始化 CADET DLL 路径（必须在 CADETProcess 导入之前）

import threading
import numpy as np

from CADETProcess.processModel import ComponentSystem
from CADETProcess.processModel import StericMassAction
from CADETProcess.processModel import Inlet, GeneralRateModel, Outlet
from CADETProcess.processModel import FlowSheet
from CADETProcess.processModel import Process
from CADETProcess.simulator import Cadet

from config_models import ProcessConfig, ElutionStep, create_default_config


class SimulationEngine:
    """
    模拟执行引擎 v6

    线程安全设计:
      - simulate_async(): 在后台线程运行模拟，UI 保持响应
      - stop(): 发出停止信号
      - 回调: on_complete / on_error / on_progress
    """

    def __init__(self):
        self.simulator = Cadet()
        self._last_process = None
        self._last_results = None
        self._stop_event = threading.Event()
        self._sim_thread = None
        self._lock = threading.Lock()

    def build_process(self, config: ProcessConfig) -> Process:
        """
        根据 ProcessConfig 构建 CADET-Process 对象。
        生成的 Process 对象中所有时间参数均为 float 秒。

        Parameters
        ----------
        config : ProcessConfig
            完整的工艺流程配置

        Returns
        -------
        Process
            CADETProcess.processModel.Process 对象
        """
        ms = config.method_settings
        n_comp = ms.n_comp

        # 1. 组分系统
        component_system = ComponentSystem()
        for comp in ms.components:
            component_system.add_component(comp)

        # 2. SMA 结合模型
        sma = ms.sma_params
        binding_model = StericMassAction(component_system, name='SMA')
        binding_model.is_kinetic = sma.is_kinetic
        binding_model.adsorption_rate = sma.adsorption_rate[:n_comp]
        binding_model.desorption_rate = sma.desorption_rate[:n_comp]
        binding_model.characteristic_charge = sma.characteristic_charge[:n_comp]
        binding_model.steric_factor = sma.steric_factor[:n_comp]
        binding_model.capacity = sma.capacity

        # 3. 入口单元
        inlet = Inlet(component_system, name='inlet')
        inlet.flow_rate = ms.inlet_params.flow_rate  # m³/s

        # 4. 色谱柱 (GeneralRateModel)
        cp = ms.column_params
        column = GeneralRateModel(component_system, name='column')
        column.binding_model = binding_model
        column.length = cp.length
        column.diameter = cp.diameter
        column.bed_porosity = cp.bed_porosity
        column.particle_radius = cp.particle_radius
        column.particle_porosity = cp.particle_porosity
        column.axial_dispersion = cp.axial_dispersion
        column.film_diffusion = cp.film_diffusion[:n_comp]
        column.pore_diffusion = cp.pore_diffusion[:n_comp]
        column.surface_diffusion = cp.surface_diffusion[:n_comp]

        # 初始条件
        init_salt = ms.initial_salt_concentration
        c_init = [init_salt] + [0.0] * (n_comp - 1)
        column.c = c_init
        column.cp = c_init
        column.q = [binding_model.capacity] + [0.0] * (n_comp - 1)

        # 5. 出口
        outlet = Outlet(component_system, name='outlet')

        # 6. 流程图
        flow_sheet = FlowSheet(component_system)
        flow_sheet.add_unit(inlet)
        flow_sheet.add_unit(column)
        flow_sheet.add_unit(outlet, product_outlet=True)
        flow_sheet.add_connection(inlet, column)
        flow_sheet.add_connection(column, outlet)

        # 7. 计算时间轴 (float 秒)
        cycle_time = config.calculate_cycle_time()
        if cycle_time <= 0:
            cycle_time = 2000.0

        process = Process(flow_sheet, config.process_name)
        process.cycle_time = float(cycle_time)

        # 8. 添加工艺步骤事件 (所有时间均为 float 秒)
        current_time = 0.0
        event_counter = {}

        for step in config.sequence:
            stype = step.step_type
            event_counter[stype] = event_counter.get(stype, 0) + 1
            idx = event_counter[stype]
            event_name = f"{stype.lower()}_{idx}"
            duration = step.get_duration_seconds()

            if stype == "Equilibration":
                if duration > 0:
                    c_eq = np.array(step.concentration[:n_comp], dtype=float)
                    process.add_event(
                        event_name, 'flow_sheet.inlet.c', c_eq, float(current_time)
                    )

            elif stype == "Load":
                c_load = np.array(step.concentration[:n_comp], dtype=float)
                process.add_event(
                    event_name, 'flow_sheet.inlet.c', c_load, float(current_time)
                )

            elif stype == "Wash":
                c_wash = np.array(step.concentration[:n_comp], dtype=float)
                process.add_event(
                    event_name, 'flow_sheet.inlet.c', c_wash, float(current_time)
                )

            elif stype == "Elution":
                if isinstance(step, ElutionStep):
                    if step.elution_mode == "isocratic":
                        c_elute = np.array(step.concentration[:n_comp], dtype=float)
                        process.add_event(
                            event_name, 'flow_sheet.inlet.c', c_elute, float(current_time)
                        )
                    else:  # linear_gradient
                        c_start = np.array(step.start_concentration[:n_comp], dtype=float)
                        c_end = np.array(step.end_concentration[:n_comp], dtype=float)
                        gradient_slope = (c_end - c_start) / duration if duration > 0 else np.zeros(n_comp)
                        c_gradient_poly = np.array(list(zip(c_start, gradient_slope)))
                        process.add_event(
                            event_name, 'flow_sheet.inlet.c', c_gradient_poly, float(current_time)
                        )
                else:
                    c_elute = np.array(step.concentration[:n_comp], dtype=float)
                    process.add_event(
                        event_name, 'flow_sheet.inlet.c', c_elute, float(current_time)
                    )

            current_time += duration

        self._last_process = process
        return process

    def simulate(self, config: ProcessConfig):
        """
        同步执行模拟

        Parameters
        ----------
        config : ProcessConfig
            工艺流程配置

        Returns
        -------
        simulation_results
            CADET-Process 模拟结果对象
        """
        process = self.build_process(config)
        with self._lock:
            self._last_results = self.simulator.simulate(process)
        return self._last_results

    def simulate_async(self, config: ProcessConfig,
                       on_complete=None, on_error=None, on_progress=None):
        """
        异步执行模拟（后台线程）

        Parameters
        ----------
        config : ProcessConfig
            工艺流程配置
        on_complete : callable(results, data)
            模拟完成回调
        on_error : callable(exception)
            模拟失败回调
        on_progress : callable(str)
            进度回调
        """
        self._stop_event.clear()

        def _worker():
            try:
                if on_progress:
                    on_progress("正在构建模型...")

                if self._stop_event.is_set():
                    if on_progress:
                        on_progress("模拟已停止")
                    return

                process = self.build_process(config)

                if self._stop_event.is_set():
                    if on_progress:
                        on_progress("模拟已停止")
                    return

                if on_progress:
                    on_progress("CADET 求解器计算中... 请稍候")

                with self._lock:
                    results = self.simulator.simulate(process)
                    self._last_results = results

                if self._stop_event.is_set():
                    if on_progress:
                        on_progress("模拟已停止")
                    return

                data = self.get_outlet_data(results)

                if on_complete:
                    on_complete(results, data)

            except Exception as e:
                if not self._stop_event.is_set():
                    if on_error:
                        on_error(e)

        self._sim_thread = threading.Thread(target=_worker, daemon=True)
        self._sim_thread.start()

    def stop(self):
        """发出停止信号"""
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        """模拟是否正在运行"""
        return self._sim_thread is not None and self._sim_thread.is_alive()

    def get_outlet_data(self, results=None):
        """
        提取出口浓度数据

        Returns
        -------
        dict
            包含 time, concentrations (各组分) 的字典
        """
        if results is None:
            results = self._last_results
        if results is None:
            raise RuntimeError("尚未执行模拟，请先调用 simulate()")

        solution = results.solution.column.outlet
        time = solution.time
        conc = solution.solution

        return {
            'time': time,
            'concentration': conc,
        }

    @property
    def last_process(self):
        return self._last_process

    @property
    def last_results(self):
        return self._last_results


def run_default_simulation():
    """使用默认配置运行模拟并返回结果"""
    config = create_default_config()
    engine = SimulationEngine()
    results = engine.simulate(config)
    data = engine.get_outlet_data()
    return config, engine, results, data


if __name__ == '__main__':
    print("使用默认配置运行模拟...")
    config, engine, results, data = run_default_simulation()
    print(f"模拟完成！时间点数量: {len(data['time'])}")
    print(f"浓度矩阵形状: {data['concentration'].shape}")
    print(f"组分: {config.method_settings.components}")
