"""
engines/evidence_manager.py
Evidence management — copy / move matched files with full audit logging.
"""

import shutil
import datetime
from pathlib import Path
from typing import List

from config import APP_NAME, APP_AUTHOR, get_logger

logger = get_logger("EvidenceManager")


class EvidenceManager:
    """Copy or move matched files to a destination with an audit log."""

    @staticmethod
    def _write_log(dest_folder: str, action: str, files: List[str]):
        ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = Path(dest_folder) / f"finder_evidence_{action}_{ts}.log"
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"{APP_NAME} — Evidence {action.upper()} Log\n")
                f.write(f"Software by {APP_AUTHOR}\n")
                f.write(
                    f"Timestamp : "
                    f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Action    : {action.upper()}\n")
                f.write(f"Files     : {len(files)}\n")
                f.write("=" * 70 + "\n\n")
                for fp in files:
                    f.write(f"{fp}\n")
            logger.info(f"Evidence log written: {log_path}")
        except Exception as e:
            logger.error(f"Log write failed: {e}")

    @staticmethod
    def copy_files(file_paths: List[str], dest_folder: str) -> int:
        """Copy files to dest_folder. Returns count of successfully copied files."""
        Path(dest_folder).mkdir(parents=True, exist_ok=True)
        copied = 0
        for fp in file_paths:
            try:
                src  = Path(fp)
                dest = Path(dest_folder) / src.name
                if dest.exists():
                    dest = Path(dest_folder) / f"{src.stem}_{copied}{src.suffix}"
                shutil.copy2(fp, dest)
                copied += 1
            except Exception as e:
                logger.warning(f"Copy failed {fp}: {e}")
        EvidenceManager._write_log(dest_folder, "copy", file_paths)
        return copied

    @staticmethod
    def move_files(file_paths: List[str], dest_folder: str) -> int:
        """Move files to dest_folder. Returns count of successfully moved files."""
        Path(dest_folder).mkdir(parents=True, exist_ok=True)
        moved = 0
        for fp in file_paths:
            try:
                src  = Path(fp)
                dest = Path(dest_folder) / src.name
                if dest.exists():
                    dest = Path(dest_folder) / f"{src.stem}_{moved}{src.suffix}"
                shutil.move(fp, dest)
                moved += 1
            except Exception as e:
                logger.warning(f"Move failed {fp}: {e}")
        EvidenceManager._write_log(dest_folder, "move", file_paths)
        return moved
