import os
import hashlib
from typing import Dict, Iterator, List, Optional, Callable

from .utils import guess_kind, normalize_path


def _hash_file(path: str, algo: str = "md5", chunk: int = 1024 * 1024) -> Optional[str]:
    try:
        h = hashlib.new(algo)
        with open(path, "rb") as f:
            while True:
                b = f.read(chunk)
                if not b:
                    break
                h.update(b)
        return h.hexdigest()
    except Exception:
        return None


def scan_dir(path: str,
             compute_hash: bool = False,
             hash_algo: str = "md5",
             exclude_dirs: Optional[List[str]] = None,
             exclude_dir_names: Optional[List[str]] = None) -> List[Dict]:
    exclude_dirs = exclude_dirs or []
    records: List[Dict] = []

    exclude_dir_names = [n.lower() for n in (exclude_dir_names or [])]
    for root, dirs, files in os.walk(path):
        # Filter excluded directories in-place
        dirs[:] = [d for d in dirs
                  if os.path.join(root, d) not in exclude_dirs
                  and d.lower() not in exclude_dir_names]

        for fname in files:
            full = normalize_path(os.path.join(root, fname))
            try:
                st = os.stat(full)
            except FileNotFoundError:
                continue
            rec = {
                "path": full,
                "name": fname,
                "ext": os.path.splitext(fname)[1].lower(),
                "size": st.st_size,
                "mtime": st.st_mtime,
                "ctime": st.st_ctime,
                "kind": guess_kind(full),
            }
            if compute_hash:
                rec[f"hash_{hash_algo}"] = _hash_file(full, algo=hash_algo)
            records.append(rec)
    return records


def iter_dir(path: str,
             compute_hash: bool = False,
             hash_algo: str = "md5",
             exclude_dirs: Optional[List[str]] = None,
             exclude_dir_names: Optional[List[str]] = None) -> Iterator[Dict]:
    """Yield records one-by-one for streaming processing."""
    exclude_dirs = exclude_dirs or []
    exclude_dir_names = [n.lower() for n in (exclude_dir_names or [])]
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs
                   if os.path.join(root, d) not in exclude_dirs
                   and d.lower() not in exclude_dir_names]
        for fname in files:
            full = normalize_path(os.path.join(root, fname))
            try:
                st = os.stat(full)
            except FileNotFoundError:
                continue
            rec = {
                "path": full,
                "name": fname,
                "ext": os.path.splitext(fname)[1].lower(),
                "size": st.st_size,
                "mtime": st.st_mtime,
                "ctime": st.st_ctime,
                "kind": guess_kind(full),
            }
            if compute_hash:
                rec[f"hash_{hash_algo}"] = _hash_file(full, algo=hash_algo)
            yield rec
