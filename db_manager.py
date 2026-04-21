"""
SQLite 数据库管理模块

表结构:
  - methods: 保存的方法配置
  - simulation_results: 模拟结果数据
  - scouting_plans: Scouting 批处理计划
  - scouting_results: Scouting 单次运行结果
  - method_queues: 方法队列
  - queue_items: 队列项
"""

import os
import sqlite3
import json
import time
import io
import numpy as np
from typing import List, Dict, Optional, Any, Tuple
from contextlib import contextmanager


DB_FILE_NAME = "cadet_cds.db"


class DatabaseManager:
    """SQLite 数据库管理器"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(db_dir, DB_FILE_NAME)
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_conn(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """初始化数据库表"""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS methods (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    method_name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    config_json TEXT NOT NULL,
                    project_name TEXT DEFAULT '',
                    filler_name TEXT DEFAULT '',
                    created_at REAL,
                    updated_at REAL
                );

                CREATE TABLE IF NOT EXISTS simulation_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    method_id INTEGER,
                    result_name TEXT DEFAULT '',
                    config_json TEXT,
                    time_data BLOB,
                    concentration_data BLOB,
                    peak_report_json TEXT,
                    created_at REAL,
                    FOREIGN KEY (method_id) REFERENCES methods(id)
                );

                CREATE TABLE IF NOT EXISTS scouting_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    method_id INTEGER NOT NULL,
                    plan_name TEXT DEFAULT '',
                    variables_json TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at REAL,
                    FOREIGN KEY (method_id) REFERENCES methods(id)
                );

                CREATE TABLE IF NOT EXISTS scouting_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    run_index INTEGER,
                    variable_values_json TEXT,
                    result_id INTEGER,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (plan_id) REFERENCES scouting_plans(id),
                    FOREIGN KEY (result_id) REFERENCES simulation_results(id)
                );

                CREATE TABLE IF NOT EXISTS method_queues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    queue_name TEXT DEFAULT '',
                    status TEXT DEFAULT 'idle',
                    created_at REAL
                );

                CREATE TABLE IF NOT EXISTS queue_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    queue_id INTEGER NOT NULL,
                    method_id INTEGER NOT NULL,
                    position INTEGER DEFAULT 0,
                    start_condition TEXT DEFAULT 'Immediate',
                    status TEXT DEFAULT 'pending',
                    result_id INTEGER,
                    FOREIGN KEY (queue_id) REFERENCES method_queues(id),
                    FOREIGN KEY (method_id) REFERENCES methods(id),
                    FOREIGN KEY (result_id) REFERENCES simulation_results(id)
                );
            """)

    # ============================================================
    # 方法管理
    # ============================================================

    def save_method(self, method_name: str,
                    config_json: str, description: str = "",
                    method_id: int = None,
                    project_name: str = "",
                    filler_name: str = "") -> int:
        """保存方法，如 method_id 不为 None 则更新"""
        now = time.time()
        with self._get_conn() as conn:
            if method_id:
                conn.execute(
                    "UPDATE methods SET method_name=?, description=?, "
                    "config_json=?, project_name=?, filler_name=?, "
                    "updated_at=? WHERE id=?",
                    (method_name, description, config_json,
                     project_name, filler_name, now, method_id)
                )
                return method_id
            else:
                cursor = conn.execute(
                    "INSERT INTO methods (method_name, description, "
                    "config_json, project_name, filler_name, "
                    "created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                    (method_name, description, config_json,
                     project_name, filler_name, now, now)
                )
                return cursor.lastrowid

    def get_methods(self) -> List[Dict]:
        """获取所有方法"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM methods ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_method(self, method_id: int) -> Optional[Dict]:
        """获取单个方法"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM methods WHERE id = ?", (method_id,)
            ).fetchone()
            return dict(row) if row else None

    def delete_method(self, method_id: int):
        """删除方法"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM methods WHERE id = ?", (method_id,))

    def get_methods_filtered(self, project_name: str = "",
                             filler_name: str = "") -> List[Dict]:
        """按 project_name / filler_name 过滤获取方法"""
        sql = "SELECT * FROM methods WHERE 1=1"
        params: list = []
        if project_name:
            sql += " AND project_name = ?"
            params.append(project_name)
        if filler_name:
            sql += " AND filler_name = ?"
            params.append(filler_name)
        sql += " ORDER BY updated_at DESC"
        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_distinct_project_names(self) -> List[str]:
        """获取所有不重复项目名称"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT project_name FROM methods "
                "WHERE project_name != '' "
                "ORDER BY project_name"
            ).fetchall()
            return [r['project_name'] for r in rows]

    def get_distinct_filler_names(self) -> List[str]:
        """获取所有不重复填料名称"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT filler_name FROM methods "
                "WHERE filler_name != '' "
                "ORDER BY filler_name"
            ).fetchall()
            return [r['filler_name'] for r in rows]

    # ============================================================
    # 模拟结果管理
    # ============================================================

    @staticmethod
    def _ndarray_to_bytes(arr: np.ndarray) -> bytes:
        """将 numpy 数组序列化为 bytes"""
        buf = io.BytesIO()
        np.save(buf, arr)
        return buf.getvalue()

    @staticmethod
    def _bytes_to_ndarray(data: bytes) -> np.ndarray:
        """从 bytes 反序列化 numpy 数组"""
        buf = io.BytesIO(data)
        return np.load(buf)

    def save_result(self, result_name: str,
                    config_json: str, time_data: np.ndarray,
                    concentration_data: np.ndarray,
                    peak_report_json: str = "",
                    method_id: int = None) -> int:
        """保存模拟结果"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO simulation_results "
                "(method_id, result_name, config_json, "
                "time_data, concentration_data, peak_report_json, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (method_id, result_name, config_json,
                 self._ndarray_to_bytes(time_data),
                 self._ndarray_to_bytes(concentration_data),
                 peak_report_json, time.time())
            )
            return cursor.lastrowid

    def get_results(self, limit: int = 50) -> List[Dict]:
        """获取模拟结果列表 (不含大数据)"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, method_id, result_name, "
                "peak_report_json, created_at "
                "FROM simulation_results "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_result_data(self, result_id: int) -> Optional[Dict]:
        """获取完整的模拟结果 (含数组数据)"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM simulation_results WHERE id = ?",
                (result_id,)
            ).fetchone()
            if row is None:
                return None
            d = dict(row)
            if d['time_data']:
                d['time_data'] = self._bytes_to_ndarray(d['time_data'])
            if d['concentration_data']:
                d['concentration_data'] = self._bytes_to_ndarray(d['concentration_data'])
            return d

    def delete_result(self, result_id: int):
        """删除模拟结果"""
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM simulation_results WHERE id = ?", (result_id,)
            )

    # ============================================================
    # Scouting 管理
    # ============================================================

    def create_scouting_plan(self, method_id: int,
                             plan_name: str, variables_json: str) -> int:
        """创建 Scouting 计划"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO scouting_plans "
                "(method_id, plan_name, variables_json, "
                "status, created_at) VALUES (?,?,?,?,?)",
                (method_id, plan_name, variables_json,
                 'pending', time.time())
            )
            return cursor.lastrowid

    def add_scouting_result(self, plan_id: int, run_index: int,
                            variable_values_json: str,
                            result_id: int = None,
                            status: str = 'pending') -> int:
        """添加 Scouting 单次运行记录"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO scouting_results "
                "(plan_id, run_index, variable_values_json, result_id, status) "
                "VALUES (?,?,?,?,?)",
                (plan_id, run_index, variable_values_json, result_id, status)
            )
            return cursor.lastrowid

    def update_scouting_result(self, scouting_result_id: int,
                               result_id: int, status: str):
        """更新 Scouting 单次运行结果"""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE scouting_results SET result_id=?, status=? WHERE id=?",
                (result_id, status, scouting_result_id)
            )

    def update_scouting_plan_status(self, plan_id: int, status: str):
        """更新 Scouting 计划状态"""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE scouting_plans SET status=? WHERE id=?",
                (status, plan_id)
            )

    def get_scouting_plans(self) -> List[Dict]:
        """获取 Scouting 计划"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM scouting_plans "
                "ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_scouting_results(self, plan_id: int) -> List[Dict]:
        """获取 Scouting 计划的所有运行结果"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM scouting_results WHERE plan_id = ? "
                "ORDER BY run_index",
                (plan_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_scouting_plan(self, plan_id: int):
        """删除 Scouting 计划及其关联结果"""
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM scouting_results WHERE plan_id = ?", (plan_id,))
            conn.execute(
                "DELETE FROM scouting_plans WHERE id = ?", (plan_id,))

    # ============================================================
    # Method Queue 管理
    # ============================================================

    def create_queue(self, queue_name: str) -> int:
        """创建方法队列"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO method_queues (queue_name, status, created_at) "
                "VALUES (?,?,?)",
                (queue_name, 'idle', time.time())
            )
            return cursor.lastrowid

    def add_queue_item(self, queue_id: int, method_id: int,
                       position: int, start_condition: str = 'Immediate') -> int:
        """添加队列项"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO queue_items "
                "(queue_id, method_id, position, start_condition, status) "
                "VALUES (?,?,?,?,?)",
                (queue_id, method_id, position, start_condition, 'pending')
            )
            return cursor.lastrowid

    def get_queues(self) -> List[Dict]:
        """获取方法队列"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM method_queues "
                "ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_queue_items(self, queue_id: int) -> List[Dict]:
        """获取队列项"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT qi.*, m.method_name FROM queue_items qi "
                "LEFT JOIN methods m ON qi.method_id = m.id "
                "WHERE qi.queue_id = ? ORDER BY qi.position",
                (queue_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def update_queue_item_status(self, item_id: int, status: str,
                                  result_id: int = None):
        """更新队列项状态"""
        with self._get_conn() as conn:
            if result_id is not None:
                conn.execute(
                    "UPDATE queue_items SET status=?, result_id=? WHERE id=?",
                    (status, result_id, item_id)
                )
            else:
                conn.execute(
                    "UPDATE queue_items SET status=? WHERE id=?",
                    (status, item_id)
                )

    def update_queue_status(self, queue_id: int, status: str):
        """更新队列状态"""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE method_queues SET status=? WHERE id=?",
                (status, queue_id)
            )

    def delete_queue(self, queue_id: int):
        """删除方法队列及其关联项"""
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM queue_items WHERE queue_id = ?", (queue_id,))
            conn.execute(
                "DELETE FROM method_queues WHERE id = ?", (queue_id,))

    # ============================================================
    # 运行时数据清理
    # ============================================================

    def clear_all_results(self):
        """清除所有模拟结果"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM simulation_results")

    def clear_runtime_data(self):
        """清除所有运行时数据 (关闭系统时调用)"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM scouting_results")
            conn.execute("DELETE FROM scouting_plans")
            conn.execute("DELETE FROM queue_items")
            conn.execute("DELETE FROM method_queues")
            conn.execute("DELETE FROM simulation_results")
