from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget

class BusyIndicator(QWidget):
    def __init__(self, size: int = 26, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._on_tick)
        self._size = size
        self.setFixedSize(size, size)
        self._running = False

    def start(self):
        if not self._running:
            self._running = True
            self._timer.start()
            self.update()

    def stop(self):
        if self._running:
            self._running = False
            self._timer.stop()
            self.update()

    def _on_tick(self):
        self._angle = (self._angle + 18) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(3,3,-3,-3)
        base_color = QColor(127, 81, 255)
        if not self._running:
            base_color.setAlpha(80)
        pen = QPen(base_color, 4, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        # Draw rotating arc (270 degrees) with current angle offset
        start_angle = self._angle * 16
        span_angle = 270 * 16
        painter.drawArc(rect, start_angle, span_angle)

        # Optional center dot
        dot_color = QColor(255, 79, 163)
        dot_color.setAlpha(160 if self._running else 80)
        painter.setBrush(dot_color)
        painter.setPen(Qt.NoPen)
        d = rect.width() // 6
        painter.drawEllipse(rect.center(), d, d)

        painter.end()
