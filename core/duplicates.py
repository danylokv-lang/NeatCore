from __future__ import annotations

import os
from typing import Dict, List, Tuple, Optional, DefaultDict
from collections import defaultdict

from PIL import Image
from imagehash import phash

from .scanner import _hash_file
from .utils import is_image_ext


def group_by_exact_hash(records: List[Dict], algo: str = "md5") -> List[List[Dict]]:
    # Pre-group by file size to avoid hashing unique sizes
    size_groups: DefaultDict[int, List[Dict]] = defaultdict(list)
    for r in records:
        size_groups[r.get("size", -1)].append(r)
    buckets: DefaultDict[str, List[Dict]] = defaultdict(list)
    key = f"hash_{algo}"
    for size, group in size_groups.items():
        if len(group) < 2 or size <= 0:
            continue
        for r in group:
            hv = r.get(key)
            if hv is None:
                hv = _hash_file(r["path"], algo=algo)
                r[key] = hv
            if hv:
                buckets[hv].append(r)
    return [items for items in buckets.values() if len(items) > 1]


def compute_phash(path: str) -> Optional[int]:
    try:
        img = Image.open(path)
        img.load()
        return int(str(phash(img)), 16)
    except Exception:
        return None


def hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def group_by_perceptual_hash(records: List[Dict], threshold: int = 5) -> List[List[Dict]]:
    imgs = [r for r in records if r.get("kind") == "image" or is_image_ext(r.get("ext", ""))]
    # Compute phash and bucket by prefix to reduce comparisons
    buckets: DefaultDict[int, List[Tuple[Dict, int]]] = defaultdict(list)
    PREFIX_BITS = 12  # 12-bit prefix bucket (~4096 buckets)
    for r in imgs:
        hv = r.get("phash")
        if hv is None:
            hv = compute_phash(r["path"]) or 0
            r["phash"] = hv if hv != 0 else None
        if hv:
            prefix = hv >> (64 - PREFIX_BITS)
            buckets[prefix].append((r, hv))

    groups: List[List[Dict]] = []
    for _, items in buckets.items():
        items.sort(key=lambda t: t[1])
        n = len(items)
        visited = set()
        for i in range(n):
            if i in visited:
                continue
            ri, hi = items[i]
            group = [ri]
            visited.add(i)
            # Compare with a limited window around i to keep near neighbors
            for j in range(i + 1, min(i + 50, n)):
                if j in visited:
                    continue
                rj, hj = items[j]
                if hamming_distance(hi, hj) <= threshold:
                    group.append(rj)
                    visited.add(j)
            if len(group) > 1:
                groups.append(group)
    return groups
