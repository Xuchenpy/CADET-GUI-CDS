@echo off
chcp 65001 >nul 2>&1

REM ============================================
REM  CADET CDS - Chromatography Simulation System
REM  CDS Launcher
REM ============================================

echo.
echo  ============================================
echo   CADET CDS - Chromatography Simulation
echo   CDS Launcher v1.0
echo  ============================================
echo.

REM --------------------------------------------------
REM Step 1: Change to script directory
REM --------------------------------------------------
cd /d "%~dp0"
echo  [1/5] Working directory: %CD%

REM --------------------------------------------------
REM Step 2: Detect CADET-SHOWCASE conda environment Python
REM --------------------------------------------------
set "CADET_PYTHON=D:\anaconda\envs\CADET-SHOWCASE\python.exe"
set "CONDA_BAT=D:\anaconda\condabin\conda.bat"
set "ANACONDA_PYTHON=D:\anaconda\python.exe"

echo  [2/5] Detecting Python environment...

if exist "%CADET_PYTHON%" (
    echo        Found CADET-SHOWCASE environment: %CADET_PYTHON%
    set "PYTHON_EXE=%CADET_PYTHON%"
    goto :check_deps
)

REM Try conda activate
if exist "%CONDA_BAT%" (
    echo        Trying conda activate CADET-SHOWCASE ...
    call "%CONDA_BAT%" activate CADET-SHOWCASE
    if %ERRORLEVEL% EQU 0 (
        set "PYTHON_EXE=python"
        echo        conda environment activated
        goto :check_deps
    ) else (
        echo        [WARNING] conda activate failed
    )
)

REM Fallback to system Python
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo        [WARNING] CADET-SHOWCASE not found, using system Python
    set "PYTHON_EXE=python"
    goto :check_deps
)

REM No Python found
echo.
echo  [ERROR] No Python environment found!
echo.
echo  Please check:
echo    1. Anaconda installed at: D:\anaconda
echo    2. CADET-SHOWCASE environment created
echo    3. Packages installed: CADET-Process, numpy, scipy, matplotlib
echo.
echo  Create environment:
echo    conda create -n CADET-SHOWCASE python=3.10
echo    conda activate CADET-SHOWCASE
echo    pip install cadet-process numpy scipy matplotlib
echo.
goto :exit_fail

REM --------------------------------------------------
REM Step 3: Check core dependencies
REM --------------------------------------------------
:check_deps
echo  [3/5] Checking core dependencies...

"%PYTHON_EXE%" -c "import tkinter; import matplotlib; import numpy; import scipy; print('OK')" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [ERROR] Core dependencies missing! Checking modules...
    echo.
    "%PYTHON_EXE%" -c "import tkinter" 2>&1 || echo        - tkinter not installed
    "%PYTHON_EXE%" -c "import matplotlib" 2>&1 || echo        - matplotlib not installed
    "%PYTHON_EXE%" -c "import numpy" 2>&1 || echo        - numpy not installed
    "%PYTHON_EXE%" -c "import scipy" 2>&1 || echo        - scipy not installed
    echo.
    echo  Install missing modules in CADET-SHOWCASE:
    echo    pip install matplotlib numpy scipy
    echo.
    goto :exit_fail
)
echo        tkinter, matplotlib, numpy, scipy ... OK

REM Check CADET-Process
"%PYTHON_EXE%" -c "import CADETProcess" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo        [WARNING] CADET-Process not installed, simulation unavailable
    echo        Install: pip install cadet-process
) else (
    echo        CADET-Process ... OK
)

REM --------------------------------------------------
REM Step 4: Check entry files
REM --------------------------------------------------
echo  [4/5] Checking entry files...

if not exist "run_app.py" (
    echo.
    echo  [ERROR] Entry file run_app.py not found!
    echo  Current directory: %CD%
    echo  Please verify script is in the correct application directory
    echo.
    goto :exit_fail
)
echo        run_app.py ... OK

if not exist "cadet_env.py" (
    echo        [WARNING] cadet_env.py not found, CADET DLL init may fail
) else (
    echo        cadet_env.py ... OK
)

REM --------------------------------------------------
REM Step 5: Launch CDS system
REM --------------------------------------------------
echo  [5/5] Launching CDS system...
echo.
echo  ============================================
echo   Starting CADET CDS interface...
echo   Please wait for the application window
echo  ============================================
echo.

"%PYTHON_EXE%" run_app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  ============================================
    echo   [ERROR] CDS system exited abnormally (code: %ERRORLEVEL%)
    echo  ============================================
    echo.
    echo  Possible causes:
    echo    1. CADET DLL not configured properly
    echo    2. Module import error
    echo    3. Resource conflict
    echo.
    goto :exit_fail
)

echo.
echo  CDS system exited normally
echo.
goto :exit_ok

:exit_fail
echo.
echo  Press any key to exit...
pause >nul
exit /b 1

:exit_ok
echo  Press any key to exit...
pause >nul
exit /b 0
