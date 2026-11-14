"""主題化下拉選單：本機 SVG 箭頭、彈出淡入、滑鼠 hover 高亮。

原生 QSS 三角形無法跟著主題著色，因此把 ::down-arrow 收掉，
改在 paintEvent 依目前調色盤繪製 arrow_drop_down.svg。
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEvent,
    QEasingCurve,
    QItemSelectionModel,
    QPropertyAnimation,
    QRectF,
    Qt,
)
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QStyle,
    QStyleOptionComboBox,
    QStyledItemDelegate,
    QWidget,
)

from core.theme_manager import ThemeManager
from ui.components.svg_icon import has_icon, svg_icon

ARROW_ICON = "arrow_drop_down.svg"
ARROW_SIZE = 18
ITEM_ICON_SIZE = 16
POPUP_FADE_DURATION = 140
# 記下每個項目用的 SVG 檔名，換主題時才能重新著色（UserRole 已給 currentData 用了）。
ICON_NAME_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class ThemedComboBox(QComboBox):
    def __init__(
        self, theme_manager: ThemeManager, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._popup_anim: QPropertyAnimation | None = None
        # QSS 的 ::item:hover 必須在 view 開啟 mouseTracking 後才會觸發。
        self.view().setMouseTracking(True)
        # QComboBox 彈窗預設用舊版 QItemDelegate，::item 的 padding／hover／selected
        # 規則對它完全無效；換成 QStyledItemDelegate 後 QSS 才畫得出來。
        self.view().setItemDelegate(QStyledItemDelegate(self.view()))
        self.view().installEventFilter(self)
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def add_themed_item(
        self, text: str, data: object = None, icon_name: str | None = None
    ) -> None:
        """加入項目；icon_name 為 assets/icons 下的檔名，尚未放檔時退回純文字。"""
        if icon_name is None or not has_icon(icon_name):
            self.addItem(text, data)
            return
        icon = svg_icon(icon_name, self._current_icon_color(), ITEM_ICON_SIZE)
        self.addItem(icon, text, data)
        self.setItemData(self.count() - 1, icon_name, ICON_NAME_ROLE)

    def _current_icon_color(self) -> str:
        return self._theme_manager.palette.text_primary

    def _retint_items(self) -> None:
        color = self._current_icon_color()
        for row in range(self.count()):
            name = self.itemData(row, ICON_NAME_ROLE)
            if isinstance(name, str) and has_icon(name):
                self.setItemIcon(row, svg_icon(name, color, ITEM_ICON_SIZE))

    def eventFilter(self, watched: object, event) -> bool:
        if watched is self.view():
            if event.type() == QEvent.Type.Show:
                self._select_current_row()
                self._fade_popup_in()
            elif event.type() == QEvent.Type.Hide:
                # 復原透明度，避免下次開啟停在動畫中途的值。
                self.view().window().setWindowOpacity(1.0)
        return super().eventFilter(watched, event)

    def _select_current_row(self) -> None:
        """把目前項目真的設成 selected，QSS 的 ::item:selected 才會套用強調色。"""
        row = self.currentIndex()
        if row < 0:
            return
        index = self.view().model().index(row, 0)
        self.view().setCurrentIndex(index)
        self.view().selectionModel().setCurrentIndex(
            index,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )

    def _fade_popup_in(self) -> None:
        popup = self.view().window()
        popup.setWindowOpacity(0.0)
        anim = QPropertyAnimation(popup, b"windowOpacity", self)
        anim.setDuration(POPUP_FADE_DURATION)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._popup_anim = anim
        anim.start()

    def _on_theme_changed(self, *_args) -> None:
        self._retint_items()
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            self,
        )
        if rect.isEmpty():
            return
        palette = self._theme_manager.palette
        color = palette.accent if self.view().isVisible() else palette.text_secondary
        pixmap = svg_icon(ARROW_ICON, color, ARROW_SIZE).pixmap(ARROW_SIZE, ARROW_SIZE)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        target = QRectF(
            rect.center().x() - ARROW_SIZE / 2.0,
            rect.center().y() - ARROW_SIZE / 2.0,
            ARROW_SIZE,
            ARROW_SIZE,
        )
        painter.drawPixmap(target, pixmap, QRectF(0.0, 0.0, float(ARROW_SIZE), float(ARROW_SIZE)))
        painter.end()
