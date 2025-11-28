from __future__ import annotations

import os
from typing import Dict, List

from .utils import file_age_days, in_downloads_path, looks_temporary


def recommend_for_record(rec: Dict, analysis: Dict, dup_count: int = 0) -> Dict:
    reasons: List[str] = []
    primary = "ignore"
    score = 0

    age_days = file_age_days(rec["mtime"]) if rec.get("mtime") else 0
    kind = rec.get("kind", "other")
    label = analysis.get("label", kind)

    # Temporary files
    if looks_temporary(rec.get("name", "")):
        reasons.append("Temporary-looking filename")
        primary = "delete"
        score += 3

    # Screenshots older than 30 days
    if label == "screenshot" and age_days > 30:
        reasons.append("Screenshot older than 30 days")
        primary = "delete"
        score += 2

    # Downloads older than 90 days
    if in_downloads_path(rec.get("path", "")) and age_days > 90:
        reasons.append("Old file in Downloads (> 90 days)")
        primary = "delete"
        score += 2

    # Duplicates
    if dup_count > 0:
        reasons.append("Duplicate detected")
        primary = "delete-duplicates"
        score += 3

    # Low-quality images
    q = analysis.get("quality") or {}
    if label in ("photo", "wallpaper"):
        if q.get("is_small") or q.get("is_dark") or q.get("is_low_sharpness"):
            reasons.append("Low-quality image")
            primary = "delete"
            score += 2

    # Large archives: suggest compress OR move
    if kind == "archive" and rec.get("size", 0) > 200 * 1024 * 1024:
        reasons.append("Large archive; consider moving")
        primary = "move"
        score += 1

    # Old documents with small size -> compress or leave
    if kind == "document" and age_days > 180 and rec.get("size", 0) > 0:
        reasons.append("Old document")
        primary = primary if primary != "ignore" else "compress"
        score += 1

    if not reasons:
        reasons.append("No issues detected")
        primary = "ignore"

    return {"primary_action": primary, "reasons": reasons, "score": score}
