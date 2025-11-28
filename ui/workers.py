from __future__ import annotations

from typing import List, Dict, Optional

from PySide6.QtCore import QThread, Signal

from core.scanner import scan_dir, iter_dir
from core.analyze import Analyzer
from core.duplicates import group_by_exact_hash, group_by_perceptual_hash
from core.utils import human_size
from core.recommend import recommend_for_record


class ScanWorker(QThread):
    progress = Signal(int)  # percentage (0-100; 0 for indeterminate)
    chunk = Signal(dict)    # emit each record as found
    done = Signal(list)     # final records list
    error = Signal(str)

    def __init__(self, paths: list[str], compute_hash: bool, fast_mode: bool = True):
        super().__init__()
        self.paths = paths
        self.compute_hash = compute_hash
        self.fast_mode = fast_mode
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            out: list[dict] = []
            # Indeterminate progress start
            self.progress.emit(0)
            # Fast-mode directory name exclusions
            exclude_names = [
                ".git", "node_modules", ".venv", "__pycache__", "dist", "build",
                "AppData", "Windows", "Program Files", "Program Files (x86)",
            ] if self.fast_mode else []

            for base in self.paths:
                if self._cancel:
                    break
                for rec in iter_dir(base, compute_hash=self.compute_hash, exclude_dir_names=exclude_names):
                    if self._cancel:
                        break
                    out.append(rec)
                    self.chunk.emit(rec)
            # Complete
            self.progress.emit(100)
            self.done.emit(out)
        except Exception as e:
            self.error.emit(str(e))


class AnalyzeWorker(QThread):
    progress = Signal(int)
    analyzed = Signal(dict)  # path -> {analysis, recommendation, dup_count}
    analyzed_batch = Signal(list)
    done = Signal()
    error = Signal(str)

    def __init__(self, records: List[Dict], enable_ai: bool, use_perceptual: bool, fast_mode: bool = True):
        super().__init__()
        self.records = records
        self.enable_ai = enable_ai
        self.use_perceptual = use_perceptual
        self.fast_mode = fast_mode
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            analyzer = Analyzer(enable_ai=self.enable_ai)

            # Duplicates: exact
            exact_groups = group_by_exact_hash(self.records, algo="md5")
            dup_map: Dict[str, int] = {}
            for grp in exact_groups:
                for r in grp:
                    dup_map[r["path"]] = len(grp) - 1

            # Perceptual duplicates (optional, image-only); limit for speed if fast_mode
            if self.use_perceptual:
                subset = self.records
                if self.fast_mode and len(self.records) > 3000:
                    subset = [r for i, r in enumerate(self.records) if r.get("kind") == "image" and (i % 2 == 0)][:3000]
                p_groups = group_by_perceptual_hash(subset, threshold=4 if self.fast_mode else 5)
                for grp in p_groups:
                    for r in grp:
                        dup_map[r["path"]] = max(dup_map.get(r["path"], 0), len(grp) - 1)

            total = len(self.records)
            batch: List[Dict] = []
            for idx, rec in enumerate(self.records):
                if self._cancel:
                    break
                analysis = analyzer.analyze_record(rec)
                dup_count = dup_map.get(rec["path"], 0)
                reco = recommend_for_record(rec, analysis, dup_count=dup_count)
                payload = {
                    "path": rec["path"],
                    "analysis": analysis,
                    "recommendation": reco,
                    "dup_count": dup_count,
                }
                batch.append(payload)
                if len(batch) >= 50:
                    self.analyzed_batch.emit(batch)
                    batch = []
                if total:
                    self.progress.emit(int((idx + 1) * 100 / total))
            if batch:
                self.analyzed_batch.emit(batch)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))
