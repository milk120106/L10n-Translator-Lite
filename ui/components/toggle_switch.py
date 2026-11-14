"""平面撥動開關：無漸層、無陰影，顏色直接讀目前調色盤。

刻意不用 QSS 画 indicator，避免被 QGraphicsOpacityEffect 的快取快照卡住舊色。
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QCheckBox, QWidget

from core.theme_manager import ThemeManager

TRACK_WIDTH = 40
TRACK_HEIGHT = 22
KNOB_MARGIN = 3
TEXT_GAP = 10


class ToggleSwitch(QCheckBox):
    def __init__(
        self,
        theme_manager: ThemeManager,
        text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._theme_manager = theme_manager
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, *_args) -> None:
        self.update()

    def sizeHint(self) -> QSize:
        width = TRACK_WIDTH
        if self.text():
            width += TEXT_GAP + QFontMetrics(self.font()).horizontalAdvance(self.text())
        return QSize(width, TRACK_HEIGHT)

    def hitButton(self, pos) -> bool:
        # 整列可點，包含右边的文字，不只軌道。
        return self.rect().contains(pos)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        palette = self._theme_manager.palette
        checked = self.isChecked()
        enabled = self.isEnabled()
        ink = palette.text_primary if enabled else palette.text_secondary

        if checked:
            track_color = palette.accent
        elif not enabled:
            track_color = palette.surface
        else:
            track_color = palette.hover if self._hover else palette.divider

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        top = (self.height() - TRACK_HEIGHT) / 2.0

        painter.setBrush(QColor(track_color))
        painter.drawRoundedRect(
            QRectF(0, top, TRACK_WIDTH, TRACK_HEIGHT),
            TRACK_HEIGHT / 2.0,
            TRACK_HEIGHT / 2.0,
        )

        knob = TRACK_HEIGHT - 2 * KNOB_MARGIN
        knob_x = TRACK_WIDTH - KNOB_MARGIN - knob if checked else KNOB_MARGIN
        painter.setBrush(QColor(ink))
        painter.drawEllipse(QRectF(knob_x, top + KNOB_MARGIN, knob, knob))

        if self.text():
            painter.setPen(QColor(ink))
            painter.drawText(
                QRectF(
                    TRACK_WIDTH + TEXT_GAP,
                    0,
                    max(0, self.width() - TRACK_WIDTH - TEXT_GAP),
                    self.height(),
                ),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                self.text(),
            )
        painter.end()
