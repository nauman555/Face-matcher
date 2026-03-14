"""
config.py — Shared configuration: constants, theme, fonts, logging.
All other modules import from here.
"""

import sys
import logging

# ── File type constants ────────────────────────────────────────────────────────
SUPPORTED_EXT  = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
CACHE_FILENAME = ".finder_encoding_cache.json"
MAX_DIM        = 800
THUMB_SIZE     = (120, 90)
PDF_THUMB_SIZE = (80, 60)

IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif",
                  ".webp", ".gif"}
DOC_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt",
                  ".csv", ".log", ".xml", ".html", ".htm", ".json"}

# ── UI Theme — Deep Navy + Cyan accent + White text hierarchy ─────────────────
C = {
    "bg":        "#0a0e17",
    "bg2":       "#0f1520",
    "bg3":       "#141d2b",
    "bg4":       "#1a2538",
    "bg5":       "#202e45",
    "accent":    "#00b4d8",
    "accent2":   "#0096c7",
    "accent3":   "#90e0ef",
    "success":   "#2ec27e",
    "warning":   "#e9c46a",
    "danger":    "#e76f51",
    "kiss_col":  "#c77dff",
    "text":      "#eaf0fb",
    "text2":     "#7f8fa6",
    "text3":     "#3d4f66",
    "border":    "#1e2d42",
    "border2":   "#283d5a",
    "header":    "#06090f",
    "divider":   "#182233",
}

# ── Fonts ──────────────────────────────────────────────────────────────────────
FONT_TITLE = ("Segoe UI",   10, "bold")
FONT_LABEL = ("Segoe UI",    9)
FONT_BOLD  = ("Segoe UI",    9, "bold")
FONT_SMALL = ("Segoe UI",    8)
FONT_TINY  = ("Segoe UI",    7)
FONT_MONO  = ("Courier New", 9)
FONT_CODE  = ("Courier New", 8)

# ── App metadata ───────────────────────────────────────────────────────────────
APP_NAME    = "Documents / Images Finder Tool"
APP_VERSION = "v2.0"
APP_AUTHOR  = "Nauman Ali"
APP_EMAIL   = "thisisnauman.ali@gmail.com"

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_FILE = "finder_tool.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

def get_logger(name: str = "FinderTool") -> logging.Logger:
    """Return a named logger. All modules call this instead of creating their own."""
    return logging.getLogger(name)
