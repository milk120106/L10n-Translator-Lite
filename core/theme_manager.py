"""主題與全域 QSS 管理。

嚴格規範：禁止任何漸層（qlineargradient／qradialgradient）與陰影效果，
所有色彩皆為平面單色，深／淺主題各一組調色盤。
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from core.config_manager import ConfigManager

DARK = "dark"
LIGHT = "light"
AUTO = "auto"

# 設定頁的下拉選單選項，順序即為顯示順序。
THEME_MODE_LABELS: tuple[tuple[str, str], ...] = (
    (AUTO, "自動（跟隨系統）"),
    (DARK, "強制深色"),
    (LIGHT, "強制淺色"),
)


@dataclass(frozen=True)
class Palette:
    background: str
    surface: str
    text_primary: str
    text_secondary: str
    accent: str
    divider: str
    hover: str
    on_accent: str
    title_hover: str
    close_hover: str
    error: str


DARK_PALETTE = Palette(
    background="#16171A",
    surface="#232428",
    text_primary="#FFFFFF",
    text_secondary="#9E9E9E",
    accent="#75C4D8",
    divider="#2F3136",
    hover="#3A3A3F",
    on_accent="#16171A",
    title_hover="#3A3A3F",
    close_hover="#E81123",
    error="#E81123",
)

LIGHT_PALETTE = Palette(
    background="#F2F3F5",
    surface="#FFFFFF",
    text_primary="#1A1A1C",
    text_secondary="#6B6B6B",
    accent="#5B9FB2",
    divider="#E0E2E6",
    hover="#E8EAEE",
    on_accent="#1A1A1C",
    title_hover="#E0E2E6",
    close_hover="#E81123",
    error="#E81123",
)


def _mix(a: str, b: str, t: float) -> str:
    """線性混合兩個 hex 顏色，t=0 回傳 a，t=1 回傳 b。"""
    ca, cb = QColor(a), QColor(b)
    return QColor(
        round(ca.red() + (cb.red() - ca.red()) * t),
        round(ca.green() + (cb.green() - ca.green()) * t),
        round(ca.blue() + (cb.blue() - ca.blue()) * t),
    ).name()


class ThemeManager(QObject):
    """持有主題模式與實際生效主題，產生對應 QSS，並在切換時發出訊號。

    mode 是使用者選擇（auto／dark／light，會寫入設定檔），
    theme 是目前真正生效的深淺色；auto 模式下兩者會因系統切換而分岔。
    """

    theme_changed = Signal(str)
    mode_changed = Signal(str)

    def __init__(
        self,
        config: ConfigManager | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._mode = config.theme_mode if config is not None else AUTO
        self._theme = self._resolve(self._mode)
        self._system_watch_installed = False
        self.apply_to_app()
        self._watch_system_scheme()

    @property
    def theme(self) -> str:
        """實際生效的主題（深色或淺色）。"""
        return self._theme

    @property
    def mode(self) -> str:
        """使用者選擇的主題模式。"""
        return self._mode

    @property
    def palette(self) -> Palette:
        return DARK_PALETTE if self._theme == DARK else LIGHT_PALETTE

    def resolve(self, mode: str) -> str:
        """預覽：該模式現在會解析成深色還是淺色。"""
        return self._resolve(mode)

    def apply_to_app(self) -> None:
        """把 QSS 寫進整個應用程式，任何控件（含下拉彈窗）都直接吃到主題樣式。"""
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(self.build_qss())

    def set_mode(self, mode: str) -> None:
        if mode not in (AUTO, DARK, LIGHT) or mode == self._mode:
            return
        if self._config is not None:
            self._config.theme_mode = mode
        self._mode = mode
        self.mode_changed.emit(mode)
        self._apply_resolved_theme()

    def toggle(self) -> None:
        """依目前生效主題反轉，並固定為顯式模式（auto 因此被使用者覆寫）。"""
        self.set_mode(LIGHT if self._theme == DARK else DARK)

    # ------------------------------------------------------------------
    # 系統深淺色
    # ------------------------------------------------------------------

    def _resolve(self, mode: str) -> str:
        if mode in (DARK, LIGHT):
            return mode
        return self._system_theme()

    @staticmethod
    def _system_theme() -> str:
        app = QApplication.instance()
        if app is None:
            return DARK
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Unknown:
            # 平台不支援或拿不到（例如離屏測試）：退回專案預設的深色。
            return DARK
        return LIGHT if scheme == Qt.ColorScheme.Light else DARK

    def _watch_system_scheme(self) -> None:
        """auto 模式下跟隨系統：colorSchemeChanged 是 Qt 6.5+ 的信號，缺就跳過。"""
        if self._system_watch_installed:
            return
        app = QApplication.instance()
        if app is None:
            return
        hints = app.styleHints()
        signal = getattr(hints, "colorSchemeChanged", None)
        if signal is None:
            return
        signal.connect(self._on_system_scheme_changed)
        self._system_watch_installed = True

    def _on_system_scheme_changed(self, _scheme) -> None:
        if self._mode != AUTO:
            return
        self._apply_resolved_theme()

    def _apply_resolved_theme(self) -> None:
        theme = self._resolve(self._mode)
        if theme == self._theme:
            return
        self._theme = theme
        self.apply_to_app()
        self.theme_changed.emit(theme)

    def build_qss(self) -> str:
        p = self.palette
        accent_hover = _mix(p.accent, p.text_primary, 0.15)
        combo_hover = _mix(p.background, p.text_secondary, 0.18)
        scroll_handle = _mix(p.surface, p.text_secondary, 0.45)
        return f"""
QWidget {{
    background: transparent;
    color: {p.text_primary};
    font-size: 14px;
}}
QMainWindow {{
    background-color: {p.background};
}}
QFrame#CardWidget {{
    background-color: {p.surface};
    border: none;
    border-radius: 14px;
}}
QFrame#DropArea {{
    background-color: {p.surface};
    border: 1px dashed {p.divider};
    border-radius: 14px;
}}
QFrame#DropArea[dragging="true"] {{
    border: 1px dashed {p.accent};
}}
QFrame#DropArea[error="true"] {{
    border: 1px solid {p.error};
}}
QLabel {{
    background: transparent;
    color: {p.text_primary};
}}
QLabel#FieldLabel {{
    color: {p.text_secondary};
    font-size: 13px;
}}
QLabel#SectionLabel {{
    color: {p.text_secondary};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#StatusLabel {{
    color: {p.text_secondary};
    font-size: 13px;
}}
QLabel#HintLabel {{
    color: {p.text_secondary};
    font-size: 13px;
}}
QLabel#PageTitle {{
    font-size: 17px;
    font-weight: 600;
}}
QLabel#PageSubtitle {{
    color: {p.text_secondary};
    font-size: 14px;
}}
QLabel#PlaceholderLabel {{
    color: {p.text_secondary};
    font-size: 14px;
}}
QLabel#TitleLabel {{
    color: {p.text_secondary};
    font-size: 12px;
    background: transparent;
}}
QFrame#NavSpacer, QFrame#TitleSpacer {{
    background: transparent;
    border: none;
}}
QFrame#DividerLine {{
    background-color: {p.divider};
    border: none;
}}
QFrame#VerticalDivider {{
    background-color: {p.divider};
    border: none;
}}
/* 移除按鈕點擊後的系統虛線焦點框 */
QPushButton:focus {{
    outline: none;
    border: none;
}}
QPlainTextEdit {{
    background: transparent;
    border: none;
    color: {p.text_primary};
    font-size: 15px;
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}
QLineEdit {{
    background-color: {p.surface};
    color: {p.text_primary};
    border: 1px solid {p.divider};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}
QLineEdit:focus {{
    border: 1px solid {p.accent};
}}
QLineEdit:disabled {{
    color: {p.text_secondary};
}}
QComboBox {{
    background-color: {p.background};
    color: {p.text_primary};
    border: none;
    border-radius: 8px;
    padding: 7px 30px 7px 12px;
    min-height: 20px;
}}
QComboBox:focus {{
    outline: none;
}}
QComboBox:hover {{
    background-color: {combo_hover};
}}
QComboBox::drop-down {{
    border: none;
    width: 26px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}}
/* 箭頭改由 ThemedComboBox 以本地 SVG 繪製，這裡把原生三角形收掉。 */
QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
    border: none;
}}
QComboBox QAbstractItemView {{
    background-color: {p.surface};
    color: {p.text_primary};
    border: 1px solid {p.divider};
    border-radius: 10px;
    padding: 4px;
    outline: none;
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}
QComboBox QAbstractItemView::item {{
    min-height: 20px;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    background-color: {p.surface};
    color: {p.text_primary};
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: {p.hover};
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {p.accent};
    color: {p.on_accent};
}}
QComboBox QAbstractItemView::item:focus {{
    outline: none;
    border: none;
}}
QGroupBox {{
    background: transparent;
    border: 1px solid {p.divider};
    border-radius: 12px;
    margin-top: 14px;
    padding: 18px 16px 16px 16px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 3px;
    padding: 0 6px;
    color: {p.text_secondary};
    background-color: {p.background};
    font-size: 13px;
    font-weight: 600;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QPushButton#SidebarItem {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 0 12px;
    text-align: left;
    color: {p.text_secondary};
    font-size: 14px;
}}
QPushButton#SidebarItem:hover {{
    background-color: {p.hover};
    color: {p.text_primary};
}}
QPushButton#SidebarItem:checked {{
    background-color: {p.accent};
    color: {p.on_accent};
    font-weight: 600;
}}
QFrame#SidebarIndicator {{
    background-color: {p.accent};
    border: none;
    border-radius: 2px;
}}
QSplitter::handle {{
    background-color: transparent;
    width: 8px;
}}
QSplitter::handle:horizontal {{
    width: 8px;
}}
QPushButton#NavIconButton {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 0px;
    margin: 0px;
    color: {p.text_secondary};
    font-size: 13px;
}}
QPushButton#NavIconButton:hover {{
    background-color: {p.hover};
    color: {p.text_primary};
}}
QPushButton#NavIconButton:checked {{
    background-color: {p.divider};
    color: {p.accent};
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 9px;
    border: 1px solid {p.text_secondary};
    background: transparent;
}}
QRadioButton::indicator:hover {{
    border: 1px solid {p.accent};
}}
QRadioButton::indicator:checked {{
    border: 1px solid {p.accent};
    background-color: {p.accent};
}}
QCheckBox {{
    background: transparent;
    color: {p.text_primary};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {p.text_secondary};
    background: transparent;
}}
QCheckBox::indicator:hover {{
    border: 1px solid {p.accent};
}}
QCheckBox::indicator:checked {{
    border: 1px solid {p.accent};
    background-color: {p.accent};
    image: none;
}}
QCheckBox:disabled {{
    color: {p.text_secondary};
}}
QComboBox:disabled {{
    color: {p.text_secondary};
    background-color: {p.divider};
}}
QPushButton#NavButton {{
    background: transparent;
    color: {p.text_secondary};
    border: none;
    border-radius: 0;
    padding: 0 18px;
    font-size: 15px;
    font-weight: 500;
}}
QPushButton#NavButton:hover {{
    color: {p.text_primary};
}}
QPushButton#NavButton:checked {{
    color: {p.accent};
    font-weight: 600;
}}
QFrame#NavIndicator {{
    background-color: {p.accent};
    border: none;
    border-radius: 2px;
}}
QPushButton#ThemeToggleButton {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 0px;
    margin: 0px;
}}
QPushButton#ThemeToggleButton:hover {{
    background-color: {p.hover};
}}
QPushButton#ThemeToggleButton:pressed {{
    background-color: {p.divider};
}}
/* 標題列視窗控制鈕：靠 ID 選擇器取得最高優先級，不被通用按鈕規則干預。 */
QToolButton#btn_min, QToolButton#btn_max, QToolButton#btn_close {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
    padding: 0px;
    margin: 0px;
}}
QToolButton#btn_min:hover, QToolButton#btn_max:hover {{
    background-color: {p.title_hover};
}}
QToolButton#btn_min:pressed, QToolButton#btn_max:pressed {{
    background-color: {p.divider};
}}
QToolButton#btn_close:hover {{
    background-color: {p.close_hover};
}}
QToolButton#btn_close:pressed {{
    background-color: {_mix(p.close_hover, p.text_primary, 0.25)};
}}
QPushButton#PrimaryButton {{
    background-color: {p.accent};
    color: {p.on_accent};
    border: none;
    border-radius: 10px;
    padding: 10px 32px;
    font-size: 15px;
    font-weight: 600;
}}
QPushButton#PrimaryButton:hover {{
    background-color: {accent_hover};
}}
QPushButton#PrimaryButton:disabled {{
    background-color: {p.surface};
    color: {p.text_secondary};
}}
QPushButton#SecondaryButton {{
    background-color: {p.surface};
    color: {p.text_primary};
    border: 1px solid {p.divider};
    border-radius: 10px;
    padding: 8px 20px;
}}
QPushButton#SecondaryButton:hover {{
    background-color: {p.hover};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {scroll_handle};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {scroll_handle};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    height: 0;
    width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
QMessageBox {{
    background-color: {p.surface};
}}
QMessageBox QLabel {{
    color: {p.text_primary};
    background: transparent;
    font-size: 14px;
}}
QToolTip {{
    background-color: {p.surface};
    color: {p.text_primary};
    border: 1px solid {p.divider};
    padding: 6px 10px;
}}
"""
