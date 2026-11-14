"""設定頁右側內容：四個分類分頁，各自包在 QScrollArea 中。

每個分頁以 QGroupBox 分組、QFormLayout 排版，確保左標籤、右輸入框對齊。
"""

from __future__ import annotations

import platform

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import (
    FALLBACK_LANGUAGES,
    UI_LANGUAGES,
    ConfigManager,
)
from core.providers.manager import ProviderManager
from core.theme_manager import THEME_MODE_LABELS, ThemeManager
from ui.components.themed_combo import ThemedComboBox
from ui.components.toggle_switch import ToggleSwitch

APP_VERSION = "0.1.0"

# 與 MainWindow 的無邊框判斷保持一致：macOS 使用系統原生標題列。
USE_CUSTOM_TITLE_BAR = platform.system() != "Darwin"

FORM_LABEL_GAP = 24
FORM_ROW_GAP = 14
PAGE_MARGIN = (24, 20, 24, 20)


def make_color_swatch(color: str, size: int = 18, border: str | None = None) -> QPixmap:
    """圓角色票，讓調色盤在設定頁直接可見（直接画，不經 QSS 快照）。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if border is None:
        painter.setPen(Qt.PenStyle.NoPen)
    else:
        painter.setPen(QColor(border))
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(0.5, 0.5, size - 1, size - 1, 6, 6)
    painter.end()
    return pixmap


class SettingsContent(QWidget):
    """設定分頁容器，由左側 SettingsSidebar 驅動 current 索引。"""

    theme_mode_selected = Signal(str)

    def __init__(
        self,
        theme_manager: ThemeManager,
        provider_manager: ProviderManager,
        config: ConfigManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._manager = provider_manager
        self._config = config

        self._stack = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._stack)

        self._build_appearance_page()
        self._build_credentials_page()
        self._build_defaults_page()
        self._build_about_page()

        theme_manager.mode_changed.connect(self._sync_theme_mode)
        theme_manager.theme_changed.connect(self._refresh_swatches)
        self._sync_theme_mode(theme_manager.mode)
        self._refresh_swatches(theme_manager.theme)

    # ------------------------------------------------------------------
    # 排版工具
    # ------------------------------------------------------------------

    def _add_page(self, body: QWidget) -> None:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setWidget(body)
        self._stack.addWidget(area)

    @staticmethod
    def _page_layout(body: QWidget) -> QVBoxLayout:
        layout = QVBoxLayout(body)
        layout.setContentsMargins(*PAGE_MARGIN)
        layout.setSpacing(16)
        return layout

    @staticmethod
    def _form(group: QGroupBox) -> QFormLayout:
        form = QFormLayout(group)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        form.setHorizontalSpacing(FORM_LABEL_GAP)
        form.setVerticalSpacing(FORM_ROW_GAP)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        return form

    @staticmethod
    def _hint(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("HintLabel")
        label.setWordWrap(True)
        return label

    # ------------------------------------------------------------------
    # 外觀與介面
    # ------------------------------------------------------------------

    def _build_appearance_page(self) -> None:
        body = QWidget()
        layout = self._page_layout(body)

        group = QGroupBox("外觀")
        form = self._form(group)

        self._ui_lang_combo = ThemedComboBox(self._theme_manager)
        for code, name in UI_LANGUAGES:
            self._ui_lang_combo.addItem(name, code)
        self._ui_lang_combo.setCurrentIndex(
            max(0, self._ui_lang_combo.findData(self._config.ui_language))
        )
        self._ui_lang_combo.currentIndexChanged.connect(self._sync_ui_language)
        form.addRow("軟體語言", self._ui_lang_combo)

        self._theme_combo = ThemedComboBox(self._theme_manager)
        for mode, label in THEME_MODE_LABELS:
            self._theme_combo.addItem(label, mode)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_mode_changed)
        form.addRow("深淺模式", self._theme_combo)

        self._swatch_row = self._build_swatch_row()
        form.addRow("目前調色盤", self._swatch_row)

        layout.addWidget(group)
        layout.addWidget(
            self._hint(
                "自動（跟隨系統）會讀取作業系統的深／淺色設定並即時切換；"
                "強制深色或強制淺色則固定不受系統影響。選擇會寫入設定檔。"
            )
        )
        layout.addWidget(
            self._hint("軟體語言目前僅記錄偏好，介面字串的國際化尚未實作。")
        )
        layout.addStretch(1)
        self._add_page(body)

    def _build_swatch_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._swatches = [QLabel() for _ in range(4)]
        for swatch in self._swatches:
            layout.addWidget(swatch)
        layout.addStretch(1)
        return row

    def _refresh_swatches(self, *_args) -> None:
        p = self._theme_manager.palette
        for swatch, color in zip(
            self._swatches, (p.background, p.surface, p.accent, p.divider)
        ):
            # 加一圈次級文字色描邊，否則淺色主題的背景色票會跟卡片融為一體。
            swatch.setPixmap(make_color_swatch(color, border=p.text_secondary))

    def _on_theme_mode_changed(self) -> None:
        mode = self._theme_combo.currentData()
        if mode:
            self.theme_mode_selected.emit(mode)

    def _sync_theme_mode(self, mode: str) -> None:
        index = self._theme_combo.findData(mode)
        if index < 0 or index == self._theme_combo.currentIndex():
            return
        # 這是把結果回寫成控件狀態，不能再觸發一次切換。
        self._theme_combo.blockSignals(True)
        self._theme_combo.setCurrentIndex(index)
        self._theme_combo.blockSignals(False)

    def _sync_ui_language(self) -> None:
        code = self._ui_lang_combo.currentData()
        if code:
            self._config.ui_language = code

    # ------------------------------------------------------------------
    # 服務憑證
    # ------------------------------------------------------------------

    def _build_credentials_page(self) -> None:
        body = QWidget()
        layout = self._page_layout(body)

        for provider in self._manager.all_providers():
            group = QGroupBox(f"{provider.display_name}（{provider.method_name}）")
            form = self._form(group)

            key_edit = QLineEdit(provider.api_key)
            key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            key_edit.setClearButtonEnabled(True)
            key_edit.setPlaceholderText("選填：Google 網頁端點不需要金鑰")
            key_edit.textChanged.connect(
                lambda text, pid=provider.provider_id: self._manager.set_api_key(
                    pid, text
                )
            )
            form.addRow("API 金鑰", key_edit)

            switch = ToggleSwitch(self._theme_manager)
            switch.setChecked(provider.enabled)
            switch.toggled.connect(
                lambda on, pid=provider.provider_id: self._manager.set_enabled(
                    pid, on
                )
            )
            form.addRow("啟用此服務", switch)

            layout.addWidget(group)

        layout.addWidget(
            self._hint("關閉開關後，該服務會立即從文字翻譯頁的「服務」選單中移除。")
        )
        layout.addStretch(1)
        self._add_page(body)

    # ------------------------------------------------------------------
    # 翻譯預設
    # ------------------------------------------------------------------

    def _build_defaults_page(self) -> None:
        body = QWidget()
        layout = self._page_layout(body)

        group = QGroupBox("翻譯行為")
        form = self._form(group)

        self._fallback_switch = QCheckBox("啟用語言降級")
        self._fallback_switch.setObjectName("FallbackCheck")
        self._fallback_switch.setChecked(self._config.enable_lang_fallback)
        self._fallback_switch.toggled.connect(self._on_fallback_toggled)
        form.addRow("語言降級", self._fallback_switch)

        self._fallback_combo = ThemedComboBox(self._theme_manager)
        for code, name in FALLBACK_LANGUAGES:
            self._fallback_combo.addItem(name, code)
        self._fallback_combo.setCurrentIndex(
            max(0, self._fallback_combo.findData(self._config.fallback_language))
        )
        self._fallback_combo.currentIndexChanged.connect(self._sync_fallback_language)
        # 未勾選時反灰：預設就是關閉的。
        self._fallback_combo.setEnabled(self._config.enable_lang_fallback)
        form.addRow("降級目標語言", self._fallback_combo)

        layout.addWidget(group)
        layout.addWidget(
            self._hint(
                "目標語言不被該服務支援時，自動改用降級語言重試一次，"
                "而不是直接回報失敗。"
            )
        )
        layout.addStretch(1)
        self._add_page(body)

    def _on_fallback_toggled(self, enabled: bool) -> None:
        self._config.enable_lang_fallback = enabled
        self._fallback_combo.setEnabled(enabled)

    def _sync_fallback_language(self) -> None:
        code = self._fallback_combo.currentData()
        if code:
            self._config.fallback_language = code

    # ------------------------------------------------------------------
    # 關於
    # ------------------------------------------------------------------

    def _build_about_page(self) -> None:
        body = QWidget()
        layout = self._page_layout(body)

        group = QGroupBox("關於")
        form = self._form(group)
        providers = "、".join(
            f"{p.display_name}／{p.method_name}" for p in self._manager.all_providers()
        )
        form.addRow("版本", QLabel(APP_VERSION))
        form.addRow("原始碼授權", QLabel("MIT"))
        form.addRow("圖示授權", QLabel("Material Symbols (Google), Apache License 2.0"))
        form.addRow(
            "標題列",
            QLabel("自訂無邊框標題列" if USE_CUSTOM_TITLE_BAR else "macOS 原生標題列"),
        )
        form.addRow("翻譯供應者", QLabel(providers))
        layout.addWidget(group)
        layout.addStretch(1)
        self._add_page(body)

    # ------------------------------------------------------------------

    def set_category(self, index: int) -> None:
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)
