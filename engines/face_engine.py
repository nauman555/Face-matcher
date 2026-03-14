"""
engines/face_engine.py
Face recognition matching engine with disk-based encoding cache.
Install: pip install face-recognition dlib
"""

import json
import multiprocessing
from pathlib import Path
from typing import Optional, List, Dict

import numpy as np
from PIL import Image

from config import MAX_DIM, CACHE_FILENAME, get_logger

logger = get_logger("FaceEngine")

# Optional import
face_recognition = None
try:
    import face_recognition as _fr
    face_recognition = _fr
except ImportError:
    pass


def _encode_worker(filepath_str: str) -> tuple:
    """
    Encode faces in one image. Runs inside a subprocess via multiprocessing.
    Must be a module-level function (not a method) for pickling to work.
    """
    try:
        import face_recognition as fr
        from PIL import Image
        import numpy as np
        from config import MAX_DIM

        pil  = Image.open(filepath_str).convert("RGB")
        w, h = pil.size
        if max(w, h) > MAX_DIM:
            scale = MAX_DIM / max(w, h)
            pil   = pil.resize(
                (int(w * scale), int(h * scale)), Image.LANCZOS)
        img  = np.ascontiguousarray(np.array(pil, dtype=np.uint8))
        locs = fr.face_locations(img, model="hog")
        encs = fr.face_encodings(img, locs) if locs else []
        return (filepath_str, [e.tolist() for e in encs])
    except Exception:
        return (filepath_str, [])


class FaceEngine:
    """Face recognition matching with disk-based encoding cache."""

    def __init__(self):
        self.available = face_recognition is not None

    # ── Image loading ──────────────────────────────────────────────
    def load_image(self, filepath: str) -> Optional[np.ndarray]:
        try:
            pil  = Image.open(filepath).convert("RGB")
            w, h = pil.size
            if max(w, h) > MAX_DIM:
                scale = MAX_DIM / max(w, h)
                pil   = pil.resize(
                    (int(w * scale), int(h * scale)), Image.LANCZOS)
            return np.ascontiguousarray(np.array(pil, dtype=np.uint8))
        except Exception:
            return None

    # ── Encode the sample (subject) image ─────────────────────────
    def encode_sample(self, filepath: str) -> Optional[np.ndarray]:
        """Encode the reference person's face. Returns encoding or None."""
        if not self.available:
            return None
        img = self.load_image(filepath)
        if img is None:
            return None
        locs = face_recognition.face_locations(img, model="hog")
        if not locs:
            return None
        if len(locs) > 1:
            # Pick the largest face
            locs = [max(locs,
                        key=lambda l: (l[2] - l[0]) * abs(l[1] - l[3]))]
        encs = face_recognition.face_encodings(img, locs)
        return encs[0] if encs else None

    # ── Encode one image (all faces) ──────────────────────────────
    def encode_image(self, filepath: str) -> List[List[float]]:
        """Return serialisable list of face encodings from one image."""
        if not self.available:
            return []
        img = self.load_image(filepath)
        if img is None:
            return []
        locs = face_recognition.face_locations(img, model="hog")
        if not locs:
            return []
        return [e.tolist() for e in face_recognition.face_encodings(img, locs)]

    # ── Match encodings against sample ────────────────────────────
    def matches_sample(self, encodings: List[List[float]],
                       sample_enc: np.ndarray,
                       tolerance: float) -> bool:
        """Return True if any encoding in the list matches the sample."""
        if not encodings or sample_enc is None:
            return False
        enc_arrays = [np.array(e) for e in encodings]
        return any(
            face_recognition.compare_faces(
                enc_arrays, sample_enc, tolerance=tolerance))

    # ── Cache helpers ──────────────────────────────────────────────
    @staticmethod
    def load_cache(folder: str) -> Dict:
        cp = Path(folder) / CACHE_FILENAME
        if cp.exists():
            try:
                with open(cp, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    @staticmethod
    def save_cache(folder: str, cache: Dict):
        cp = Path(folder) / CACHE_FILENAME
        try:
            with open(cp, "w") as f:
                json.dump(cache, f)
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")

    # ── Multi-process batch encoding ──────────────────────────────
    def encode_batch(self, paths: List[str],
                     n_workers: int = 4,
                     progress_cb=None) -> Dict[str, List]:
        """
        Encode many images using a multiprocessing pool.
        Returns {filepath: [encodings]} dict.
        """
        result = {}
        try:
            with multiprocessing.Pool(processes=n_workers) as pool:
                for i, (path_str, encs) in enumerate(
                    pool.imap_unordered(_encode_worker, paths, chunksize=50)
                ):
                    result[path_str] = encs or []
                    if progress_cb:
                        progress_cb(i + 1, len(paths))
        except Exception as e:
            logger.error(f"Multiprocessing error: {e} — falling back to single thread")
            for i, p in enumerate(paths):
                _, encs = _encode_worker(p)
                result[p] = encs or []
                if progress_cb:
                    progress_cb(i + 1, len(paths))
        return result
