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
            # Try a pink-ish theme similar to CleanMyMac; fallback to dark_teal
            for theme in ('dark_pink.xml', 'dark_amber.xml', 'dark_teal.xml'):
                try:
                    apply_stylesheet(app, theme=theme)
                    break
                except Exception:
                    continue

        # Top bar
        top = QWidget()
        top_l = QHBoxLayout(top)
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
        
            # Sidebar (navigation)
            self.sidebar = QListWidget()
            self.sidebar.setFixedWidth(180)
            self.sidebar.setSpacing(4)
            for label in ["Dashboard", "Results", "Recommendations", "Settings"]:
                item = QListWidgetItem(label)
                item.setSizeHint(Qt.QSize(160, 42))
                self.sidebar.addItem(item)
            self.sidebar.setCurrentRow(0)
            self.sidebar.currentRowChanged.connect(self._on_nav_change)
        
            # Hero page (initial dashboard)
            self.hero_page = QWidget()
            hero_l = QVBoxLayout(self.hero_page)
            hero_l.setAlignment(Qt.AlignCenter)
            self.hero_title = QLabel("Welcome to NeatCore")
            self.hero_title.setStyleSheet("font-size:34px;font-weight:600;letter-spacing:0.5px;color:white;")
            self.hero_sub = QLabel("Start a smart scan to classify, detect duplicates and get safe cleanup recommendations.")
            self.hero_sub.setWordWrap(True)
            self.hero_sub.setStyleSheet("color:rgba(255,255,255,0.75);font-size:14px;max-width:540px;")
            self.hero_scan_btn = QPushButton("Scan Now")
            self.hero_scan_btn.setObjectName("HeroScanButton")
            self.hero_scan_btn.setMinimumSize(160,160)
            self.hero_scan_btn.clicked.connect(self.on_scan)
            self.hero_extra = QPushButton("Quick Suggest Folders")
            self.hero_extra.setObjectName("HeroSuggestButton")
            self.hero_extra.clicked.connect(self.on_quick_suggest)
            hero_l.addWidget(self.hero_title)
            hero_l.addWidget(self.hero_sub)
            hero_l.addSpacing(20)
            hero_l.addWidget(self.hero_scan_btn)
            hero_l.addSpacing(10)
            hero_l.addWidget(self.hero_extra)
        
            # Results page (table + top controls)
            self.results_page = QWidget()
            res_l = QVBoxLayout(self.results_page)
            top_bar = QWidget()
            top_l = QHBoxLayout(top_bar)
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
            res_l.addWidget(top_bar)
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
        self._flush_timer.setInterval(120)
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

        # Menu theme switch (light/dark)
        theme_action = QAction("Toggle Theme", self)
        theme_action.triggered.connect(self.toggle_theme)
        self.menuBar().addAction(theme_action)
        self._is_dark = True

    # UI Actions
    def toggle_theme(self):
        self._is_dark = not self._is_dark
        theme = 'dark_teal.xml' if self._is_dark else 'light_blue.xml'
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
        self._scan_worker.error.connect(lambda e: QMessageBox.critical(self, "Scan Error", e))
        self._scan_worker.start()
        self._flush_timer.start()
        # Switch to results page automatically
        self._stack.setCurrentIndex(1)
        self.sidebar.setCurrentRow(1)

    def on_scan_progress(self, val: int):
        if val == 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(val)

    def on_scan_chunk(self, rec: Dict):
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
        self._analyze_worker.error.connect(lambda e: QMessageBox.critical(self, "Analysis Error", e))
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
        # Ensure we are on results page when rows populate
        if self._stack.currentIndex() != 1:
            self._stack.setCurrentIndex(1)
            self.sidebar.setCurrentRow(1)

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

    def on_analysis_done(self):
        self.statusBar().showMessage("Analysis complete", 5000)
        self._set_busy(False)

    def _update_chart(self):
        # Build a donut chart of kinds (image/document/other) and actions
        counts: Dict[str, int] = {"image": 0, "document": 0, "video": 0, "audio": 0, "archive": 0, "other": 0}
        actions: Dict[str, int] = {"delete": 0, "delete-duplicates": 0, "move": 0, "compress": 0, "ignore": 0}
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            kind = self.table.item(row, 2).text()
            counts[kind] = counts.get(kind, 0) + 1
            reco_text = self.table.item(row, 7).text().lower()
            if reco_text:
                act = reco_text.split(":", 1)[0]
                actions[act] = actions.get(act, 0) + 1

        if not _HAS_CHARTS or self.chart_view is None:
            return
        chart = QChart()
        chart.setTitle("Files by Type and Suggested Actions")

        type_series = QPieSeries()
        for k in ["image", "document", "video", "audio", "archive", "other"]:
            v = counts.get(k, 0)
            if v:
                type_series.append(k, v)
        type_series.setHoleSize(0.35)
        chart.addSeries(type_series)

        action_series = QPieSeries()
        for a in ["delete", "delete-duplicates", "move", "compress", "ignore"]:
            v = actions.get(a, 0)
            if v:
                action_series.append(a, v)
        action_series.setHoleSize(0.6)
        chart.addSeries(action_series)

        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        self.chart_view.setChart(chart)

    def _apply_row_style(self, row: int, kind: str, analysis: Dict|None, dup_count: int, reco: Dict|None):
        # Gradient mapping per type for full-row banding
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
            brush = grad(QColor(232, 210, 255), QColor(206, 170, 255))
        elif label == "photo":
            brush = grad(QColor(200, 240, 245), QColor(160, 220, 235))
        elif kind == "document":
            brush = grad(QColor(210, 255, 220), QColor(180, 245, 200))
        elif kind == "video":
            brush = grad(QColor(255, 230, 200), QColor(255, 215, 170))
        elif kind == "audio":
            brush = grad(QColor(220, 220, 255), QColor(195, 195, 245))
        elif kind == "archive":
            brush = grad(QColor(255, 240, 200), QColor(255, 228, 170))
        elif dup_count > 0:
            brush = grad(QColor(255, 218, 190), QColor(255, 205, 165))
        elif q.get("is_low_sharpness") or q.get("is_dark") or q.get("is_small") or primary == "delete":
            brush = grad(QColor(255, 200, 205), QColor(255, 180, 190))
        else:
            brush = grad(QColor(245, 245, 245), QColor(235, 235, 235))
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
        N = 200
        added = 0
        while self._chunk_buffer and added < N:
            rec = self._chunk_buffer.pop(0)
            self._add_table_row(rec)
            added += 1
        # No overview chart anymore

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

    def _on_nav_change(self, row: int):
        # Simple navigation: dashboard stays if not scanning yet
        self._stack.setCurrentIndex(row)

    def _inject_styles(self):
        # Extend existing material theme with custom gradients
        base = """
        QWidget { background: #1a1d25; }
        QMainWindow { background: #1a1d25; }
        QListWidget { border:0; background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #221c35, stop:1 #181a24); color: #d0d3dc; }
        QListWidget::item { border-radius: 10px; margin:4px; padding:10px 12px; }
        QListWidget::item:selected { background: rgba(127,81,255,0.28); color: #ffffff; }
        QListWidget::item:hover { background: rgba(127,81,255,0.18); }
        #HeroScanButton { border:0; border-radius:80px; background: qradialgradient(cx:0.5, cy:0.45, radius:0.8, stop:0 #ff4fa3, stop:0.55 #7f51ff, stop:1 #4f9dff); color:#fff; font-size:22px; font-weight:600; }
        #HeroScanButton:hover { box-shadow: 0 0 22px rgba(127,81,255,0.65); }
        #HeroSuggestButton { border:1px solid #3b3f48; padding:10px 18px; border-radius:14px; background:#242730; color:#e4e6eb; }
        #HeroSuggestButton:hover { background:#2e323b; }
        QProgressBar { background:#252a33; border:1px solid #2f3540; border-radius:6px; height:12px; }
        QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #ff4fa3, stop:0.5 #7f51ff, stop:1 #4f9dff); border-radius:6px; }
        QPushButton { transition: all 180ms; }
        QPushButton:hover { opacity:0.92; }
        QTableWidget { background: transparent; }
        QHeaderView::section { background:#262b33; color:#d0d3dc; padding:6px; border:0; }
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
