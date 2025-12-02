import os
import math
import mimetypes
from datetime import datetime, timezone
from typing import Optional

from PIL import Image
import numpy as np


IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp", ".heic"
}
DOC_EXTS = {
    ".txt", ".md", ".rtf", ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"
}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz"}
TEMP_PATTERNS = {"~$", ".tmp", ".temp", ".partial"}


def human_size(num: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num)
    for unit in units:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def file_age_days(mtime: float) -> float:
    dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - dt).total_seconds() / 86400.0


def is_image_ext(ext: str) -> bool:
    return ext.lower() in IMAGE_EXTS


def is_doc_ext(ext: str) -> bool:
    return ext.lower() in DOC_EXTS


def is_video_ext(ext: str) -> bool:
    return ext.lower() in VIDEO_EXTS


def is_audio_ext(ext: str) -> bool:
    return ext.lower() in AUDIO_EXTS


def is_archive_ext(ext: str) -> bool:
    return ext.lower() in ARCHIVE_EXTS


def looks_temporary(name: str) -> bool:
    lname = name.lower()
    return any(pat in lname for pat in TEMP_PATTERNS)


def in_downloads_path(path: str) -> bool:
    lname = path.lower()
    return "\\downloads\\" in lname or "/downloads/" in lname


def guess_kind(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if is_image_ext(ext):
        return "image"
    if is_doc_ext(ext):
        return "document"
    if is_video_ext(ext):
        return "video"
    if is_audio_ext(ext):
        return "audio"
    if is_archive_ext(ext):
        return "archive"
    # fallback on mimetypes
    mime, _ = mimetypes.guess_type(path)
    if mime:
        if mime.startswith("image/"):
            return "image"
        if mime.startswith("text/"):
            return "document"
    return "other"


def normalize_path(p: str) -> str:
    """Normalize to an absolute Windows path with backslashes consistently."""
    ap = os.path.abspath(p)
    return os.path.normpath(ap)


def windows_long_path(p: str) -> str:
    r"""Prefix with \\?\ for very long Windows paths to avoid API errors."""
    np = normalize_path(p)
    if os.name == "nt" and not np.startswith("\\\\?\\") and len(np) >= 248:
        return "\\\\?\\" + np
    return np


def safe_open_image(path: str) -> Optional[Image.Image]:
    try:
        img = Image.open(path)
        img.load()
        return img
    except Exception:
        return None


def image_brightness(img: Image.Image) -> float:
    arr = np.asarray(img.convert("L"), dtype=np.float32)
    return float(np.mean(arr))


def image_resolution(img: Image.Image) -> tuple[int, int]:
    return img.size  # (w, h)


def estimate_sharpness(img: Image.Image) -> float:
    # Gradient magnitude energy as sharpness proxy with guards for tiny images
    try:
        # Downscale very large images for speed
        w, h = img.size
        if max(w, h) > 1024:
            ratio = 1024.0 / float(max(w, h))
            nw, nh = max(1, int(w * ratio)), max(1, int(h * ratio))
            img = img.resize((nw, nh), Image.BILINEAR)
        gray = np.asarray(img.convert("L"), dtype=np.float32)
        if gray.ndim != 2 or min(gray.shape) < 2:
            return 0.0
        gy, gx = np.gradient(gray)
        mag = np.sqrt(gx * gx + gy * gy)
        return float(np.mean(mag))
    except Exception:
        return 0.0
