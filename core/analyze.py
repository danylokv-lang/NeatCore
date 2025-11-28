from __future__ import annotations

import os
from typing import Dict, Optional, List

from .utils import (
    safe_open_image,
    image_brightness,
    image_resolution,
    estimate_sharpness,
)


class Analyzer:
    def __init__(self, enable_ai: bool = False) -> None:
        # Defer transformers import until actually needed to avoid heavy deps at startup
        self.enable_ai = enable_ai
        self._clip_model = None
        self._clip_proc = None
        self.labels = ["screenshot", "document", "photo", "meme", "wallpaper"]

    def _ensure_clip(self) -> bool:
        if not self.enable_ai:
            return False
        if self._clip_model is not None:
            return True
        try:
            from transformers import CLIPProcessor, CLIPModel  # type: ignore
            self._clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            self._clip_proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            return True
        except Exception:
            # Fallback if model load fails or transformers/torch unavailable
            self.enable_ai = False
            return False

    def classify_image(self, path: str) -> Dict:
        img = safe_open_image(path)
        if img is None:
            return {"label": "unknown", "confidence": 0.0, "quality": {}}

        # Heuristic quality features
        w, h = image_resolution(img)
        bright = image_brightness(img)
        sharp = estimate_sharpness(img)

        quality = {
            "width": w,
            "height": h,
            "brightness": float(bright),
            "sharpness": float(sharp),
            "is_small": (w < 800 or h < 600),
            "is_dark": bright < 50.0,
            "is_low_sharpness": sharp < 5.0,
        }

        # Simple screenshot heuristic
        lname = os.path.basename(path).lower()
        if (
            "screenshot" in lname or "скрін" in lname or "скрин" in lname or "скріншот" in lname
        ) and (w >= 800 and h >= 600):
            return {"label": "screenshot", "confidence": 0.7, "quality": quality}

        # Optional CLIP classification
        if self._ensure_clip():
            try:
                from PIL import Image  # local import
                inputs = self._clip_proc(text=self.labels, images=img, return_tensors="pt", padding=True)
                outputs = self._clip_model(**inputs)
                probs = outputs.logits_per_image.softmax(dim=1)[0]
                idx = int(probs.argmax())
                conf = float(probs[idx])
                return {"label": self.labels[idx], "confidence": conf, "quality": quality}
            except Exception:
                pass

        # Fallback heuristics
        if w >= 1600 and h >= 900 and not quality["is_dark"] and not quality["is_low_sharpness"]:
            return {"label": "wallpaper", "confidence": 0.55, "quality": quality}
        if not quality["is_small"] and not quality["is_dark"]:
            return {"label": "photo", "confidence": 0.5, "quality": quality}
        if quality["is_small"] or quality["is_dark"] or quality["is_low_sharpness"]:
            return {"label": "photo", "confidence": 0.4, "quality": quality}
        return {"label": "unknown", "confidence": 0.0, "quality": quality}

    def analyze_record(self, rec: Dict) -> Dict:
        kind = rec.get("kind", "other")
        out = {"kind": kind, "label": kind, "confidence": 0.0, "quality": {}}

        if kind == "image":
            res = self.classify_image(rec["path"])
            out.update(res)
        elif kind == "document":
            out.update({"label": "document", "confidence": 0.5, "quality": {}})
        else:
            out.update({"label": kind, "confidence": 0.3, "quality": {}})
        return out
