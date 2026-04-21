"""
CADET Environment Initialization Module

Resolves CADET-Core DLL dependency issues:
Adds cadet-showcase environment bin directories to PATH and DLL search paths.

This module should be imported before all other CADET-related imports.
"""

import os
import sys

# CADET environment path configuration
CADET_ENV_ROOT = r"D:\anaconda\envs\cadet-showcase"
CADET_BIN_DIR = os.path.join(CADET_ENV_ROOT, "bin")

# Directories to add to DLL search path
_DLL_DIRS = [
    CADET_BIN_DIR,
    CADET_ENV_ROOT,
    os.path.join(CADET_ENV_ROOT, "Library", "bin"),
    os.path.join(CADET_ENV_ROOT, "Library", "lib"),
]

_initialized = False


def init_cadet_env():
    """
    Initialize CADET runtime environment.

    Adds cadet-showcase environment DLL directories to:
    1. os.environ['PATH'] - legacy DLL search path
    2. os.add_dll_directory() - Python 3.8+ Windows DLL search path
    """
    global _initialized
    if _initialized:
        return

    for dll_dir in _DLL_DIRS:
        if os.path.isdir(dll_dir):
            # Add to PATH environment variable
            if dll_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = dll_dir + ";" + os.environ.get("PATH", "")

            # Python 3.8+ Windows: explicitly register DLL search directory
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(dll_dir)
                except OSError:
                    pass

    _initialized = True


# Auto-initialize on module import
init_cadet_env()
