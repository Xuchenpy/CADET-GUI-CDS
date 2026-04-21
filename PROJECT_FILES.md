# CADET CDS - Project File Documentation

Detailed description of every file and directory in the project.

## Directory Overview

```
akta_chromsim_app/
  __pycache__/            Python bytecode cache (auto-generated)
  tmp/
    simulation_files/     Temporary CADET solver files during simulation
  run_app.py              [Entry] Application launcher
  start.bat               [Entry] Windows batch launcher
  app.py                  [GUI]   Main application window
  cadet_env.py            [Init]  CADET DLL path setup
  method_editor.py        [GUI]   Method Editor module
  method_run.py           [GUI]   Method Run module
  result_analysis.py      [GUI]   Result Analysis module
  config_models.py        [Logic] Data models & configuration
  simulation_engine.py    [Logic] CADET simulation wrapper
  peak_analysis.py        [Logic] Peak detection & analysis
  visualization.py        [Logic] Chromatogram plotting
  unit_converter.py       [Logic] Unit conversion utilities
  db_manager.py           [Data]  SQLite database manager
  csv_export.py           [Data]  CSV export utilities
  styles.py               [Theme] Tkinter UI styling
  env_manager.py          [Util]  Python environment scanner
  cadet_cds.db            [Data]  SQLite database (auto-created)
  akta_cadet.db           [Data]  Legacy database (unused)
  requirements.txt        [Doc]   Python dependency list
  README.md               [Doc]   GitHub project page
  CODE_DOCUMENTATION.md   [Doc]   Code architecture documentation
  USER_GUIDE.md           [Doc]   End-user guide
  PROJECT_FILES.md        [Doc]   This file
```
---

## Entry Point Files

### run_app.py (559 bytes)

**Purpose:** Application entry point script.

- Adds the application directory to `sys.path`
- Imports `cadet_env` to initialize CADET DLL paths before any CADET import
- Calls `main()` from `app.py` to launch the GUI
- This is the file users should execute: `python run_app.py`

**Dependencies:** `cadet_env.py`, `app.py`

### start.bat (5,090 bytes)

**Purpose:** Windows batch launcher with automated environment detection.

**Startup sequence (5 steps):**
1. Changes to script directory
2. Detects CADET-SHOWCASE conda environment Python (with fallbacks)
3. Checks core dependencies (tkinter, matplotlib, numpy, scipy, CADET-Process)
4. Verifies entry files exist (`run_app.py`, `cadet_env.py`)
5. Launches `run_app.py` with error reporting

**Error handling:** Shows diagnostic messages and suggested fixes for common issues.

### cadet_env.py (1,532 bytes)

**Purpose:** CADET-Core DLL path initialization.

- Configures `CADET_ENV_ROOT` pointing to the cadet-showcase Conda environment
- Adds environment `bin/`, `Library/bin/`, `Library/lib/` to DLL search paths
- Uses both `os.environ["PATH"]` and `os.add_dll_directory()` (Python 3.8+)
- Auto-initializes on import (module-level `init_cadet_env()` call)
- Must be imported before any CADET-Process imports

**Key configuration:**
```python
CADET_ENV_ROOT = r"D://anaconda//envs//cadet-showcase"
```
---

## GUI Modules

### app.py (8,998 bytes)

**Purpose:** Main application window integrating all modules.

**Class: `CadetCDSApp`**
- Creates root Tk window with teal-themed header
- Menu bar: File (Exit), Tools (Scan Environments, Detect Packages), Help (About)
- 3-tab Notebook: Method Editor, Method Run, Result Analysis
- Manages shared `app_context` dict for inter-module communication
- Initializes `DatabaseManager` instance shared across all modules
- Handles application lifecycle (cleanup on close, tab change refresh)

**Inter-module communication:**
- `run_scouting_callback`: Method Editor triggers scouting in Method Run
- `run_queue_callback`: Method Editor triggers queue run in Method Run
- `get_editor_config`: Method Run reads current editor configuration

**Dependencies:** `styles`, `db_manager`, `method_editor`, `method_run`, `result_analysis`, `env_manager`

### method_editor.py (49,165 bytes)

**Purpose:** Complete method editing interface - the largest module.

**Class: `MethodEditorModule(ttk.Frame)`**

**Toolbar buttons:** New, Open, Save, Save As, Delete

**Sub-tabs:**
- **Method Tab:** Global parameters (column, flow rate, initial salt) + inline step cards
  - Dynamic step management: Add/delete Equilibration, Load, Wash, Elution steps
  - Component system: Add/remove/rename protein components
  - SMA parameter table: Per-component binding parameters
  - Unit selector (seconds / CV / mL) with real-time conversion
- **Scouting Tab:** Parameter sweep configuration
  - Checkbox grid of numeric parameters
  - Value range editor with min/max/step
  - Plan save/load/delete/run
- **Queue Tab:** Method batch queue
  - Create named queues, add methods, run sequentially
  - Queue status tracking and deletion

**Key data flow:**
- UI widgets -> `_sync_cards_to_config()` -> `ProcessConfig` object
- `ProcessConfig` -> `_refresh_all()` -> UI widgets
- Save: `ProcessConfig.to_json()` -> `db.save_method()`
- Load: `db.get_method()` -> `ProcessConfig.from_json()`

**Dependencies:** `config_models`, `unit_converter`, `styles`, `db_manager`
### method_run.py (18,201 bytes)

**Purpose:** Simulation execution interface with real-time visualization.

**Class: `MethodRunModule(ttk.Frame)`**

**Run modes:**
- **Run from Editor:** Execute current Method Editor configuration
- **Run Saved Method:** Select and run a method from the database
- **Scouting:** Batch parameter sweep execution
- **Queue:** Sequential multi-method execution

**UI layout:**
- Matplotlib figure with NavigationToolbar (chromatogram display)
- Run log text area with timestamped messages
- Peak analysis Treeview (component, height, retention time, FWHM, resolution)
- Batch run progress Treeview (for scouting/queue tracking)
- Progress bar and status label

**Execution:** Background thread via `SimulationEngine.simulate_async()` with
`root.after()` callbacks for thread-safe GUI updates.

**Dependencies:** `config_models`, `simulation_engine`, `visualization`, `peak_analysis`, `styles`, `db_manager`

### result_analysis.py (18,377 bytes)

**Purpose:** Historical result browsing, comparison, and export.

**Class: `ResultAnalysisModule(ttk.Frame)`**

**Toolbar buttons:** Refresh, Export CSV, Export Peaks, Delete Result

**Features:**
- **Result List:** Treeview showing all saved results (ID, name, date)
- **Chromatogram Tab:** Single result chromatogram with NavigationToolbar
- **Overlay Tab:** Multi-result comparison chart
  - Add/remove results to overlay dataset
  - Alignment modes: None, Injection Marker, Main Peak
- **Peak Analysis Tab:** Treeview with component, height, retention time, FWHM, resolution
- **CSV Export:** UV data, peak reports, overlay comparison data

**Dependencies:** `config_models`, `visualization`, `peak_analysis`, `unit_converter`, `styles`, `csv_export`, `db_manager`
---

## Business Logic Modules

### config_models.py (29,016 bytes)

**Purpose:** Core data models for chromatography process configuration.

**Classes (dataclasses):**
- `NumpyEncoder(json.JSONEncoder)` - JSON serializer for numpy types
- `ComponentManager` - Centralized component add/remove/rename with cascade updates
- `SMAParams` - Steric Mass Action binding parameters (ka, kd, nu, sigma per component)
- `ColumnParams` - Column geometry (length, diameter, particle_radius, porosity)
- `InletParams` - Inlet flow rate configuration
- `MethodSettings` - Combines all above with component list and initial conditions
- `StepModule` - Base class for process steps
- `EquilibrationStep`, `LoadStep`, `WashStep`, `ElutionStep` - Step types
- `ProcessConfig` - Top-level configuration containing sequence of steps

**Key functions:**
- `create_default_config()` - Factory for default IEX configuration
- `extract_numeric_parameters()` - Extract all tunable parameters for scouting
- `apply_parameter_value()` - Programmatically set parameter by path string

**Serialization:** `ProcessConfig.to_json()` / `ProcessConfig.from_json()` for database storage

### simulation_engine.py (10,898 bytes)

**Purpose:** CADET-Process simulation wrapper.

**Class: `SimulationEngine`**
- `build_process(config)` - Constructs CADETProcess Process from ProcessConfig
  - Creates ComponentSystem, SMA binding model, GRM column, Inlet/Outlet
  - Builds FlowSheet with connections
  - Adds Events for each process step (salt concentration changes)
- `simulate(config)` - Synchronous simulation execution
- `simulate_async(config, callback, error_callback)` - Background thread execution
- `get_outlet_data(results)` - Extracts time/concentration arrays from results

**CADET imports:** ComponentSystem, StericMassAction, Inlet, GeneralRateModel,
Outlet, FlowSheet, Process, Cadet simulator

### peak_analysis.py (12,276 bytes)

**Purpose:** Chromatographic peak detection and analysis.

**Classes:**
- `PeakInfo` - Data container for single peak results
  - Fields: component, peak_height, retention_time, fwhm, baseline_width
- `PeakAnalyzer` - Peak detection engine
  - Uses scipy.signal.find_peaks (with fallback simple algorithm)
  - Calculates: peak height (mM), retention time (s), FWHM, baseline width
  - Resolution (Rs) between adjacent peaks
  - Generates structured report dict

### visualization.py (12,854 bytes)

**Purpose:** Publication-quality chromatogram plotting.

**Class: `ChromatogramPlotter`**
- `plot_chromatogram()` - Main plotting method
  - Dual Y-axes: protein concentration (left), salt concentration (right)
  - Individual component curves (dashed) + total protein (solid)
  - Process step boundary annotations with shading
  - Peak markers with arrows
  - Configurable X-axis units (seconds / CV / mL)
- `plot_comparison()` - Simulation vs. experiment comparison

### unit_converter.py (7,578 bytes)

**Purpose:** Chromatography unit conversion utilities.

**Class: `UnitConverter` (static methods only)**
- Flow rate: mL/min <-> m3/s
- Volume: m3 <-> mL
- Time: seconds <-> column volumes (CV) <-> volume (mL)
- Array conversions: bulk time array transformation with axis labels
---

## Data & Persistence Modules

### db_manager.py (17,824 bytes)

**Purpose:** SQLite database management for all persistent data.

**Class: `DatabaseManager`**

**Database file:** `cadet_cds.db` (auto-created in application directory)

**Tables and operations:**

| Table | Key Operations |
|-------|----------------|
| `methods` | save, get, get_filtered, delete |
| `simulation_results` | save (with numpy BLOB), get, get_data, delete |
| `scouting_plans` | create, get, update_status, delete |
| `scouting_results` | add, update, get |
| `method_queues` | create, get, update_status, delete |
| `queue_items` | add, get, update_status |

**NumPy serialization:** Arrays are stored as binary BLOBs using
`numpy.save()`/`numpy.load()` with `io.BytesIO` buffers.

**Thread safety:** Uses `contextmanager` for connection lifecycle management.

### csv_export.py (4,898 bytes)

**Purpose:** CSV file export utilities.

**Functions:**
- `export_chromatogram_csv(path, time, concentration, components)` - UV data export
- `export_peak_report_csv(path, report)` - Peak analysis report export
- `export_overlay_csv(path, datasets)` - Multi-result overlay data export

---

## Configuration & Utility Modules

### styles.py (8,373 bytes)

**Purpose:** Tkinter theme and visual style definitions.

**Color palette:**
- Primary: Teal (#0D8070), Dark Navy (#1B2838)
- Background: Main (#F0F2F5), Content (#FFFFFF), Header (#E8EAED)
- Text: Primary (#2C3E50), Light (#FFFFFF), Secondary (#6C7B8A)
- Component colors: Distinct colors for up to 10 protein components

**Functions:**
- `apply_cds_theme(root)` - Apply complete ttk style configuration
- `configure_root_window(root, title)` - Set window size, position, icon

### env_manager.py (8,584 bytes)

**Purpose:** Python environment scanning and CADET package verification.

**Class: `EnvironmentManager`**
- `scan_conda_environments()` - Detect Conda environments via `conda env list --json`
- `scan_venv_environments()` - Detect venv/virtualenv in common directories
- `scan_system_python()` - Detect system Python installations
- `get_all_environments()` - Combined scan with deduplication
- `check_packages(python_exe)` - Verify CADET package installation

**Security:** Uses `subprocess.run()` with list-form commands (no shell injection).

---

## Data Files

### cadet_cds.db
Active SQLite database. Auto-created on first run. Contains all saved methods,
simulation results, scouting plans, and queues.

### akta_cadet.db
Legacy database from earlier version. Not used by current application.
Can be safely deleted.

### tmp/simulation_files/
Temporary directory for CADET solver working files during simulation.
Cleaned up on application close.

### __pycache__/
Python bytecode cache. Auto-generated, safe to delete.

---

## Documentation Files

| File | Description |
|------|-------------|
| `README.md` | GitHub project page with features, installation, usage |
| `requirements.txt` | Python package dependency list |
| `CODE_DOCUMENTATION.md` | Code architecture and module overview |
| `USER_GUIDE.md` | End-user operation guide |
| `PROJECT_FILES.md` | This file - detailed file descriptions |

---

## Module Dependency Graph

```
run_app.py
  -> cadet_env.py
  -> app.py
       -> styles.py
       -> db_manager.py
       -> env_manager.py
       -> method_editor.py
       |    -> config_models.py -> unit_converter.py
       |    -> styles.py
       -> method_run.py
       |    -> config_models.py
       |    -> simulation_engine.py -> cadet_env.py, CADETProcess
       |    -> visualization.py -> config_models.py, unit_converter.py
       |    -> peak_analysis.py -> unit_converter.py
       |    -> styles.py
       -> result_analysis.py
            -> config_models.py
            -> visualization.py
            -> peak_analysis.py
            -> csv_export.py
            -> styles.py
```
