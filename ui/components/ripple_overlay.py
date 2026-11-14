"""主題切換的圓形顯影覆蓋層。

畫的是「舊主題整窗截圖」，並用矩形減圓形的 clip 把圓內挖空：
圓內露出底下已經換好 QSS 的新主題 UI，圓外維持舊畫面凍結影，
因此整個過渡期間內容都看得見，不會被純色蓋掉。
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QWidget


class RippleOverlay(QWidget):
    def __init__(self, parent: QWidget, center: QPointF, frozen: QPixmap) -> None:
        super().__init__(parent)
        # 動畫期間吞掉點擊，避免使用者在半新半舊的畫面上操作。
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._center = QPointF(center)
        self._frozen = frozen
        self._radius = 0.0
        self.setGeometry(parent.rect())
        self.show()
        self.raise_()

    def set_radius(self, radius: float) -> None:
        self._radius = float(radius)
        self.update()

    def mousePressEvent(self, event) -> None:
        event.accept()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if self._radius <= 0.0:
            painter.drawPixmap(0, 0, self._frozen)
            painter.end()
            return
        hole = QPainterPath()
        hole.addEllipse(self._center, self._radius, self._radius)
        outside = QPainterPath()
        outside.addRect(QRectF(self.rect()))
        painter.setClipPath(outside.subtracted(hole))
        painter.drawPixmap(0, 0, self._frozen)
        painter.end()
