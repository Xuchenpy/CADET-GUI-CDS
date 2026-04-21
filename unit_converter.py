"""
独立单位转换工具类 - CADET-Process 层析模拟系统 v6

负责所有单位换算逻辑，UI 层仅调用本模块的转换函数，不掺杂计算逻辑。
支持:
  - 流速: mL/min <-> m³/s
  - 时间: Time(s) <-> CV <-> Volume(mL)
  - 体积: m³ <-> mL
"""

import numpy as np


class UnitConverter:
    """
    单位转换工具类

    所有方法均为静态方法，无需实例化即可调用。
    内部存储标准单位: 时间=秒(s)，流速=m³/s，体积=m³
    """

    # ============================================================
    # 流速转换: mL/min <-> m³/s
    # ============================================================

    @staticmethod
    def ml_min_to_m3_s(flow_ml_min: float) -> float:
        """mL/min -> m³/s"""
        return flow_ml_min / (1000.0 * 1000.0 * 60.0)

    @staticmethod
    def m3_s_to_ml_min(flow_m3_s: float) -> float:
        """m³/s -> mL/min"""
        return flow_m3_s * 1000.0 * 1000.0 * 60.0

    # ============================================================
    # 柱体积转换: m³ <-> mL
    # ============================================================

    @staticmethod
    def m3_to_ml(volume_m3: float) -> float:
        """m³ -> mL"""
        return volume_m3 * 1e6

    @staticmethod
    def ml_to_m3(volume_ml: float) -> float:
        """mL -> m³"""
        return volume_ml * 1e-6

    # ============================================================
    # 柱体积计算
    # ============================================================

    @staticmethod
    def calc_column_volume_ml(length_m: float, diameter_m: float) -> float:
        """
        计算柱体积 (mL)

        Column_Volume_mL = π * (diameter/2)² * length * 1e6
        """
        return np.pi * (diameter_m / 2.0) ** 2 * length_m * 1e6

    # ============================================================
    # 时间 <-> CV (柱体积数)
    # ============================================================

    @staticmethod
    def time_s_to_cv(time_s: float, column_volume_ml: float, flow_rate_ml_min: float) -> float:
        """
        时间(秒) -> 柱体积数(CV)

        CV = time_s * (flow_rate_mL_min / 60) / column_volume_mL
        """
        if column_volume_ml <= 0:
            return 0.0
        flow_rate_ml_s = flow_rate_ml_min / 60.0
        return time_s * flow_rate_ml_s / column_volume_ml

    @staticmethod
    def cv_to_time_s(cv: float, column_volume_ml: float, flow_rate_ml_min: float) -> float:
        """
        柱体积数(CV) -> 时间(秒)

        time_s = CV * column_volume_mL / (flow_rate_mL_min / 60)
        """
        flow_rate_ml_s = flow_rate_ml_min / 60.0
        if flow_rate_ml_s <= 0:
            return 0.0
        return cv * column_volume_ml / flow_rate_ml_s

    # ============================================================
    # 时间 <-> 体积 (mL)
    # ============================================================

    @staticmethod
    def time_s_to_volume_ml(time_s: float, flow_rate_ml_min: float) -> float:
        """
        时间(秒) -> 体积(mL)

        Volume_mL = time_s * (flow_rate_mL_min / 60)
        """
        return time_s * (flow_rate_ml_min / 60.0)

    @staticmethod
    def volume_ml_to_time_s(volume_ml: float, flow_rate_ml_min: float) -> float:
        """
        体积(mL) -> 时间(秒)

        time_s = Volume_mL / (flow_rate_mL_min / 60)
        """
        flow_rate_ml_s = flow_rate_ml_min / 60.0
        if flow_rate_ml_s <= 0:
            return 0.0
        return volume_ml / flow_rate_ml_s

    # ============================================================
    # 批量时间轴转换 (numpy 数组)
    # ============================================================

    @staticmethod
    def convert_time_array(
        time_s: np.ndarray,
        target_unit: str,
        column_volume_ml: float,
        flow_rate_ml_min: float,
    ) -> tuple:
        """
        将时间数组从秒转换为目标单位。

        Parameters
        ----------
        time_s : np.ndarray
            时间数组（秒）
        target_unit : str
            目标单位: 'seconds', 'cv', 'volume_ml'
        column_volume_ml : float
            柱体积 (mL)
        flow_rate_ml_min : float
            流速 (mL/min)

        Returns
        -------
        tuple(np.ndarray, str)
            (转换后的时间数组, X轴标签)
        """
        if target_unit == 'cv':
            flow_rate_ml_s = flow_rate_ml_min / 60.0
            if column_volume_ml > 0:
                converted = time_s * flow_rate_ml_s / column_volume_ml
            else:
                converted = time_s
            return converted, 'Column Volumes / CV'
        elif target_unit == 'volume_ml':
            flow_rate_ml_s = flow_rate_ml_min / 60.0
            converted = time_s * flow_rate_ml_s
            return converted, 'Volume / mL'
        else:
            return time_s.copy(), 'Time / s'

    # ============================================================
    # 标量时间转换 (用于 UI 输入框显示)
    # ============================================================

    @staticmethod
    def convert_duration(
        value: float,
        from_unit: str,
        to_unit: str,
        column_volume_ml: float,
        flow_rate_ml_min: float,
    ) -> float:
        """
        将持续时间从一个单位转换为另一个单位。

        Parameters
        ----------
        value : float
            输入值
        from_unit : str
            源单位: 'seconds', 'cv', 'volume_ml'
        to_unit : str
            目标单位: 'seconds', 'cv', 'volume_ml'
        column_volume_ml : float
            柱体积 (mL)
        flow_rate_ml_min : float
            流速 (mL/min)

        Returns
        -------
        float
            转换后的值
        """
        # 先转为秒
        if from_unit == 'cv':
            time_s = UnitConverter.cv_to_time_s(value, column_volume_ml, flow_rate_ml_min)
        elif from_unit == 'volume_ml':
            time_s = UnitConverter.volume_ml_to_time_s(value, flow_rate_ml_min)
        else:
            time_s = value

        # 再转为目标单位
        if to_unit == 'cv':
            return UnitConverter.time_s_to_cv(time_s, column_volume_ml, flow_rate_ml_min)
        elif to_unit == 'volume_ml':
            return UnitConverter.time_s_to_volume_ml(time_s, flow_rate_ml_min)
        else:
            return time_s


if __name__ == '__main__':
    # 测试
    print("=== 单位转换测试 ===")

    # 流速转换
    flow_ml = 4.01
    flow_m3 = UnitConverter.ml_min_to_m3_s(flow_ml)
    print(f"流速: {flow_ml} mL/min = {flow_m3:.6e} m³/s")
    print(f"反向: {UnitConverter.m3_s_to_ml_min(flow_m3):.4f} mL/min")

    # 柱体积
    cv_ml = UnitConverter.calc_column_volume_ml(0.014, 0.02)
    print(f"\n柱体积: {cv_ml:.4f} mL")

    # 时间 <-> CV
    time_s = 100.0
    cv = UnitConverter.time_s_to_cv(time_s, cv_ml, flow_ml)
    print(f"\n{time_s}s = {cv:.4f} CV")
    print(f"反向: {UnitConverter.cv_to_time_s(cv, cv_ml, flow_ml):.4f} s")

    # 时间 <-> Volume
    vol = UnitConverter.time_s_to_volume_ml(time_s, flow_ml)
    print(f"\n{time_s}s = {vol:.4f} mL")
    print(f"反向: {UnitConverter.volume_ml_to_time_s(vol, flow_ml):.4f} s")
