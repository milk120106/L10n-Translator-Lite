"""設定頁左側分類導航：自訂按鈕群＋左緣垂直滑動指示器。

取代原本的 QListWidget——列表項的選中樣式由 QSS 控制，指示器卻無法在
QListWidget 上自由滑動；改成按鈕群後，指示器就跟頂部導航列一樣是一條
獨立 QFrame，可以用同一套動畫邏輯打斷接續。
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QSize,
    QTimer,
    Signal,
)
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.theme_manager import ThemeManager
from ui.components.animated_button import AnimatedButton
from ui.components.svg_icon import has_icon, svg_icon

CATEGORIES: tuple[tuple[str, str], ...] = (
    ("外觀與介面", "palette.svg"),
    ("服務憑證", "key.svg"),
    ("翻譯預設", "tune.svg"),
    ("關於", "info.svg"),
)

CATEGORY_ICON_SIZE = 18
ITEM_HEIGHT = 44
INDICATOR_WIDTH = 4
INDICATOR_HEIGHT = 28
SLIDE_DURATION = 250


class SettingsSidebar(QWidget):
    """分類按鈕群：點選發出 category_changed，指示器以 250ms 平滑上下滑動。"""

    category_changed = Signal(int)

    def __init__(
        self, theme_manager: ThemeManager, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsSidebar")
        self._theme_manager = theme_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(2)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[AnimatedButton] = []
        for index, (title, icon_name) in enumerate(CATEGORIES):
            button = AnimatedButton(title)
            button.setObjectName("SidebarItem")
            button.setCheckable(True)
            button.setFixedHeight(ITEM_HEIGHT)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _checked=False, row=index: self._on_clicked(row))
            self._group.addButton(button, index)
            layout.addWidget(button)
            self._buttons.append(button)
        layout.addStretch(1)

        self._indicator = QFrame(self)
        self._indicator.setObjectName("SidebarIndicator")
        self._indicator.setFixedSize(INDICATOR_WIDTH, INDICATOR_HEIGHT)
        self._indicator.hide()

        self._slide = QPropertyAnimation(self._indicator, b"pos", self)
        self._slide.setDuration(SLIDE_DURATION)
        self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._current = 0
        self._buttons[0].setChecked(True)
        self._refresh_icons()
        theme_manager.theme_changed.connect(self._refresh_icons)
        QTimer.singleShot(0, lambda: self._move_indicator(self._current, animate=False))

    # ------------------------------------------------------------------

    def _refresh_icons(self) -> None:
        """圖示顏色跟著調色盤走；SVG 還沒放進來時就只顯示文字。"""
        color = self._theme_manager.palette.text_primary
        for button, (_title, icon_name) in zip(self._buttons, CATEGORIES):
            if has_icon(icon_name):
                button.setIcon(svg_icon(icon_name, color, CATEGORY_ICON_SIZE))
            else:
                button.setIcon(QIcon())
            button.setIconSize(QSize(CATEGORY_ICON_SIZE, CATEGORY_ICON_SIZE))

    def _on_clicked(self, row: int) -> None:
        self._current = row
        self._move_indicator(row, animate=True)
        self.category_changed.emit(row)

    def _target_pos(self, row: int) -> QPoint:
        button = self._buttons[row]
        y = button.y() + (button.height() - INDICATOR_HEIGHT) // 2
        return QPoint(0, y)

    def _move_indicator(self, row: int, animate: bool) -> None:
        target = self._target_pos(row)
        # 先讀取目前位置再重新啟動：動畫中途改點別項也能平滑接續，不會跳位。
        self._slide.stop()
        if animate and self._indicator.isVisible():
            self._slide.setStartValue(self._indicator.pos())
            self._slide.setEndValue(target)
            self._slide.start()
        else:
            self._indicator.move(target)
            self._indicator.show()
            self._indicator.raise_()

    def set_category(self, row: int) -> None:
        if 0 <= row < len(self._buttons) and row != self._current:
            self._buttons[row].setChecked(True)
            self._on_clicked(row)

    def current_category(self) -> int:
        return self._current

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._move_indicator(self._current, animate=False)
