"""主視窗：自訂標題列（無邊框）、滑動指示導航列、QSplitter 側欄＋內容雙堆疊。"""

from __future__ import annotations

import math
import platform
from typing import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPointF,
    QPoint,
    QPropertyAnimation,
    QSize,
    QTimer,
    QVariantAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QSplitterHandle,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from core.providers.manager import ProviderManager
from core.theme_manager import DARK, LIGHT, ThemeManager
from ui.components.animated_button import AnimatedButton
from ui.components.ripple_overlay import RippleOverlay
from ui.components.svg_icon import has_icon, svg_icon
from ui.components.title_bar import TitleBar
from ui.pages.file_page import FilePage
from ui.pages.settings_content import SettingsContent
from ui.pages.settings_sidebar import SettingsSidebar
from ui.pages.text_page import TextPage

NAV_ITEMS = ("文字翻譯", "文件翻譯", "設定")
INDICATOR_WIDTH = 28
INDICATOR_HEIGHT = 4
NAV_HEIGHT = 56
NAV_BUTTON_SIZE = 36
NAV_ICON_SIZE = 18
HANDLE_WIDTH = 8
HANDLE_LINE_WIDTH = 1
RESIZE_MARGIN = 6
SIDEBAR_MIN_WIDTH = 120
SIDEBAR_MAX_WIDTH = 400
SIDEBAR_DEFAULT_WIDTH = 160
COLLAPSE_DURATION = 220
FADE_DURATION = 250
RIPPLE_DURATION = 380
THEME_BUTTON_SIZE = 36
THEME_ICON_SIZE = 20
APP_TITLE = "L10n Translator Lite"
COLLAPSE_FALLBACK_TEXT = "☰"


class NavBar(QWidget):
    """主導航列：收起側欄鈕、三個分頁、底部滑動指示線、右側主題切換鈕。"""

    tab_changed = Signal(int)
    theme_toggle_requested = Signal()
    collapse_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NavBar")
        self.setFixedHeight(NAV_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 16, 0)
        layout.setSpacing(4)

        self._collapse_button = AnimatedButton(COLLAPSE_FALLBACK_TEXT)
        self._collapse_button.setObjectName("NavIconButton")
        self._collapse_button.setFixedSize(NAV_BUTTON_SIZE, NAV_BUTTON_SIZE)
        self._collapse_button.setIconSize(QSize(NAV_ICON_SIZE, NAV_ICON_SIZE))
        self._collapse_button.setCheckable(True)
        self._collapse_button.setToolTip("收起／展開側邊欄")
        self._collapse_button.clicked.connect(self.collapse_requested)
        layout.addWidget(self._collapse_button)
        layout.addSpacing(8)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[AnimatedButton] = []
        for index, title in enumerate(NAV_ITEMS):
            button = AnimatedButton(title)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setFixedHeight(NAV_HEIGHT)
            self._group.addButton(button, index)
            layout.addWidget(button)
            self._buttons.append(button)
        layout.addStretch(1)

        self._theme_button = AnimatedButton("")
        self._theme_button.setObjectName("ThemeToggleButton")
        # 正方形且圖示小於按鈕，邊緣自然留出呼吸空間。
        self._theme_button.setFixedSize(THEME_BUTTON_SIZE, THEME_BUTTON_SIZE)
        self._theme_button.setIconSize(QSize(THEME_ICON_SIZE, THEME_ICON_SIZE))
        self._theme_button.setToolTip("切換深色／淺色主題")
        self._theme_button.clicked.connect(self.theme_toggle_requested)
        layout.addWidget(self._theme_button)

        self._indicator = QFrame(self)
        self._indicator.setObjectName("NavIndicator")
        self._indicator.setFixedSize(INDICATOR_WIDTH, INDICATOR_HEIGHT)
        self._indicator.hide()

        self._slide = QPropertyAnimation(self._indicator, b"pos", self)
        self._slide.setDuration(250)
        self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._group.idClicked.connect(self._on_tab_clicked)
        self._buttons[0].setChecked(True)

    @property
    def theme_button(self) -> AnimatedButton:
        """圓形擴散動畫的圓心來源。"""
        return self._theme_button

    def set_theme_icon(self, icon: QIcon) -> None:
        self._theme_button.setIcon(icon)

    def set_collapse_icon(self, icon: QIcon | None, text: str) -> None:
        """有 menu.svg 就用圖示，還沒放進來就退回文字符號。"""
        if icon is None:
            self._collapse_button.setIcon(QIcon())
            self._collapse_button.setText(text)
        else:
            self._collapse_button.setIcon(icon)
            self._collapse_button.setText("")

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        self._collapse_button.setChecked(collapsed)
        self._collapse_button.setToolTip("展開側邊欄" if collapsed else "收起側邊欄")

    def _on_tab_clicked(self, index: int) -> None:
        self.tab_changed.emit(index)
        self._move_indicator(index, animate=True)

    def _indicator_target(self, index: int) -> QPoint:
        button = self._buttons[index]
        x = button.x() + (button.width() - INDICATOR_WIDTH) // 2
        y = self.height() - INDICATOR_HEIGHT
        return QPoint(x, y)

    def _move_indicator(self, index: int, animate: bool) -> None:
        target = self._indicator_target(index)
        # 停下來讀取目前位置再重新啟動，動畫中途切換分頁也能平滑接續。
        self._slide.stop()
        if animate and self._indicator.isVisible():
            self._slide.setStartValue(self._indicator.pos())
            self._slide.setEndValue(target)
            self._slide.start()
        else:
            self._indicator.move(target)
            self._indicator.show()
            self._indicator.raise_()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(
            0, lambda: self._move_indicator(self._group.checkedId(), animate=False)
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._move_indicator(self._group.checkedId(), animate=False)


class SidebarPlaceholder(QWidget):
    """尚未提供分類導航的頁面所對應的佔位側欄。"""

    def __init__(self, title: str, hint: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(6)

        caption = QLabel(title)
        caption.setObjectName("SectionLabel")
        body = QLabel(hint)
        body.setObjectName("HintLabel")
        body.setWordWrap(True)

        layout.addWidget(caption)
        layout.addWidget(body)
        layout.addStretch(1)


class SidebarHandle(QSplitterHandle):
    """8px 命中區、中間只畫 1px 分割線；hover 時整條轉強調色。"""

    def __init__(
        self,
        orientation: Qt.Orientation,
        parent: QSplitter,
        theme_manager: ThemeManager,
    ) -> None:
        super().__init__(orientation, parent)
        self._theme_manager = theme_manager
        theme_manager.theme_changed.connect(lambda *_: self.update())

    def paintEvent(self, event) -> None:
        palette = self._theme_manager.palette
        color = palette.accent if self.underMouse() else palette.divider
        painter = QPainter(self)
        x = (self.width() - HANDLE_LINE_WIDTH) // 2
        painter.fillRect(x, 0, HANDLE_LINE_WIDTH, self.height(), QColor(color))
        painter.end()

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self.update()


class SidebarSplitter(QSplitter):
    """改用自繪 handle 的 QSplitter，其餘行為與原生相同。"""

    def __init__(
        self,
        orientation: Qt.Orientation,
        theme_manager: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(orientation, parent)
        self._theme_manager = theme_manager

    def createHandle(self) -> QSplitterHandle:
        return SidebarHandle(self.orientation(), self, self._theme_manager)


class MainWindow(QMainWindow):
    def __init__(
        self,
        theme_manager: ThemeManager,
        provider_manager: ProviderManager,
        config: ConfigManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._config = config
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(920, 620)
        self.setMouseTracking(True)

        # macOS 保留系統原生標題列（紅綠燈在左側），其餘平台採無邊框＋自訂標題列。
        self._use_custom_title_bar = platform.system() != "Darwin"
        self._title_bar: TitleBar | None = None
        if self._use_custom_title_bar:
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self._title_bar = TitleBar(APP_TITLE, theme_manager)

        central = QWidget()
        central.setObjectName("CentralWidget")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        if self._title_bar is not None:
            root.addWidget(self._title_bar)

        self._nav = NavBar()
        root.addWidget(self._nav)

        hairline = QFrame()
        hairline.setObjectName("DividerLine")
        hairline.setFixedHeight(1)
        root.addWidget(hairline)

        # 左側動態欄與右側內容區以同一個索引連動切換。
        self._sidebar = QStackedWidget()
        self._sidebar.setMinimumWidth(SIDEBAR_MIN_WIDTH)
        self._sidebar.setMaximumWidth(SIDEBAR_MAX_WIDTH)
        self._sidebar.addWidget(
            SidebarPlaceholder("文字翻譯", "語言與服務選項都在右側調整。")
        )
        self._sidebar.addWidget(
            SidebarPlaceholder("文件翻譯", "單一 .txt／.md 文件預覽、翻譯與另存。")
        )
        self._settings_sidebar = SettingsSidebar(theme_manager)
        self._sidebar.addWidget(self._settings_sidebar)

        self._stack = QStackedWidget()
        self._text_page = TextPage(theme_manager, provider_manager, config)
        self._settings_content = SettingsContent(theme_manager, provider_manager, config)
        self._stack.addWidget(self._text_page)
        self._file_page = FilePage(provider_manager, config)
        self._stack.addWidget(self._file_page)
        self._stack.addWidget(self._settings_content)

        # 分隔線交給自繪 handle：8px 命中區＋1px 細線，hover 轉強調色。
        self._splitter = SidebarSplitter(Qt.Orientation.Horizontal, theme_manager)
        self._splitter.setObjectName("SidebarSplitter")
        # 預設帶 1px 面板框，會在收起時讓 handle 縫隙多出一條邊。
        self._splitter.setFrameShape(QFrame.Shape.NoFrame)
        self._splitter.setHandleWidth(HANDLE_WIDTH)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._sidebar)
        self._splitter.addWidget(self._stack)
        self._splitter.setCollapsible(0, True)
        self._splitter.splitterMoved.connect(self._on_splitter_moved)
        for handle in self._splitter.findChildren(QSplitterHandle):
            handle.installEventFilter(self)

        self._content = QWidget()
        content_layout = QHBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self._splitter)
        root.addWidget(self._content, 1)
        self.setCentralWidget(central)

        self._sidebar_ratio = config.sidebar_ratio
        self._sidebar_collapsed = config.sidebar_collapsed
        self._syncing_splitter = False
        self._splitter_sync_pending = False
        self._splitter.installEventFilter(self)
        self._apply_splitter_sizes()
        self._nav.set_sidebar_collapsed(self._sidebar_collapsed)

        # 頁面淡入淡出的 effect 只在動畫期間掛上：常駐 effect 會讓換主題時
        # 留下未重繪的帶狀空白。animation 綁在 effect 的 opacity 上。
        self._fade_effect: QGraphicsOpacityEffect | None = None
        self._fade_anim: QPropertyAnimation | None = None
        self._pending_index: int | None = None
        self._fade_target = 1.0
        # 動畫萬一沒跑（平台不支援 graphics effect 等），watchdog 仍會把頁面落地。
        self._fade_watchdog = QTimer(self)
        self._fade_watchdog.setSingleShot(True)
        self._fade_watchdog.timeout.connect(self._fade_fallback)

        self._collapse_anim: QVariantAnimation | None = None

        self._ripple_overlay: RippleOverlay | None = None
        self._ripple_anim: QVariantAnimation | None = None

        self._settings_sidebar.category_changed.connect(
            self._settings_content.set_category
        )
        self._settings_content.theme_mode_selected.connect(self._change_theme_mode)
        self._nav.tab_changed.connect(self._switch_page)
        self._nav.theme_toggle_requested.connect(self._toggle_theme)
        self._nav.collapse_requested.connect(self._toggle_sidebar)
        self._theme_manager.theme_changed.connect(self._apply_theme)
        self._apply_theme()

        if self._title_bar is not None:
            self._title_bar.minimize_requested.connect(self.showMinimized)
            self._title_bar.toggle_maximize_requested.connect(self._toggle_maximize)
            self._title_bar.close_requested.connect(self.close)
            self.installEventFilter(self)
            app = QApplication.instance()
            if app is not None:
                # hover 不一定會傳播到視窗本身，裝在應用層才能對任何子控件命中邊緣。
                app.installEventFilter(self)

    # ------------------------------------------------------------------
    # 主題
    # ------------------------------------------------------------------

    def _apply_theme(self, *_args) -> None:
        self._update_icons()
        self._refresh_rendering()

    def _update_icons(self) -> None:
        """視窗圖示、收起鈕與主題切換鈕：以目前調色盤為本地 SVG 著色。"""
        palette = self._theme_manager.palette
        self.setWindowIcon(svg_icon("translate.svg", palette.accent))
        # 圖示代表「點選後要切換到的主題」，而非目前主題。
        glyph = "light_mode.svg" if self._theme_manager.theme == DARK else "dark_mode.svg"
        self._nav.set_theme_icon(svg_icon(glyph, palette.text_primary, THEME_ICON_SIZE))
        menu_icon = (
            svg_icon("menu.svg", palette.text_secondary, NAV_ICON_SIZE)
            if has_icon("menu.svg")
            else None
        )
        self._nav.set_collapse_icon(menu_icon, COLLAPSE_FALLBACK_TEXT)

    def _refresh_rendering(self) -> None:
        """換主題後主動重套 QSS 並重繪，避免任何被快取的舊畫面留下來。"""
        style = self.style()
        for widget in self._content.findChildren(QWidget) + [self._content]:
            style.unpolish(widget)
            style.polish(widget)
            widget.update()

    # ------------------------------------------------------------------
    # 主題切換：圓形擴散過渡
    # ------------------------------------------------------------------

    def _toggle_theme(self) -> None:
        next_mode = LIGHT if self._theme_manager.theme == DARK else DARK
        self._start_ripple(
            next_mode,
            lambda: self._theme_manager.set_mode(next_mode),
            self._nav.theme_button,
        )

    def _change_theme_mode(self, mode: str) -> None:
        self._start_ripple(mode, lambda: self._theme_manager.set_mode(mode), None)

    def _start_ripple(
        self,
        target_mode: str,
        apply_changes: Callable[[], None],
        source: QWidget | None,
    ) -> None:
        """凍結舊主題截圖當覆蓋層，立刻換 QSS，再用擴散的圓把新 UI 顯影出來。

        圓內是活的新主題、圓外是舊畫面凍結影，全程內容都可見；
        動畫期間重複點擊直接忽略。
        """
        if self._ripple_overlay is not None:
            return
        if self._theme_manager.resolve(target_mode) == self._theme_manager.theme:
            # 解析後顏色沒變（例如 auto 剛好就是同一色），不用演。
            apply_changes()
            return

        center = self._ripple_center(source or self._nav.theme_button)
        frozen = self.grab()
        self._ripple_overlay = RippleOverlay(self, center, frozen)
        # 換裝在覆蓋層底下完成，顯影圓推進時露出的就是新主題。
        apply_changes()
        anim = QVariantAnimation(self)
        anim.setDuration(RIPPLE_DURATION)
        anim.setStartValue(0.0)
        anim.setEndValue(self._ripple_radius(center))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(self._ripple_overlay.set_radius)
        anim.finished.connect(self._finish_ripple)
        self._ripple_anim = anim
        anim.start()

    def _ripple_center(self, source: QWidget) -> QPointF:
        global_pos = source.mapToGlobal(source.rect().center())
        return QPointF(self.mapFromGlobal(global_pos))

    def _ripple_radius(self, center: QPointF) -> float:
        rect = self.rect()
        corners = (
            (rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight())
        )
        return max(
            math.hypot(center.x() - corner.x(), center.y() - corner.y())
            for corner in corners
        )

    def _finish_ripple(self) -> None:
        overlay, self._ripple_overlay = self._ripple_overlay, None
        self._ripple_anim = None
        # 顯影完成：把動畫期間暫存的頁面切換落地、拆掉 effect，再移除覆蓋層。
        self._commit_page()
        self._detach_page_effect()
        if overlay is not None:
            overlay.deleteLater()

    # ------------------------------------------------------------------
    # 側邊欄：QSplitter 拖曳與收起
    # ------------------------------------------------------------------

    def _toggle_sidebar(self) -> None:
        self.set_sidebar_collapsed(not self._sidebar_collapsed)

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        self._sidebar_collapsed = collapsed
        self._nav.set_sidebar_collapsed(collapsed)
        target = 0 if collapsed else self._target_sidebar_width()
        self._animate_sidebar_width(target)

    def _target_sidebar_width(self) -> int:
        total = self._splitter.width()
        if self._sidebar_ratio > 0:
            width = round(total * self._sidebar_ratio)
        else:
            width = SIDEBAR_DEFAULT_WIDTH
        return min(SIDEBAR_MAX_WIDTH, max(SIDEBAR_MIN_WIDTH, width))

    def _animate_sidebar_width(self, target: int) -> None:
        if self._collapse_anim is not None:
            self._collapse_anim.stop()
            self._collapse_anim.deleteLater()
            self._collapse_anim = None
        start = self._sidebar.width()
        if start == target or self._splitter.width() <= 0:
            self._apply_sidebar_width(target)
            self._persist_sidebar_state()
            return
        anim = QVariantAnimation(self)
        anim.setDuration(COLLAPSE_DURATION)
        anim.setStartValue(float(start))
        anim.setEndValue(float(target))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(self._on_collapse_frame)
        anim.finished.connect(self._on_collapse_finished)
        self._collapse_anim = anim
        anim.start()

    def _on_collapse_frame(self, value) -> None:
        self._apply_sidebar_width(int(value))

    def _on_collapse_finished(self) -> None:
        if self._collapse_anim is not None:
            self._collapse_anim.deleteLater()
            self._collapse_anim = None
        target = 0 if self._sidebar_collapsed else self._target_sidebar_width()
        self._apply_sidebar_width(target)
        self._persist_sidebar_state()

    def _apply_sidebar_width(self, width: int) -> None:
        """剩餘寬度留給 handle，放大視窗時 handle 才不會被撐粗。

        寬度小於下限時同步放寬 minimumWidth，否則 setSizes 會被夾回去。
        """
        total = self._splitter.width()
        if total <= 0:
            return
        self._sidebar.setMinimumWidth(min(SIDEBAR_MIN_WIDTH, width))
        self._syncing_splitter = True
        try:
            self._splitter.setSizes([width, max(1, total - width - HANDLE_WIDTH)])
        finally:
            self._syncing_splitter = False

    def _persist_sidebar_state(self) -> None:
        self._config.sidebar_collapsed = self._sidebar_collapsed
        if not self._sidebar_collapsed and self._sidebar.width() > 0:
            self._sidebar_ratio = self._sidebar.width() / max(1, self._splitter.width())
            self._config.sidebar_ratio = self._sidebar_ratio

    def _sync_splitter_after_layout(self) -> None:
        self._splitter_sync_pending = False
        self._apply_splitter_sizes()

    def _apply_splitter_sizes(self) -> None:
        total = self._splitter.width()
        if total <= 0:
            # 尚未排版（視窗還沒顯示）：先用預設寬度佔位。
            self._splitter.setSizes([SIDEBAR_DEFAULT_WIDTH, 800])
            return
        if self._sidebar_collapsed:
            self._apply_sidebar_width(0)
        else:
            self._apply_sidebar_width(self._target_sidebar_width())

    def _on_splitter_moved(self, _pos: int, _index: int) -> None:
        # 拖曳過程只更新記憶體狀態；寫檔留到 handle 放開（eventFilter）。
        if self._syncing_splitter:
            return
        width = self._sidebar.width()
        self._sidebar_collapsed = width == 0
        self._nav.set_sidebar_collapsed(self._sidebar_collapsed)
        if not self._sidebar_collapsed:
            self._sidebar_ratio = width / max(1, self._splitter.width())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._ripple_overlay is not None:
            self._ripple_overlay.setGeometry(self.rect())

    # ------------------------------------------------------------------
    # 頁面淡入淡出（effect 只在動畫期間存在）
    # ------------------------------------------------------------------

    def _switch_page(self, index: int) -> None:
        if index == self._stack.currentIndex() and self._pending_index is None:
            return
        self._pending_index = index
        if self._fade_effect is None:
            self._attach_page_effect()
            self._animate_opacity(0.0)
        elif self._fade_effect.opacity() <= 0.001:
            self._commit_page()
            self._animate_opacity(1.0)
        else:
            self._animate_opacity(0.0)

    def _attach_page_effect(self) -> None:
        effect = QGraphicsOpacityEffect(self._content)
        effect.setOpacity(1.0)
        self._content.setGraphicsEffect(effect)
        self._fade_effect = effect
        # 屬性必須是 effect 的 opacity；windowOpacity 是視窗的，掛錯會永遠不動。
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(FADE_DURATION)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.finished.connect(self._on_fade_finished)
        self._fade_anim = anim

    def _detach_page_effect(self) -> None:
        self._fade_watchdog.stop()
        if self._fade_anim is not None:
            self._fade_anim.stop()
            self._fade_anim.deleteLater()
            self._fade_anim = None
        self._fade_effect = None
        self._content.setGraphicsEffect(None)

    def _commit_page(self) -> None:
        if self._pending_index is not None:
            self._stack.setCurrentIndex(self._pending_index)
            self._sidebar.setCurrentIndex(self._pending_index)
            self._pending_index = None

    def _animate_opacity(self, target: float) -> None:
        if self._fade_effect is None or self._fade_anim is None:
            self._commit_page()
            return
        self._fade_anim.stop()
        self._fade_target = target
        self._fade_anim.setStartValue(self._fade_effect.opacity())
        self._fade_anim.setEndValue(target)
        self._fade_watchdog.start(FADE_DURATION * 2 + 100)
        self._fade_anim.start()

    def _on_fade_finished(self) -> None:
        if self._fade_effect is None:
            return
        # 只看目標不看實際透明度：動畫被 stop() 打斷時也要把流程接下去。
        if self._fade_target <= 0.001:
            self._commit_page()
            self._animate_opacity(1.0)
        else:
            self._detach_page_effect()

    def _fade_fallback(self) -> None:
        """watchdog：動畫沒跑完也要保證頁面落地、effect 拆掉。"""
        self._commit_page()
        self._detach_page_effect()

    # ------------------------------------------------------------------
    # 自訂標題列與無邊框視窗操作
    # ------------------------------------------------------------------

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        if self._title_bar is not None:
            self._title_bar.set_maximized(self.isMaximized())

    def eventFilter(self, watched, event) -> bool:
        kind = event.type()
        if isinstance(watched, QSplitterHandle) and kind == QEvent.Type.MouseButtonRelease:
            # 拖曳結束才寫檔，避免每移動 1px 就存一次 JSON。
            self._persist_sidebar_state()
            return False
        if watched is self._splitter and kind == QEvent.Type.Resize:
            # Resize 當下 QSplitter 自己還沒重排，直接 setSizes 會被它稍後的內部
            # 重算蓋掉；等這一輪配置跑完再依比例分配。
            if not self._splitter_sync_pending:
                self._splitter_sync_pending = True
                QTimer.singleShot(0, self._sync_splitter_after_layout)
            return False
        if (
            kind in (QEvent.Type.HoverMove, QEvent.Type.HoverLeave)
            and self._use_custom_title_bar
            and not self.isMaximized()
            and isinstance(watched, QWidget)
            and watched.window() is self
        ):
            # hover 的 position 是接收控件的本地座標，拿它判斷會把控件內部
            # 誤認成視窗邊緣；一律用全局座標換算回視窗座標再命中。
            if kind == QEvent.Type.HoverLeave:
                self.unsetCursor()
            else:
                edges = self._edges_at(self.mapFromGlobal(event.globalPosition().toPoint()))
                if edges:
                    self.setCursor(self._resize_cursor(edges))
                else:
                    self.unsetCursor()
            return False
        if watched is self and self._use_custom_title_bar and not self.isMaximized():
            if kind == QEvent.Type.MouseButtonPress:
                edges = self._edges_at(event.position().toPoint())
                handle = self.windowHandle()
                if edges and handle is not None and handle.startSystemResize(edges):
                    return True
        return super().eventFilter(watched, event)

    def _edges_at(self, pos: QPoint) -> Qt.Edges:
        rect = self.rect()
        edges = Qt.Edges()
        if pos.x() <= RESIZE_MARGIN:
            edges |= Qt.Edge.LeftEdge
        if pos.x() >= rect.width() - RESIZE_MARGIN:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= RESIZE_MARGIN:
            edges |= Qt.Edge.TopEdge
        if pos.y() >= rect.height() - RESIZE_MARGIN:
            edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _resize_cursor(edges: Qt.Edges) -> Qt.CursorShape:
        if edges in (
            Qt.Edge.LeftEdge | Qt.Edge.TopEdge,
            Qt.Edge.RightEdge | Qt.Edge.BottomEdge,
        ):
            return Qt.CursorShape.SizeFDiagCursor
        if edges in (
            Qt.Edge.RightEdge | Qt.Edge.TopEdge,
            Qt.Edge.LeftEdge | Qt.Edge.BottomEdge,
        ):
            return Qt.CursorShape.SizeBDiagCursor
        if edges in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
            return Qt.CursorShape.SizeHorCursor
        if edges in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    def closeEvent(self, event) -> None:
        self._text_page.wait_for_worker()
        self._file_page.wait_for_worker()
        super().closeEvent(event)
