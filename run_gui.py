"""
run_gui.py - Entry point untuk menjalankan GUI
"""
import sys
from pathlib import Path

# Pastikan folder proyek ada di sys.path
PROJECT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_DIR))

from gui import main

if __name__ == "__main__":
    main()

