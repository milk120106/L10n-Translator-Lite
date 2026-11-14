"""自訂按鈕：按下縮至 0.95，放開以 OutBack 曲線彈回 1.0（150ms）。"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPointF,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QGraphicsScale,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QWidget,
)

PRESS_SCALE = 0.95
PRESS_DURATION = 90
RELEASE_DURATION = 150


class AnimatedButton(QPushButton):
    # QGraphicsScale 無法直接掛到 QWidget，因此動畫化它的 xScale/yScale，
    # 再於 paintEvent 手動把縮放套用到 QPainter 上。
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

        self._scale = QGraphicsScale()
        self._scale.scaleChanged.connect(self.update)

        self._x_anim = QPropertyAnimation(self._scale, b"xScale", self)
        self._y_anim = QPropertyAnimation(self._scale, b"yScale", self)
        self._anim_group = QParallelAnimationGroup(self)
        self._anim_group.addAnimation(self._x_anim)
        self._anim_group.addAnimation(self._y_anim)

    def _animate_scale(self, target: float, duration: int, easing: QEasingCurve) -> None:
        self._anim_group.stop()
        self._x_anim.setStartValue(self._scale.xScale())
        self._y_anim.setStartValue(self._scale.yScale())
        for anim in (self._x_anim, self._y_anim):
            anim.setEndValue(target)
            anim.setDuration(duration)
            anim.setEasingCurve(easing)
        self._anim_group.start()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._animate_scale(PRESS_SCALE, PRESS_DURATION, QEasingCurve.OutQuad)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._animate_scale(1.0, RELEASE_DURATION, QEasingCurve.OutBack)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        if self._scale.xScale() != 1.0 or self._scale.yScale() != 1.0:
            center = QPointF(self.rect().center())
            painter.translate(center)
            painter.scale(self._scale.xScale(), self._scale.yScale())
            painter.translate(-center)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        self.style().drawControl(QStyle.CE_PushButton, option, painter, self)