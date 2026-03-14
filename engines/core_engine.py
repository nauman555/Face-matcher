"""
engines/core_engine.py
Core processing engine: file hashing, EXIF metadata extraction, thumbnails.
No external ML dependencies — works with just Pillow.
"""

import json
import hashlib
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from PIL import Image, ImageTk

from config import (
    SUPPORTED_EXT, THUMB_SIZE, PDF_THUMB_SIZE, get_logger
)

logger = get_logger("CoreEngine")


class ForensicEngine:
    """Handles hashing, metadata extraction, and thumbnail generation."""

    @staticmethod
    def compute_hashes(filepath: str) -> Dict[str, str]:
        """Compute MD5 and SHA256 hashes from raw file bytes."""
        md5    = hashlib.md5()
        sha256 = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    md5.update(chunk)
                    sha256.update(chunk)
            return {"md5": md5.hexdigest(), "sha256": sha256.hexdigest()}
        except Exception as e:
            logger.warning(f"Hash error for {filepath}: {e}")
            return {"md5": "No data found", "sha256": "No data found"}

    @staticmethod
    def extract_metadata(filepath: str) -> Dict[str, Any]:
        """Extract file metadata: size, dates, EXIF, GPS."""
        nd   = "No data found"
        p    = Path(filepath)
        meta = {
            "filename":      p.name,
            "folder":        str(p.parent),
            "filepath":      str(p.resolve()),
            "filesize":      nd,
            "device":        nd,
            "capture_date":  nd,
            "gps":           nd,
            "last_modified": nd,
            "last_accessed": nd,
            "exif_raw":      nd,
        }

        try:
            stat = p.stat()
            meta["filesize"]      = (
                f"{stat.st_size:,} bytes ({stat.st_size / 1024:.1f} KB)")
            meta["last_modified"] = datetime.datetime.fromtimestamp(
                stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            meta["last_accessed"] = datetime.datetime.fromtimestamp(
                stat.st_atime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

        # EXIF via Pillow — only works for image files
        try:
            img       = Image.open(filepath)
            exif_data = img._getexif() if hasattr(img, "_getexif") else None
            if exif_data:
                from PIL.ExifTags import TAGS
                decoded = {}
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    decoded[tag] = str(value)[:200]

                meta["exif_raw"]     = json.dumps(decoded, indent=2)[:2000]
                meta["device"]       = decoded.get("Make", nd)
                if "Model" in decoded and decoded.get("Make", nd) != nd:
                    meta["device"]   = (
                        f"{decoded.get('Make','')} "
                        f"{decoded.get('Model','')}".strip())
                meta["capture_date"] = decoded.get(
                    "DateTimeOriginal", decoded.get("DateTime", nd))

                gps_info = exif_data.get(34853)
                if gps_info:
                    try:
                        lat = ForensicEngine._convert_gps(
                            gps_info.get(2), gps_info.get(1))
                        lon = ForensicEngine._convert_gps(
                            gps_info.get(4), gps_info.get(3))
                        if lat and lon:
                            meta["gps"] = f"{lat:.6f}, {lon:.6f}"
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"EXIF error for {filepath}: {e}")

        return meta

    @staticmethod
    def _convert_gps(coord, ref) -> Optional[float]:
        if not coord or not ref:
            return None
        try:
            val = float(coord[0]) + float(coord[1]) / 60 + float(coord[2]) / 3600
            if ref in ("S", "W"):
                val = -val
            return val
        except Exception:
            return None

    @staticmethod
    def make_thumbnail(filepath: str,
                       size=THUMB_SIZE) -> Optional[ImageTk.PhotoImage]:
        """Generate a Tk-compatible thumbnail with cyan border."""
        try:
            img = Image.open(filepath).convert("RGB")
            img.thumbnail(size, Image.LANCZOS)
            bordered = Image.new("RGB",
                                 (img.width + 4, img.height + 4),
                                 (0, 174, 255))
            bordered.paste(img, (2, 2))
            return ImageTk.PhotoImage(bordered)
        except Exception:
            return None

    @staticmethod
    def make_pil_thumbnail(filepath: str,
                           size=PDF_THUMB_SIZE) -> Optional[Image.Image]:
        """Generate a plain PIL thumbnail for PDF embedding."""
        try:
            img = Image.open(filepath).convert("RGB")
            img.thumbnail(size, Image.LANCZOS)
            return img
        except Exception:
            return None

    @staticmethod
    def collect_images(folder: str) -> List[Path]:
        """Recursively collect all supported image paths in a folder."""
        return [
            p for p in Path(folder).rglob("*")
            if p.suffix.lower() in SUPPORTED_EXT
            and not p.name.startswith(".")
        ]
