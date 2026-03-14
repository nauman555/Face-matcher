"""
engines/nsfw_engine.py
NSFW / explicit content detection using NudeNet.
Install: pip install nudenet
"""

from pathlib import Path
from typing import Dict, Any

from config import get_logger

logger = get_logger("NSFWEngine")

# Optional import — checked at runtime
NudeDetector = None
try:
    from nudenet import NudeDetector as _ND
    NudeDetector = _ND
except ImportError:
    pass


class NSFWEngine:
    """AI-based explicit content detection using NudeNet."""

    LABELS_V2 = {
        "EXPOSED_ANUS", "EXPOSED_BUTTOCKS",
        "EXPOSED_BREAST_F", "EXPOSED_BREAST_M",
        "EXPOSED_GENITALIA_F", "EXPOSED_GENITALIA_M",
        "EXPOSED_BELLY", "EXPOSED_ARMPITS",
    }
    LABELS_V3 = {
        "FEMALE_BREAST_EXPOSED", "FEMALE_GENITALIA_EXPOSED",
        "MALE_BREAST_EXPOSED",   "MALE_GENITALIA_EXPOSED",
        "BUTTOCKS_EXPOSED",      "ANUS_EXPOSED",
        "FEMALE_BREAST_COVERED", "FEMALE_GENITALIA_COVERED",
        "MALE_GENITALIA_COVERED","BUTTOCKS_COVERED",
    }
    EXPLICIT_LABELS = LABELS_V2 | LABELS_V3

    SKIP_LABELS = {
        "FACE_FEMALE", "FACE_MALE", "ARMPITS_COVERED",
        "BELLY_COVERED", "FEET_COVERED", "FEET_EXPOSED",
    }

    def __init__(self):
        self.detector  = None
        self.available = NudeDetector is not None
        if self.available:
            try:
                self.detector = NudeDetector()
                logger.info("NudeNet loaded successfully.")
            except Exception as e:
                logger.error(f"NudeNet load failed: {e}")
                self.available = False

    def analyze(self, filepath: str,
                threshold: float = 0.3) -> Dict[str, Any]:
        """
        Analyze one image for explicit content.

        Returns:
            is_explicit : bool
            confidence  : float
            detections  : list of detection dicts
        """
        null = {"is_explicit": False, "confidence": 0.0, "detections": []}
        if not self.available or self.detector is None:
            return null
        try:
            results = self.detector.detect(filepath)

            if results:
                logger.debug(
                    f"NudeNet [{Path(filepath).name}]: "
                    f"{[(r.get('class'), round(r.get('score', 0), 3)) for r in results]}")

            explicit = [
                r for r in results
                if r.get("class") in self.EXPLICIT_LABELS
                and r.get("score", 0) >= threshold
            ]

            # Fallback — catch unlisted labels above threshold
            if not explicit:
                explicit = [
                    r for r in results
                    if r.get("score", 0) >= threshold
                    and "COVERED" not in r.get("class", "")
                    and r.get("class", "") not in self.SKIP_LABELS
                ]

            confidence  = max(
                (r.get("score", 0) for r in explicit), default=0.0)
            is_explicit = len(explicit) > 0

            if is_explicit:
                logger.info(
                    f"NSFW DETECTED: {Path(filepath).name} "
                    f"conf={confidence:.2f} "
                    f"labels={[d.get('class') for d in explicit]}")

            return {
                "is_explicit": is_explicit,
                "confidence":  round(confidence, 3),
                "detections":  explicit,
            }
        except Exception as e:
            logger.warning(f"NSFW error {filepath}: {e}")
            return null
