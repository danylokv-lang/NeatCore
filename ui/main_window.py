from __future__ import annotations

import os
import zipfile
from typing import List, Dict

from PySide6.QtCore import Qt, QTimer, QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QAction, QColor, QBrush, QLinearGradient, QGradient
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QMessageBox, QProgressBar, QComboBox, QApplication, QFrame
)

from qt_material import apply_stylesheet
# Charts removed; keep guard variables to avoid NameError in legacy calls
_HAS_CHARTS = False
from PySide6.QtWidgets import QGraphicsOpacityEffect
from send2trash import send2trash

from core.utils import human_size, normalize_path, windows_long_path
from .workers import ScanWorker, AnalyzeWorker
from .indicators import BusyIndicator


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NeatCore")
        self.resize(1200, 720)

        self._records: List[Dict] = []
        self._analyses: Dict[str, Dict] = {}

        # Theming (apply to the QApplication instance)
        app = QApplication.instance()
        if app is not None:
            # Try green-blue themes
            for theme in ('dark_cyan.xml', 'dark_teal.xml', 'dark_blue.xml'):
                try:
                    apply_stylesheet(app, theme=theme)
                    break
                except Exception:
                    continue

        # Top bar
        top = QWidget()
        top_l = QHBoxLayout(top)
        # App logo on the left
        self.logo_lbl = QLabel()
        try:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            png = os.path.join(base, "assets", "blue_icon.png")
            if os.path.exists(png):
                from PySide6.QtGui import QPixmap
                self.logo_lbl.setPixmap(QPixmap(png).scaled(20,20, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception:
            pass
        self.btn_folder = QPushButton("Add Folder")
        self.lbl_folder = QLabel("No folders selected")
        self.btn_clear = QPushButton("Clear")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Images", "Documents", "Screenshots", "Low Quality", "Old Downloads", "Recommended Delete"])
        self.chk_duplicates = QCheckBox("Find Duplicates")
        self.chk_perceptual = QCheckBox("Similar Images (pHash)")
        self.chk_ai = QCheckBox("Enable AI (CLIP)")
        self.btn_scan = QPushButton("Scan")
        self.btn_stop = QPushButton("Stop")
        self.chk_fast = QCheckBox("Fast Mode")
        self.chk_fast.setChecked(True)
        self.btn_quick = QPushButton("Quick Suggest")
        self.busy_indicator = BusyIndicator()
        self.busy_indicator.setVisible(False)
        self.progress = QProgressBar()
        self.progress.setMaximum(100)
        self.progress.setValue(0)

        top_l.addWidget(self.logo_lbl)
        top_l.addWidget(self.btn_folder)
        top_l.addWidget(self.lbl_folder, 1)
        top_l.addWidget(self.btn_clear)
        top_l.addWidget(QLabel("Filter:"))
        top_l.addWidget(self.filter_combo)
        top_l.addWidget(self.chk_duplicates)
        top_l.addWidget(self.chk_perceptual)
        top_l.addWidget(self.chk_ai)
        top_l.addWidget(self.chk_fast)
        top_l.addWidget(self.busy_indicator)
        top_l.addWidget(self.btn_scan)
        top_l.addWidget(self.btn_stop)
        top_l.addWidget(self.btn_quick)
        top_l.addWidget(self.progress)

        # Table
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Select", "Path", "Type", "Size", "Modified", "Classification", "Duplicates", "Recommendation"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        # Remove borders/obvodky: hide grid and disable row selection outlines
        self.table.setShowGrid(False)
        self.table.setSelectionMode(self.table.SelectionMode.NoSelection)
        # Hide frame and header bottom border (remove white line)
        self.table.setFrameShape(QFrame.NoFrame)
        self.table.setStyleSheet(
            self.table.styleSheet() +
            """
            QHeaderView::section { border: 0px; }
            QTableCornerButton::section { border: 0px; }
            QTableView { background-color: transparent; }
            QTableView::item { background-color: transparent; }
            QTableView::item:selected { background: transparent; }
            QCheckBox { background: transparent; }
            QCheckBox::indicator { border: 0px; background: transparent; }
            """
        )
        # Hide the Duplicates column completely
        self.table.setColumnHidden(6, True)

        # Bottom action bar
        bottom = QWidget()
        bottom_l = QHBoxLayout(bottom)
        self.btn_select_reco = QPushButton("Select Recommended Deletes")
        self.btn_delete = QPushButton("Delete Selected")
        self.btn_move = QPushButton("Move Selected")
        self.btn_compress = QPushButton("Compress Selected")
        bottom_l.addWidget(self.btn_select_reco)
        bottom_l.addWidget(self.btn_delete)
        bottom_l.addWidget(self.btn_move)
        bottom_l.addWidget(self.btn_compress)
        bottom_l.addStretch(1)

        # Central layout (main content) — Overview removed per request
        root = QWidget()
        root_l = QVBoxLayout(root)
        root_l.addWidget(top)
        root_l.addWidget(self.table, 1)
        root_l.addWidget(bottom)
        self.setCentralWidget(root)

        # Signals
        self.btn_folder.clicked.connect(self.on_select_folder)
        self.btn_scan.clicked.connect(self.on_scan)
        self.btn_select_reco.clicked.connect(self.on_select_recommended_deletes)
        self.btn_delete.clicked.connect(self.on_delete_selected)
        self.btn_move.clicked.connect(self.on_move_selected)
        self.btn_compress.clicked.connect(self.on_compress_selected)
        self.btn_clear.clicked.connect(self.on_clear_folders)
        self.filter_combo.currentTextChanged.connect(self.apply_filter)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_quick.clicked.connect(self.on_quick_suggest)

        # Workers
        self._scan_worker = None
        self._analyze_worker = None
        self._folders: list[str] = []
        self._chunk_buffer: list[Dict] = []
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(300)  # Збільшено інтервал для кращої продуктивності
        self._flush_timer.timeout.connect(self._flush_rows)

        # Subtle fade-in animation on table during analysis
        self._fade = QGraphicsOpacityEffect(self.table)
        self.table.setGraphicsEffect(self._fade)
        self._fade.setOpacity(1.0)

        # Animated appearance of progress bar (opacity animation)
        self._progress_fx = QGraphicsOpacityEffect(self.progress)
        self.progress.setGraphicsEffect(self._progress_fx)
        self._progress_fx.setOpacity(0.0)
        self._progress_anim = QPropertyAnimation(self._progress_fx, b"opacity", self)
        self._progress_anim.setDuration(420)
        self._progress_anim.setStartValue(0.0)
        self._progress_anim.setEndValue(1.0)
        self._progress_anim.setEasingCurve(QEasingCurve.InOutQuad)

        # Row animation queue
        self._row_anim_timer = QTimer(self)
        self._row_anim_timer.setInterval(30)
        self._row_anim_timer.timeout.connect(self._tick_row_fade)
        self._fading_rows = {}  # row -> step (0..10)

        # State
        self._stopped = False
        self.btn_stop.setEnabled(False)

        # Helper to enable/disable controls
        self._set_busy(False)

        # Apply custom styles
        self._inject_styles()

        # Menu theme switch (light/dark)
        theme_action = QAction("Toggle Theme", self)
        theme_action.triggered.connect(self.toggle_theme)
        self.menuBar().addAction(theme_action)
        self._is_dark = True

        # Loading overlay for long analysis phase
        self._overlay_dismissed = False
        self._loading_overlay = QWidget(self)
        self._loading_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._loading_overlay.setStyleSheet(
            """
            QWidget { background: rgba(10, 16, 18, 180); }
            QLabel#OverlayTitle { color: #e7fbfb; font-size: 18px; font-weight: 600; }
            QLabel#OverlayHint { color: #a8c7c9; font-size: 13px; }
            QPushButton#OverlayClose { background: #162024; color: #e7fbfb; border: 1px solid #25383d; border-radius: 6px; padding: 6px 10px; }
            QPushButton#OverlayClose:hover { background: #1c2a2f; }
            """
        )
        ol_layout = QVBoxLayout(self._loading_overlay)
        ol_layout.setContentsMargins(28, 24, 28, 24)
        ol_layout.setSpacing(10)
        ol_box = QWidget(self._loading_overlay)
        box_layout = QVBoxLayout(ol_box)
        box_layout.setContentsMargins(16, 14, 16, 14)
        box_layout.setSpacing(8)
        self._ol_title = QLabel("Processing analysis…")
        self._ol_title.setObjectName("OverlayTitle")
        self._ol_hint = QLabel("If loading takes long, you likely selected a folder with a very large number of files.")
        self._ol_hint.setWordWrap(True)
        self._ol_hint.setObjectName("OverlayHint")
        self._ol_close = QPushButton("Hide message")
        self._ol_close.setObjectName("OverlayClose")
        self._ol_close.clicked.connect(self._dismiss_overlay)
        box_layout.addWidget(self._ol_title)
        box_layout.addWidget(self._ol_hint)
        box_layout.addWidget(self._ol_close, alignment=Qt.AlignLeft)
        ol_layout.addStretch(1)
        ol_layout.addWidget(ol_box)
        ol_layout.addStretch(2)
        self._loading_overlay.setVisible(False)
        # Delayed overlay timer to avoid flicker on fast analyses
        self._overlay_timer = QTimer(self)
        self._overlay_timer.setSingleShot(True)
        self._overlay_timer.timeout.connect(lambda: self._show_loading_overlay(True))

    def _dismiss_overlay(self):
        # Hide and mark dismissed to avoid re-showing during this analysis session
        self._overlay_dismissed = True
        self._loading_overlay.setVisible(False)

    # UI Actions
    def toggle_theme(self):
        self._is_dark = not self._is_dark
        theme = 'dark_cyan.xml' if self._is_dark else 'light_cyan.xml'
        app = QApplication.instance()
        if app is not None:
            try:
                apply_stylesheet(app, theme=theme)
            except Exception:
                pass

    def on_select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Add Folder to Scan")
        if path:
            self._folders.append(path)
            self.lbl_folder.setText(
                ", ".join(self._folders[-3:]) if len(self._folders) <= 3 else f"{len(self._folders)} folders selected"
            )

    def on_clear_folders(self):
        self._folders.clear()
        self.lbl_folder.setText("No folders selected")

    def on_scan(self):
        # Reset overlay dismissal for new run
        self._overlay_dismissed = False
        # Reset seen paths to avoid stale duplicates across runs
        self._seen_paths = set()
        # Cancel previous runs if any
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.cancel(); self._scan_worker.wait(500)
        if self._analyze_worker and self._analyze_worker.isRunning():
            self._analyze_worker.cancel(); self._analyze_worker.wait(500)

        if not self._folders:
            QMessageBox.warning(self, "Select Folders", "Please add at least one folder to scan.")
            return
        self._stopped = False
        self._set_busy(True)
        self.table.setRowCount(0)
        # Indeterminate progress during scanning
        self.progress.setRange(0, 0)
        self._records = []
        self._analyses = {}
        self._chunk_buffer.clear()

        self._scan_worker = ScanWorker(self._folders, compute_hash=self.chk_duplicates.isChecked(), fast_mode=self.chk_fast.isChecked())
        self._scan_worker.progress.connect(self.on_scan_progress)
        self._scan_worker.chunk.connect(self.on_scan_chunk)
        self._scan_worker.done.connect(self.on_scan_done)
        self._scan_worker.error.connect(self._on_worker_error)
        self._scan_worker.start()
        self._flush_timer.start()

    def on_scan_progress(self, val: int):
        if val == 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(val)

    def on_scan_chunk(self, rec: Dict):
        # Prevent duplicate rows (seen path set)
        if not hasattr(self, "_seen_paths"):
            self._seen_paths = set()
        p = rec.get("path")
        if p and p in self._seen_paths:
            return
        if p:
            self._seen_paths.add(p)
        self._records.append(rec)
        self._chunk_buffer.append(rec)

    def on_scan_done(self, records: List[Dict]):
        # Finish any pending UI updates
        self._flush_rows()
        self._flush_timer.stop()
        if self._stopped:
            # User stopped; do not start analysis
            self._set_busy(False)
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            return
        # Switch progress back to determinate for analysis
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._records = records
        # Start analysis
        # Schedule the loading overlay to avoid flicker on quick runs
        self._overlay_timer.start(800)
        self._analyze_worker = AnalyzeWorker(
            records=records,
            enable_ai=self.chk_ai.isChecked(),
            use_perceptual=self.chk_perceptual.isChecked(),
            fast_mode=self.chk_fast.isChecked(),
        )
        self._analyze_worker.progress.connect(self.progress.setValue)
        self._analyze_worker.analyzed.connect(self.on_analyzed)
        self._analyze_worker.analyzed_batch.connect(self.on_analyzed_batch)
        self._analyze_worker.done.connect(self.on_analysis_done)
        self._analyze_worker.error.connect(self._on_worker_error)
        self._analyze_worker.start()

    def _add_table_row(self, rec: Dict):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Select checkbox
        chk = QCheckBox()
        chk.setChecked(False)
        # Make checkbox cell transparent to avoid white stripes
        chk.setAttribute(Qt.WA_TranslucentBackground, True)
        chk.setStyleSheet("QCheckBox{background: transparent;} QCheckBox::indicator{border:0;background:transparent;}")
        self.table.setCellWidget(row, 0, chk)

        # Path
        self.table.setItem(row, 1, QTableWidgetItem(rec.get("path", "")))
        # Type
        self.table.setItem(row, 2, QTableWidgetItem(rec.get("kind", "")))
        # Size
        self.table.setItem(row, 3, QTableWidgetItem(human_size(rec.get("size", 0))))
        # Modified
        self.table.setItem(row, 4, QTableWidgetItem(str(int(rec.get("mtime", 0)))))
        # Classification
        self.table.setItem(row, 5, QTableWidgetItem("-"))
        # Duplicates
        self.table.setItem(row, 6, QTableWidgetItem("0"))
        # Recommendation
        self.table.setItem(row, 7, QTableWidgetItem("-"))
        # Initial color by kind
        # Apply initial muted style, then schedule animated reveal
        self._apply_row_style(row, kind=rec.get("kind", "other"), analysis=None, dup_count=0, reco=None)
        # Register for fade effect
        self._fading_rows[row] = 0
        if not self._row_anim_timer.isActive():
            self._row_anim_timer.start()
        self._update_chart()

    def on_analyzed(self, payload: Dict):
        if self._stopped:
            return
        path = payload.get("path")
        self._analyses[path] = payload
        # Find row by path
        for row in range(self.table.rowCount()):
            if self.table.item(row, 1).text() == path:
                analysis = payload.get("analysis", {})
                reco = payload.get("recommendation", {})
                dup_count = payload.get("dup_count", 0)
                self.table.setItem(row, 5, QTableWidgetItem(f"{analysis.get('label','-')} ({analysis.get('confidence',0):.2f})"))
                self.table.setItem(row, 6, QTableWidgetItem(str(dup_count)))
                self.table.setItem(row, 7, QTableWidgetItem(
                    f"{reco.get('primary_action','-')}: "+"; ".join(reco.get('reasons', []))
                ))
                self._apply_row_style(row, kind=self.table.item(row, 2).text(), analysis=analysis, dup_count=dup_count, reco=reco)
                break

        # Update filter visibility and chart after analysis comes in
        self.apply_filter()

    def on_analyzed_batch(self, payloads: List[Dict]):
        if self._stopped:
            return
        # Відключити оновлення UI для швидшого batch update
        self.table.setUpdatesEnabled(False)
        try:
            # Batch update rows for speed
            for payload in payloads:
                path = payload.get("path")
                self._analyses[path] = payload
            # Build an index map from path to row
            index = {}
            for row in range(self.table.rowCount()):
                index[self.table.item(row, 1).text()] = row
            for payload in payloads:
                path = payload.get("path")
                row = index.get(path)
                if row is None:
                    continue
                analysis = payload.get("analysis", {})
                reco = payload.get("recommendation", {})
                dup_count = payload.get("dup_count", 0)
                self.table.setItem(row, 5, QTableWidgetItem(f"{analysis.get('label','-')} ({analysis.get('confidence',0):.2f})"))
                self.table.setItem(row, 6, QTableWidgetItem(str(dup_count)))
                self.table.setItem(row, 7, QTableWidgetItem(
                    f"{reco.get('primary_action','-')}: "+"; ".join(reco.get('reasons', []))
                ))
                self._apply_row_style(row, kind=self.table.item(row, 2).text(), analysis=analysis, dup_count=dup_count, reco=reco)
            self.apply_filter()
        finally:
            # Увімкнути оновлення UI назад
            self.table.setUpdatesEnabled(True)

    def on_analysis_done(self):
        self.statusBar().showMessage("Analysis complete", 5000)
        self._set_busy(False)
        self._overlay_timer.stop()
        self._show_loading_overlay(False)

    def _update_chart(self):
        # Charts are disabled - skip chart updates
        pass

    def _apply_row_style(self, row: int, kind: str, analysis: Dict|None, dup_count: int, reco: Dict|None):
        # Gradient mapping per type for full-row banding - ЗЕЛЕНО-СИНЯ СХЕМА
        def grad(base: QColor, accent: QColor) -> QBrush:
            g = QLinearGradient(0, 0, 1, 0)
            g.setCoordinateMode(QGradient.ObjectBoundingMode)
            g.setColorAt(0.0, base)
            g.setColorAt(0.6, base)
            g.setColorAt(1.0, accent)
            return QBrush(g)

        label = (analysis or {}).get("label", kind)
        q = (analysis or {}).get("quality", {})
        primary = (reco or {}).get("primary_action", "")
        if label == "screenshot":
            brush = grad(QColor(180, 220, 240), QColor(140, 200, 230))  # Блакитний
        elif label == "photo":
            brush = grad(QColor(200, 240, 230), QColor(160, 230, 210))  # М'ятний
        elif kind == "document":
            brush = grad(QColor(210, 250, 220), QColor(180, 240, 200))  # Світло-зелений
        elif kind == "video":
            brush = grad(QColor(190, 230, 240), QColor(160, 215, 230))  # Блакитний
        elif kind == "audio":
            brush = grad(QColor(200, 235, 245), QColor(175, 220, 235))  # Світло-синій
        elif kind == "archive":
            brush = grad(QColor(180, 240, 235), QColor(150, 225, 220))  # Бірюзовий
        elif dup_count > 0:
            brush = grad(QColor(160, 220, 210), QColor(130, 200, 190))  # Темно-м'ятний
        elif q.get("is_low_sharpness") or q.get("is_dark") or q.get("is_small") or primary == "delete":
            brush = grad(QColor(255, 200, 180), QColor(245, 180, 160))  # Помаранчевий (для попередження)
        else:
            brush = grad(QColor(235, 245, 245), QColor(225, 240, 240))  # Нейтральний світлий
        # Color all columns, including the checkbox cell
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item is not None:
                item.setBackground(brush)
            else:
                w = self.table.cellWidget(row, col)
                if w is not None:
                    # Approximate background for widget cell
                    try:
                        pal = w.palette()
                        pal.setColor(w.backgroundRole(), QColor(235, 235, 235))
                        w.setAutoFillBackground(True)
                        w.setPalette(pal)
                    except Exception:
                        pass

        # Increase row height slightly for nicer banding
        self.table.setRowHeight(row, max(self.table.rowHeight(row), 30))

        # Tooltip with explanation for AI decision
        reasons = (reco or {}).get("reasons", [])
        tip_lines = [f"Type: {kind}", f"Class: {label}"]
        if dup_count:
            tip_lines.append(f"Duplicates: {dup_count}")
        qv = (analysis or {}).get("quality", {})
        if qv:
            try:
                tip_lines.append(f"Quality: {qv.get('width','?')}x{qv.get('height','?')}, bright={float(qv.get('brightness',0)):.1f}, sharp={float(qv.get('sharpness',0)):.1f}")
            except Exception:
                pass
        if reasons:
            tip_lines.append("Reasons: " + "; ".join(reasons))
        tooltip = "\n".join(tip_lines)
        for col in range(1, self.table.columnCount()):
            itm = self.table.item(row, col)
            if itm:
                itm.setToolTip(tooltip)

    def on_quick_suggest(self):
        # Scan common user folders without manual selection and immediately analyze
        import os
        user = os.path.expanduser('~')
        candidates = [
            os.path.join(user, 'Downloads'),
            os.path.join(user, 'Desktop'),
            os.path.join(user, 'Documents'),
            os.path.join(user, 'Pictures'),
            os.path.join(user, 'Videos'),
        ]
        paths = [p for p in candidates if os.path.isdir(p)]
        if not paths:
            QMessageBox.information(self, "Quick Suggest", "No common folders found to scan.")
            return
        self._folders = paths
        self.lbl_folder.setText(f"Quick: {len(paths)} folders")
        # Start scan as usual
        self.on_scan()

    def apply_filter(self):
        mode = self.filter_combo.currentText()
        for row in range(self.table.rowCount()):
            kind = self.table.item(row, 2).text()
            dup = int(self.table.item(row, 6).text()) if self.table.item(row, 6) else 0
            label_text = self.table.item(row, 5).text()
            reco_text = self.table.item(row, 7).text()
            show = True
            if mode == "Images":
                show = (kind == "image")
            elif mode == "Documents":
                show = (kind == "document")
            elif mode == "Screenshots":
                show = label_text.startswith("screenshot")
            elif mode == "Low Quality":
                show = ("Low-quality" in reco_text)
            elif mode == "Old Downloads":
                show = ("Downloads" in reco_text)
            elif mode == "Recommended Delete":
                show = reco_text.lower().startswith("delete")
            self.table.setRowHidden(row, not show)

    def on_select_recommended_deletes(self):
        # Tick checkboxes for rows recommended for delete
        count = 0
        for row in range(self.table.rowCount()):
            reco_text = self.table.item(row, 7).text().lower() if self.table.item(row, 7) else ""
            if reco_text.startswith("delete"):
                w = self.table.cellWidget(row, 0)
                if isinstance(w, QCheckBox):
                    if not w.isChecked():
                        w.setChecked(True)
                        count += 1
        if count == 0:
            self.statusBar().showMessage("No recommended deletes to select", 4000)
        else:
            self.statusBar().showMessage(f"Selected {count} recommended deletes", 4000)

    def closeEvent(self, event):
        # Gracefully stop workers to avoid QThread destruction errors
        try:
            if self._scan_worker and self._scan_worker.isRunning():
                self._scan_worker.cancel()
                self._scan_worker.wait(2000)
            if self._analyze_worker and self._analyze_worker.isRunning():
                self._analyze_worker.cancel()
                self._analyze_worker.wait(2000)
        except Exception:
            pass
        super().closeEvent(event)

    def _flush_rows(self):
        # Add up to N rows per tick to keep UI responsive
        N = 500  # Збільшено для кращої продуктивності
        if not self._chunk_buffer:
            return
        # Відключити оновлення під час пакетного додавання
        self.table.setUpdatesEnabled(False)
        try:
            added = 0
            while self._chunk_buffer and added < N:
                rec = self._chunk_buffer.pop(0)
                self._add_table_row(rec)
                added += 1
        finally:
            self.table.setUpdatesEnabled(True)

    def on_stop(self):
        try:
            if self._scan_worker and self._scan_worker.isRunning():
                self._scan_worker.cancel()
                self._scan_worker.wait(1500)
            if self._analyze_worker and self._analyze_worker.isRunning():
                self._analyze_worker.cancel()
                self._analyze_worker.wait(1500)
        except Exception:
            pass
        self._stopped = True
        self._flush_timer.stop()
        self._set_busy(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

    def _set_busy(self, busy: bool):
        self.btn_stop.setEnabled(busy)
        self.btn_scan.setEnabled(not busy)
        enabled = not busy
        for w in [self.btn_folder, self.btn_clear, self.chk_duplicates, self.chk_perceptual, self.chk_ai, self.chk_fast, self.filter_combo]:
            w.setEnabled(enabled)
        if busy:
            self.busy_indicator.start()
            self.busy_indicator.setVisible(True)
            # Animate progress bar appear
            self._progress_anim.stop()
            self._progress_anim.setDirection(QPropertyAnimation.Forward)
            self._progress_anim.start()
        else:
            self.busy_indicator.stop()
            self.busy_indicator.setVisible(False)
            # Animate progress bar disappear
            self._progress_anim.stop()
            self._progress_anim.setDirection(QPropertyAnimation.Backward)
            self._progress_anim.start()

    def resizeEvent(self, event):
        try:
            # Keep overlay covering the whole window content
            if self._loading_overlay:
                self._loading_overlay.setGeometry(self.rect())
        except Exception:
            pass
        super().resizeEvent(event)

    def _on_worker_error(self, msg: str):
        # Suppress disruptive popups; log to status bar instead
        try:
            self.statusBar().showMessage(str(msg), 7000)
        except Exception:
            pass

    def _show_loading_overlay(self, show: bool):
        try:
            if show and self._overlay_dismissed:
                # Respect user dismissal; do not re-show
                return
            self._loading_overlay.setGeometry(self.rect())
            if show:
                # Hide heavy table while overlay is active to prevent drawing artifacts
                self.table.setVisible(False)
                self._loading_overlay.setVisible(True)
                self._loading_overlay.raise_()
                self._loading_overlay.setFocus()
            else:
                self._loading_overlay.setVisible(False)
                self.table.setVisible(True)
                self.table.viewport().update()
        except Exception:
            pass

    def _tick_row_fade(self):
        if not self._fading_rows:
            self._row_anim_timer.stop()
            return
        finished = []
        for row, step in list(self._fading_rows.items()):
            # Increase opacity effect by overlaying a white->none fade (simulate by adjusting alpha of base color)
            factor = min(step / 10.0, 1.0)
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    bg = item.background()
                    # Convert gradient to solid color interpolation end value (rough approximation)
                    # We just adjust transparency by painting a composite color.
                    # Extract first color
                    color = QColor(255, 255, 255, int((1 - factor) * 140))
                    # Store overlay using background role via stylesheet-rich text: not perfect but subtle.
                    # PySide doesn't support per-item opacity directly, so we skip if factor reached.
                    if factor >= 1:
                        # Done
                        pass
            if step >= 10:
                finished.append(row)
            else:
                self._fading_rows[row] = step + 1
        for r in finished:
            self._fading_rows.pop(r, None)



    def _inject_styles(self):
        # Extend existing material theme with custom green-blue gradients
        base = """
        QWidget { background: #1a2428; }
        QMainWindow { background: #1a2428; }
        QPushButton { 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #20b2aa, stop:1 #1e90ff); 
            color: white; 
            border: none; 
            border-radius: 6px; 
            padding: 8px 16px;
            font-weight: 500;
        }
        QPushButton:hover { 
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #17a299, stop:1 #1c7fd4); 
        }
        QPushButton:disabled { 
            background: #3a4448; 
            color: #808080; 
        }
        QProgressBar { 
            background:#1e2a2e; 
            border:1px solid #2a3a3e; 
            border-radius:6px; 
            height:12px; 
        }
        QProgressBar::chunk { 
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00ff9f, stop:0.5 #00d4ff, stop:1 #1e90ff); 
            border-radius:6px; 
        }
        QTableWidget { 
            background: transparent; 
            gridline-color: transparent;
        }
        QHeaderView::section { 
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2a4a4e, stop:1 #1e3438); 
            color: #e0f0f0; 
            padding:8px; 
            border:0; 
            font-weight: 600;
        }
        QComboBox {
            background: #2a3a3e;
            color: #e0f0f0;
            border: 1px solid #3a4a4e;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QLabel {
            color: #d0e8e8;
        }
        """
        self.setStyleSheet(self.styleSheet() + base)

    def _iter_selected_paths(self) -> List[str]:
        sel: List[str] = []
        for row in range(self.table.rowCount()):
            w = self.table.cellWidget(row, 0)
            if isinstance(w, QCheckBox) and w.isChecked():
                sel.append(self.table.item(row, 1).text())
        return sel

    def on_delete_selected(self):
        paths = self._iter_selected_paths()
        if not paths:
            QMessageBox.information(self, "Delete", "No files selected.")
            return
        if QMessageBox.question(self, "Delete", f"Send {len(paths)} files to Recycle Bin?") != QMessageBox.Yes:
            return
        errs = []
        for p in paths:
            try:
                np = windows_long_path(p)
                send2trash(np)
            except Exception as e:
                errs.append(f"{p}: {e}")
        if errs:
            QMessageBox.warning(self, "Some errors", "\n".join(errs[:10]))
        else:
            QMessageBox.information(self, "Done", "Selected files deleted (Recycle Bin)")

    def on_move_selected(self):
        paths = self._iter_selected_paths()
        if not paths:
            QMessageBox.information(self, "Move", "No files selected.")
            return
        dest = QFileDialog.getExistingDirectory(self, "Select destination folder")
        if not dest:
            return
        import shutil
        errs = []
        for p in paths:
            try:
                base = os.path.basename(p)
                target = os.path.join(dest, base)
                i = 1
                while os.path.exists(target):
                    name, ext = os.path.splitext(base)
                    target = os.path.join(dest, f"{name} ({i}){ext}")
                    i += 1
                shutil.move(windows_long_path(p), windows_long_path(target))
            except Exception as e:
                errs.append(f"{p}: {e}")
        if errs:
            QMessageBox.warning(self, "Some errors", "\n".join(errs[:10]))
        else:
            QMessageBox.information(self, "Done", "Selected files moved")

    def on_compress_selected(self):
        paths = self._iter_selected_paths()
        if not paths:
            QMessageBox.information(self, "Compress", "No files selected.")
            return
        zip_path, _ = QFileDialog.getSaveFileName(self, "Save ZIP", "archive.zip", "ZIP Files (*.zip)")
        if not zip_path:
            return
        errs = []
        try:
            with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                for p in paths:
                    try:
                        np = windows_long_path(p)
                        # Try normal write first
                        try:
                            zf.write(np, arcname=os.path.basename(p))
                        except Exception:
                            # Fallback: read bytes and write directly to zip to avoid path issues
                            with open(np, 'rb') as fh:
                                data = fh.read()
                            zf.writestr(os.path.basename(p), data)
                    except Exception as e:
                        errs.append(f"{p}: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Zip Error", str(e))
            return
        if errs:
            QMessageBox.warning(self, "Some errors", "\n".join(errs[:10]))
        else:
            QMessageBox.information(self, "Done", f"Saved {len(paths)} files to {zip_path}")
