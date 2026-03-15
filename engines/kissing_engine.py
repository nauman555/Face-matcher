"""
engines/kissing_engine.py
Kissing / intimate content detection using OpenAI CLIP (zero-shot).
Install: pip install transformers torch torchvision

Speed optimisations:
  - Text prompts encoded ONCE at load time — not per image
  - Images processed in batches of 16 — ~16x faster than one-by-one
  - torch.inference_mode() for maximum speed

Version compatibility:
  - Works with transformers old (plain tensor) and new (ModelOutput wrapper)
  - Handles download-in-progress gracefully — never permanently disables
    on a transient network error, only on a real code/version error
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from PIL import Image

from config import get_logger

logger = get_logger("KissingEngine")

# Optional imports — checked at runtime
clip_ok = False
try:
    from transformers import CLIPProcessor, CLIPModel
    import torch
    clip_ok = True
except ImportError:
    pass


def _extract_tensor(output):
    """
    Safely extract a plain tensor from either:
      - A raw tensor  (old transformers)
      - BaseModelOutputWithPooling  (new transformers)
      - Any other ModelOutput wrapper
    """
    import torch
    if isinstance(output, torch.Tensor):
        return output
    # Named tuple / dataclass style (new transformers)
    if hasattr(output, 'pooler_output') and output.pooler_output is not None:
        return output.pooler_output
    if hasattr(output, 'last_hidden_state'):
        # CLS token = first token
        return output.last_hidden_state[:, 0, :]
    # Fallback: first element of whatever was returned
    if hasattr(output, '__iter__'):
        first = next(iter(output))
        if isinstance(first, torch.Tensor):
            return first
    raise TypeError(f"Cannot extract tensor from {type(output)}")


class KissingDetector:
    """Zero-shot kissing / intimate content detection via CLIP."""

    MODEL_ID   = "openai/clip-vit-base-patch32"
    BATCH_SIZE = 16

    POSITIVE_PROMPTS = [
        "two people kissing",
        "couple kissing on lips",
        "people making out",
        "romantic kiss",
        "intimate kiss between two people",
    ]
    NEGATIVE_PROMPTS = [
        "people standing",
        "landscape or nature photo",
        "text document",
        "crowd of people",
    ]

    def __init__(self):
        self.model          = None
        self.processor      = None
        self.available      = clip_ok   # True if transformers+torch installed
        self._loaded        = False     # True only after model fully ready
        self._text_features = None
        self._n_pos         = len(self.POSITIVE_PROMPTS)
        self._load_error    = None      # last error message, for display

    # ── Helper: extract + normalise a feature tensor ──────────────
    @staticmethod
    def _norm(output) -> "torch.Tensor":
        import torch
        t = _extract_tensor(output)
        return t / t.norm(dim=-1, keepdim=True)

    # ── Model load ────────────────────────────────────────────────
    def load(self, log_fn: Optional[Callable] = None) -> bool:
        """
        Download (first run) and load CLIP model.
        Safe to call multiple times — skips if already loaded.
        Does NOT permanently disable on network errors so retries work.

        Args:
            log_fn: optional callback(msg, tag) to write to the UI log

        Returns:
            True if loaded successfully, False otherwise.
        """
        if self._loaded:
            return True
        if not self.available:
            return False

        def _log(msg, tag="info"):
            logger.info(msg)
            if log_fn:
                log_fn(f"  {msg}", tag)

        try:
            _log("Loading CLIP processor…", "info")
            self.processor = CLIPProcessor.from_pretrained(self.MODEL_ID)

            _log("Downloading / loading CLIP model (~600 MB on first run)…", "info")
            _log("  This may take several minutes. Progress is shown in the terminal.", "info")
            self.model = CLIPModel.from_pretrained(self.MODEL_ID)
            self.model.eval()
            _log("Model loaded — encoding text prompts…", "info")

            # Pre-encode ALL text prompts once — reused for every image batch
            all_prompts = self.POSITIVE_PROMPTS + self.NEGATIVE_PROMPTS
            text_inputs = self.processor(
                text=all_prompts, return_tensors="pt", padding=True)

            with torch.inference_mode():
                raw_feats           = self.model.get_text_features(**text_inputs)
                self._text_features = self._norm(raw_feats)

            self._loaded     = True
            self._load_error = None
            _log(
                f"✔ CLIP ready — {len(all_prompts)} prompts × "
                f"{self._text_features.shape[-1]}d (text features cached)",
                "match")
            return True

        except Exception as e:
            self._load_error = str(e)
            self._loaded     = False
            # Only permanently disable if the libraries themselves are broken
            # (not for transient download / network errors)
            is_code_error = any(x in str(e).lower() for x in [
                'attribute', 'has no', 'module', 'import',
                'unexpected keyword', 'got an unexpected'
            ])
            if is_code_error:
                # Code/version error — disable to avoid repeated crashes
                self.available = False
                _log(f"✘ CLIP code error — kissing detection disabled: {e}", "error")
                _log("  Run:  pip install --upgrade transformers torch torchvision", "error")
            else:
                # Network / download error — keep available so user can retry
                _log(f"✘ CLIP load failed (will retry next scan): {e}", "error")
                _log("  Check your internet connection and try again.", "error")
            return False

    # ── Batch analyse ─────────────────────────────────────────────
    def analyze_batch(self, filepaths: List[str],
                      threshold: float = 0.25) -> List[Dict[str, Any]]:
        """
        Analyse a batch of images in one CLIP forward pass.
        Returns a list of result dicts in the same order as filepaths.
        """
        null = {"is_kissing": False, "confidence": 0.0, "top_prompt": ""}
        if not self.available or not self._loaded or not filepaths:
            return [null] * len(filepaths)

        try:
            pil_images, valid_idx = [], []
            for i, fp in enumerate(filepaths):
                try:
                    img = Image.open(fp).convert("RGB")
                    img.thumbnail((224, 224), Image.BILINEAR)
                    pil_images.append(img)
                    valid_idx.append(i)
                except Exception:
                    pass

            if not pil_images:
                return [null] * len(filepaths)

            img_inputs = self.processor(
                images=pil_images, return_tensors="pt", padding=True)

            with torch.inference_mode():
                raw_img_feat = self.model.get_image_features(**img_inputs)
                img_feat     = self._norm(raw_img_feat)
                # Cosine similarity scores [n_images × n_prompts]
                probs = (
                    (img_feat @ self._text_features.T) * 100
                ).softmax(dim=-1)

            results = [null] * len(filepaths)
            for j, orig_i in enumerate(valid_idx):
                pos_probs  = probs[j, :self._n_pos].tolist()
                total_conf = sum(pos_probs)
                best_idx   = pos_probs.index(max(pos_probs))
                is_kissing = total_conf >= threshold

                if is_kissing:
                    logger.info(
                        f"KISSING: {Path(filepaths[orig_i]).name} "
                        f"conf={total_conf:.3f}")

                results[orig_i] = {
                    "is_kissing":  is_kissing,
                    "confidence":  round(total_conf, 3),
                    "top_prompt":  (self.POSITIVE_PROMPTS[best_idx]
                                    if is_kissing else ""),
                }
            return results

        except Exception as e:
            logger.warning(f"CLIP batch error: {e}")
            return [null] * len(filepaths)

    def analyze(self, filepath: str,
                threshold: float = 0.25) -> Dict[str, Any]:
        """Single-image convenience wrapper around analyze_batch."""
        return self.analyze_batch([filepath], threshold)[0]
