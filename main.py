from __future__ import annotations

import sys
import time

import os
import platform
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QLinearGradient, QFont
from PySide6.QtWidgets import QApplication, QSplashScreen


def _generate_app_icon(size: int = 256) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    # Зелено-синій градієнт
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0.0, QColor(32, 178, 170))  # Light Sea Green
    g.setColorAt(1.0, QColor(30, 144, 255))  # Dodger Blue
    p.setBrush(g)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, size, size, size * 0.2, size * 0.2)
    # Stylized broom icon (simple lines)
    p.setPen(QColor(255, 255, 255, 220))
    p.setBrush(QColor(255, 255, 255, 200))
    p.drawRect(int(size * 0.62), int(size * 0.25), int(size * 0.06), int(size * 0.45))  # handle
    p.drawPolygon(
        [
            pm.rect().bottomLeft() + QPoint(int(size * 0.25), -int(size * 0.25)),
            pm.rect().bottomLeft() + QPoint(int(size * 0.55), -int(size * 0.25)),
            pm.rect().bottomLeft() + QPoint(int(size * 0.45), -int(size * 0.05)),
            pm.rect().bottomLeft() + QPoint(int(size * 0.30), -int(size * 0.05)),
        ]
    )
    p.end()
    return QIcon(pm)


# No app.ico generation — use PNG directly


def _show_splash(app: QApplication) -> QSplashScreen:
    pm = QPixmap(600, 360)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    bg = QLinearGradient(0, 0, pm.width(), pm.height())
    bg.setColorAt(0.0, QColor(35, 25, 45))
    bg.setColorAt(1.0, QColor(55, 35, 75))
    p.fillRect(pm.rect(), bg)
    # Title and logo
    p.setPen(QColor(255, 255, 255))
    font = QFont("Segoe UI", 20, QFont.Bold)
    p.setFont(font)
    p.drawText(pm.rect(), Qt.AlignHCenter | Qt.AlignTop, "NeatCore")
    # Center icon.png if available
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        png_path = os.path.join(base, "assets", "icon.png")
        if os.path.exists(png_path):
            logo = QPixmap(png_path).scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (pm.width() - logo.width()) // 2
            y = (pm.height() - logo.height()) // 2
            p.drawPixmap(x, y, logo)
    except Exception:
        pass
    p.end()

    splash = QSplashScreen(pm)
    splash.setWindowFlag(Qt.FramelessWindowHint)
    splash.show()
    # Animated loading dots
    dots = ["", ".", "..", "...", "...."]
    idx = {"i": 0}

    def tick():
        splash.showMessage(f"Starting{dots[idx['i'] % len(dots)]}", Qt.AlignBottom | Qt.AlignHCenter, QColor(255, 255, 255, 220))
        idx["i"] += 1

    t = QTimer()
    t.setInterval(180)
    t.timeout.connect(tick)
    t.start()
    # Store timer on splash to keep alive
    splash._timer = t
    app.processEvents()
    return splash


def main():
    try:
        from ui.main_window import MainWindow
        app = QApplication(sys.argv)

        # Windows taskbar grouping + icon
        if platform.system() == "Windows":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("neatcore.app")
            except Exception:
                pass

        # App icon: prefer file ico (useful for packaging), fallback to generated pixmap
        icon = None
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            # Prefer blue_icon.png for app/taskbar/window icon
            png_path = os.path.join(base, "assets", "blue_icon.png")
            if os.path.exists(png_path):
                icon = QIcon(png_path)
        except Exception:
            icon = None
        if icon is None or icon.isNull():
            icon = _generate_app_icon(256)
        app.setWindowIcon(icon)

        # Splash with simple animation
        splash = _show_splash(app)

        w = MainWindow()
        # Small delay to let animation play a bit
        QTimer.singleShot(600, lambda: (splash.finish(w), w.setWindowIcon(icon), w.show()))

        sys.exit(app.exec())
    except Exception as e:
        import traceback
        print("Startup error:", e)
        traceback.print_exc()


if __name__ == "__main__":
    main()
