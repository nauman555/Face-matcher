"""
engines/kissing_engine.py
Kissing / intimate content detection using OpenAI CLIP (zero-shot).
Install: pip install transformers torch torchvision

Speed optimisations:
  - Text prompts encoded ONCE at load time
  - Images processed in batches of 16
  - torch.inference_mode() for maximum speed
"""

from pathlib import Path
from typing import List, Dict, Any

from PIL import Image

from config import get_logger

logger = get_logger("KissingEngine")

# Optional imports
clip_ok = False
try:
    from transformers import CLIPProcessor, CLIPModel
    import torch
    clip_ok = True
except ImportError:
    pass


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
        self.available      = clip_ok
        self._loaded        = False
        self._text_features = None
        self._n_pos         = len(self.POSITIVE_PROMPTS)

    def load(self):
        """Load model and pre-encode all text prompts. Call once before scanning."""
        if self._loaded or not self.available:
            return
        try:
            logger.info("Loading CLIP model (first run ~600 MB download)…")
            self.processor = CLIPProcessor.from_pretrained(self.MODEL_ID)
            self.model     = CLIPModel.from_pretrained(self.MODEL_ID)
            self.model.eval()

            all_prompts = self.POSITIVE_PROMPTS + self.NEGATIVE_PROMPTS
            text_inputs = self.processor(
                text=all_prompts, return_tensors="pt", padding=True)
            with torch.inference_mode():
                feats = self.model.get_text_features(**text_inputs)
                self._text_features = feats / feats.norm(dim=-1, keepdim=True)

            self._loaded = True
            logger.info(
                f"CLIP ready — {len(all_prompts)} prompts × "
                f"{self._text_features.shape[-1]}d cached")
        except Exception as e:
            logger.error(f"CLIP load failed: {e}")
            self.available = False

    def analyze_batch(self, filepaths: List[str],
                      threshold: float = 0.25) -> List[Dict[str, Any]]:
        """
        Analyze a batch of images in one forward pass.
        Returns results in the same order as filepaths.
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
                img_feat = self.model.get_image_features(**img_inputs)
                img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
                probs    = (
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
