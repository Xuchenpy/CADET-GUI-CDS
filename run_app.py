"""
CADET CDS - Chromatography Simulation System
Application Entry Point

Usage:
  conda activate CADET-SHOWCASE
  python run_app.py

Dependencies:
  - Python 3.8+
  - tkinter (built-in)
  - matplotlib
  - numpy
  - scipy
  - CADET-Process
"""

import sys
import os

# Add application directory to path
app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Initialize CADET environment (DLL paths)
import cadet_env

# Launch application
from app import main

if __name__ == '__main__':
    main()
