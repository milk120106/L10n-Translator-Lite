"""自訂無邊框視窗的標題列：32px 拖拽區＋視窗控制鈕。

macOS 不適用：紅綠燈在左側且由系統繪製，硬拔標題列會很怪，
因此 MainWindow 只在非 Darwin 平台建立此元件。

背景色（含關閉鈕的紅色 hover）全部交給 QSS 的 ID 規則，
程式只負責圖示本身與「hover 時要翻白」的顏色切換。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from core.theme_manager import ThemeManager
from ui.components.window_glyph import (
    CLOSE,
    HOVER_FOREGROUND,
    MAXIMIZE,
    MINIMIZE,
    RESTORE,
    window_glyph_icon,
)

TITLE_BAR_HEIGHT = 32
BUTTON_WIDTH = 46
GLYPH_SIZE = 16


class WindowButton(QToolButton):
    """46x32 的視窗控制鈕：QSS 畫背景，QIcon 畫線條。"""

    def __init__(
        self,
        object_name: str,
        glyph: str,
        tooltip: str,
        theme_manager: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self._glyph = glyph
        self._theme_manager = theme_manager
        self.setFixedSize(BUTTON_WIDTH, TITLE_BAR_HEIGHT)
        self.setIconSize(QSize(GLYPH_SIZE, GLYPH_SIZE))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self._update_icon()

    def set_glyph(self, glyph: str) -> None:
        self._glyph = glyph
        self._update_icon()

    def refresh(self) -> None:
        """換主題後重取前景色：QIcon 是快取點圖，不會跟著調色盤自己變。"""
        self._update_icon()

    def _update_icon(self) -> None:
        self.setIcon(window_glyph_icon(self._glyph, self._foreground(), GLYPH_SIZE))

    def _foreground(self) -> str:
        # 關閉鈕 hover 時底色變紅，叉叉必須翻白才看得見。
        if self._glyph == CLOSE and self.underMouse():
            return HOVER_FOREGROUND
        return self._theme_manager.palette.text_primary

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._update_icon()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._update_icon()


class TitleBar(QWidget):
    """可拖拽的標題列；右側為縮小／最大化／關閉，雙擊切換最大化。"""

    minimize_requested = Signal()
    toggle_maximize_requested = Signal()
    close_requested = Signal()

    def __init__(
        self,
        title: str,
        theme_manager: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(TITLE_BAR_HEIGHT)
        self.setObjectName("TitleBar")
        self._theme_manager = theme_manager
        self._drag_offset: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 0, 0)
        layout.setSpacing(0)

        label = QLabel(title)
        label.setObjectName("TitleLabel")
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(label)

        spacer = QWidget()
        spacer.setObjectName("TitleSpacer")
        spacer.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(spacer, 1)

        self._min_button = WindowButton("btn_min", MINIMIZE, "縮小", theme_manager, self)
        self._maximize_button = WindowButton(
            "btn_max", MAXIMIZE, "最大化", theme_manager, self
        )
        self._close_button = WindowButton(
            "btn_close", CLOSE, "關閉", theme_manager, self
        )
        self._min_button.clicked.connect(self.minimize_requested)
        self._maximize_button.clicked.connect(self.toggle_maximize_requested)
        self._close_button.clicked.connect(self.close_requested)
        for button in (self._min_button, self._maximize_button, self._close_button):
            layout.addWidget(button)

        theme_manager.theme_changed.connect(self._refresh_icons)

    def _refresh_icons(self, *_args) -> None:
        for button in (self._min_button, self._maximize_button, self._close_button):
            button.refresh()

    def set_maximized(self, maximized: bool) -> None:
        self._maximize_button.set_glyph(RESTORE if maximized else MAXIMIZE)
        self._maximize_button.setToolTip("還原視窗大小" if maximized else "最大化")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window()
            self._drag_offset = (
                event.globalPosition().toPoint() - window.frameGeometry().topLeft()
            )
            focus = window.focusWidget()
            if focus is not None:
                focus.clearFocus()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        window = self.window()
        if window.isMaximized():
            window.showNormal()
            self.set_maximized(False)
            self._drag_offset = QPoint(window.width() // 2, TITLE_BAR_HEIGHT // 2)
        window.move(event.globalPosition().toPoint() - self._drag_offset)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximize_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
