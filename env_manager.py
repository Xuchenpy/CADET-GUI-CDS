"""
CADET CDS - 环境管理模块

功能:
  - 扫描系统中的 Conda 环境
  - 扫描 venv/virtualenv 环境
  - 检测系统级 Python 安装
  - 检查 CADET 相关包的安装状态
"""

import os
import sys
import subprocess
import json
import re
from typing import List, Dict, Optional


class EnvironmentManager:
    """Python环境扫描与CADET包检测管理器"""

    # CADET 相关必需/可选包
    CADET_PACKAGES = [
        'cadet-process',
        'cadet-python',
        'numpy',
        'scipy',
        'matplotlib',
        'pandas',
    ]

    def __init__(self):
        self._cached_envs: Optional[List[Dict]] = None

    def scan_conda_environments(self) -> List[Dict]:
        """扫描所有 Conda 环境"""
        envs = []
        conda_exe = self._find_conda_executable()
        if not conda_exe:
            return envs

        try:
            result = subprocess.run(
                [conda_exe, 'env', 'list', '--json'],
                capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == 'win32' else 0
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for env_path in data.get('envs', []):
                    if os.path.isdir(env_path):
                        python_exe = self._get_python_in_env(env_path)
                        if python_exe:
                            name = os.path.basename(env_path)
                            if env_path == data.get('envs', [''])[0]:
                                name = 'base'
                            envs.append({
                                'type': 'conda',
                                'name': name,
                                'path': env_path,
                                'python': python_exe,
                            })
        except (subprocess.TimeoutExpired, json.JSONDecodeError,
                FileNotFoundError, OSError):
            pass

        return envs

    def scan_venv_environments(self, search_dirs: Optional[List[str]] = None
                               ) -> List[Dict]:
        """扫描 venv/virtualenv 环境
        
        默认搜索用户主目录下的常见位置
        """
        envs = []
        if search_dirs is None:
            home = os.path.expanduser('~')
            search_dirs = [
                os.path.join(home, '.virtualenvs'),
                os.path.join(home, 'envs'),
                os.path.join(home, '.venvs'),
            ]

        for base_dir in search_dirs:
            if not os.path.isdir(base_dir):
                continue
            try:
                for entry in os.listdir(base_dir):
                    env_path = os.path.join(base_dir, entry)
                    if not os.path.isdir(env_path):
                        continue
                    # 检查是否是有效的 venv
                    python_exe = self._get_python_in_env(env_path)
                    pyvenv_cfg = os.path.join(env_path, 'pyvenv.cfg')
                    if python_exe and os.path.isfile(pyvenv_cfg):
                        envs.append({
                            'type': 'venv',
                            'name': entry,
                            'path': env_path,
                            'python': python_exe,
                        })
            except OSError:
                continue

        return envs

    def scan_system_python(self) -> List[Dict]:
        """检测系统级 Python 安装"""
        envs = []
        # 当前运行的 Python
        current_python = sys.executable
        if current_python and os.path.isfile(current_python):
            envs.append({
                'type': 'system',
                'name': f'Python {sys.version_info.major}.{sys.version_info.minor}',
                'path': os.path.dirname(current_python),
                'python': current_python,
            })
        return envs

    def get_all_environments(self) -> List[Dict]:
        """获取所有检测到的Python环境"""
        if self._cached_envs is not None:
            return self._cached_envs

        all_envs = []
        all_envs.extend(self.scan_system_python())
        all_envs.extend(self.scan_conda_environments())
        all_envs.extend(self.scan_venv_environments())

        # 去重（基于python路径）
        seen = set()
        unique_envs = []
        for env in all_envs:
            key = os.path.normcase(os.path.normpath(env['python']))
            if key not in seen:
                seen.add(key)
                unique_envs.append(env)

        self._cached_envs = unique_envs
        return unique_envs

    def check_packages(self, python_exe: Optional[str] = None
                       ) -> Dict[str, Dict]:
        """检查指定Python环境中CADET相关包的安装状态
        
        Returns:
            dict: {package_name: {'installed': bool, 'version': str}}
        """
        if python_exe is None:
            python_exe = sys.executable

        result = {}
        for pkg in self.CADET_PACKAGES:
            result[pkg] = {'installed': False, 'version': ''}

        try:
            proc = subprocess.run(
                [python_exe, '-m', 'pip', 'list', '--format=json'],
                capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == 'win32' else 0
            )
            if proc.returncode == 0:
                installed_pkgs = json.loads(proc.stdout)
                pkg_map = {
                    p['name'].lower().replace('_', '-'): p['version']
                    for p in installed_pkgs
                }
                for pkg in self.CADET_PACKAGES:
                    normalized = pkg.lower().replace('_', '-')
                    if normalized in pkg_map:
                        result[pkg] = {
                            'installed': True,
                            'version': pkg_map[normalized]
                        }
        except (subprocess.TimeoutExpired, json.JSONDecodeError,
                FileNotFoundError, OSError):
            pass

        return result

    def _find_conda_executable(self) -> Optional[str]:
        """查找 conda 可执行文件"""
        # 方法1: 从环境变量 CONDA_EXE
        conda_exe = os.environ.get('CONDA_EXE')
        if conda_exe and os.path.isfile(conda_exe):
            return conda_exe

        # 方法2: 从 PATH 查找
        if sys.platform == 'win32':
            names = ['conda.exe', 'conda.bat']
        else:
            names = ['conda']

        path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        for d in path_dirs:
            for name in names:
                full = os.path.join(d, name)
                if os.path.isfile(full):
                    return full

        # 方法3: Windows 常见位置
        if sys.platform == 'win32':
            common_roots = [
                os.path.expanduser('~'),
                os.environ.get('LOCALAPPDATA', ''),
                os.environ.get('ProgramData', ''),
                'C:\\',
            ]
            for root in common_roots:
                if not root:
                    continue
                for sub in ['Anaconda3', 'Miniconda3', 'anaconda3', 'miniconda3']:
                    conda_path = os.path.join(root, sub, 'condabin', 'conda.bat')
                    if os.path.isfile(conda_path):
                        return conda_path
                    conda_path = os.path.join(root, sub, 'Scripts', 'conda.exe')
                    if os.path.isfile(conda_path):
                        return conda_path

        return None

    def _get_python_in_env(self, env_path: str) -> Optional[str]:
        """获取环境目录中的 Python 可执行文件路径"""
        if sys.platform == 'win32':
            candidates = [
                os.path.join(env_path, 'python.exe'),
                os.path.join(env_path, 'Scripts', 'python.exe'),
            ]
        else:
            candidates = [
                os.path.join(env_path, 'bin', 'python'),
                os.path.join(env_path, 'bin', 'python3'),
            ]

        for c in candidates:
            if os.path.isfile(c):
                return c
        return None
