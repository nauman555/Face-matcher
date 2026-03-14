"""
main.py
═══════════════════════════════════════════════════════════════
  Documents / Images Finder Tool
  A software by Nauman Ali  ·  thisisnauman.ali@gmail.com
  v2.0
═══════════════════════════════════════════════════════════════

Entry point. Run this file to launch the application:
    python main.py

Project structure:
    main.py                   ← you are here
    config.py                 ← theme, constants, logging
    engines/
        __init__.py           ← public engine API
        core_engine.py        ← hashing, metadata, thumbnails
        face_engine.py        ← face recognition + encoding cache
        nsfw_engine.py        ← NudeNet explicit content detection
        kissing_engine.py     ← CLIP kissing/intimate detection
        keyword_engine.py     ← OCR + document keyword search
        evidence_manager.py   ← copy/move files with audit log
        report_engine.py      ← PDF report generation
    ui/
        __init__.py           ← public UI API
        app.py                ← main Tkinter application window
"""

import sys
import multiprocessing

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    from PIL import Image
    import numpy as np
except ImportError as e:
    print(f"\n[FATAL] Missing required library: {e}")
    print("Run:  pip install Pillow numpy")
    sys.exit(1)

# ── Project imports ───────────────────────────────────────────────────────────
from config import APP_NAME, APP_VERSION, APP_AUTHOR, APP_EMAIL, get_logger
from ui import ForensicApp

logger = get_logger("Main")


def print_banner():
    """Print startup banner to terminal."""
    print("\n" + "╔" + "═" * 50 + "╗")
    print(f"║  {APP_NAME:<48}║")
    print(f"║  A software by {APP_AUTHOR:<33}║")
    print(f"║  {APP_EMAIL:<48}║")
    print(f"║  {APP_VERSION:<48}║")
    print("╚" + "═" * 50 + "╝\n")

    # Show which optional libraries are loaded
    checks = [
        ("face_recognition", "face-recognition"),
        ("nudenet",          "nudenet"),
        ("transformers",     "transformers torch"),
        ("easyocr",          "easyocr"),
        ("pdfplumber",       "pdfplumber"),
        ("docx",             "python-docx"),
        ("pptx",             "python-pptx"),
        ("reportlab",        "reportlab"),
        ("piexif",           "piexif"),
    ]
    for module, install in checks:
        try:
            __import__(module)
            print(f"  {'✔':2}  {module}")
        except ImportError:
            print(f"  {'✘':2}  {module:<20}  →  pip install {install}")
    print()


def main():
    # Required for multiprocessing on Windows (face encoding pool)
    multiprocessing.freeze_support()

    print_banner()
    logger.info(f"{APP_NAME} started.")

    app = ForensicApp()
    app.mainloop()

    logger.info(f"{APP_NAME} closed.")


if __name__ == "__main__":
    main()
