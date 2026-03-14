"""
engines/__init__.py
Public API for all engine modules.
Import from here instead of individual files:

    from engines import ForensicEngine, FaceEngine, NSFWEngine
"""

from engines.core_engine     import ForensicEngine
from engines.face_engine     import FaceEngine, _encode_worker
from engines.nsfw_engine     import NSFWEngine
from engines.kissing_engine  import KissingDetector
from engines.keyword_engine  import KeywordSearchEngine
from engines.evidence_manager import EvidenceManager
from engines.report_engine   import ReportEngine

__all__ = [
    "ForensicEngine",
    "FaceEngine",
    "_encode_worker",
    "NSFWEngine",
    "KissingDetector",
    "KeywordSearchEngine",
    "EvidenceManager",
    "ReportEngine",
]
