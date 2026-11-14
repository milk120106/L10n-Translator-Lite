"""文字翻譯頁：頂部參數列、左右雙欄編輯器、底部翻譯按鈕。

翻譯一律透過 TranslateWorker（QThread）在背景執行，
再以 Signal 回報結果，嚴禁阻塞 UI 主執行緒。
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from core.providers.base import BaseProvider
from core.providers.errors import (
    LanguageNotSupportedError,
    RateLimitedError,
    TranslationError,
    to_display_error,
)
from core.providers.manager import ProviderManager
from core.theme_manager import ThemeManager
from ui.components.animated_button import AnimatedButton
from ui.components.card_widget import CardWidget
from ui.components.themed_combo import ThemedComboBox

LANGUAGES: list[tuple[str, str]] = [
    ("auto", "自動偵測"),
    ("zh-TW", "繁體中文"),
    ("zh-CN", "簡體中文"),
    ("en", "英文"),
    ("ja", "日文"),
    ("ko", "韓文"),
    ("es", "西班牙文"),
    ("fr", "法文"),
    ("de", "德文"),
    ("ru", "俄文"),
    ("th", "泰文"),
    ("vi", "越南文"),
]

# 尚未放進 assets/icons 時，add_themed_item 會自動退回純文字項目。
SERVICE_ICON = "cloud.svg"
METHOD_ICON = "terminal.svg"

RATE_LIMIT_MESSAGE = "當前免費接口限流中，請稍後再試，或切換至其他翻譯服務。"


class TranslateWorker(QThread):
    """在背景執行緒呼叫 Provider.translate()，並將例外分級成訊號。"""

    succeeded = Signal(str)
    fallback_used = Signal(str)
    rate_limited = Signal()
    failed = Signal(str)

    def __init__(
        self,
        provider: BaseProvider,
        text: str,
        src: str,
        tgt: str,
        config: ConfigManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._provider = provider
        self._text = text
        self._src = src
        self._tgt = tgt
        self._config = config

    def run(self) -> None:
        # Provider 應把第三方例外收斂成 core.providers.errors 的型別；
        # 最後那個 except 是防堵忘記包好的新供應者直接把背景執行緒炸掉。
        try:
            result = self._provider.translate(self._text, self._src, self._tgt)
        except RateLimitedError:
            self.rate_limited.emit()
        except LanguageNotSupportedError:
            self._try_fallback()
        except TranslationError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(to_display_error(exc)))
        else:
            self.succeeded.emit(result)

    def _try_fallback(self) -> None:
        language = self._config.fallback_language
        if not self._config.enable_lang_fallback or language == self._tgt:
            self.failed.emit("此服務不支援目標語言，且未啟用語言降級。")
            return
        try:
            result = self._provider.translate(self._text, self._src, language)
        except RateLimitedError:
            self.rate_limited.emit()
        except TranslationError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(to_display_error(exc)))
        else:
            self.fallback_used.emit(language)
            self.succeeded.emit(result)


class TextPage(QWidget):
    def __init__(
        self,
        theme_manager: ThemeManager,
        provider_manager: ProviderManager,
        config: ConfigManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._manager = provider_manager
        self._config = config
        self._worker: TranslateWorker | None = None
        self._fallback_language: str | None = None
        self._build_ui(theme_manager)
        self._refresh_services()
        provider_manager.providers_changed.connect(self._refresh_services)

    def _build_ui(self, theme_manager: ThemeManager) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(16)

        param_card = CardWidget()
        param_layout = QHBoxLayout(param_card)
        param_layout.setContentsMargins(16, 14, 16, 14)
        param_layout.setSpacing(16)

        self._src_combo = ThemedComboBox(theme_manager)
        for code, name in LANGUAGES:
            self._src_combo.addItem(f"{name} ({code})", code)
        self._src_combo.setCurrentIndex(0)

        self._tgt_combo = ThemedComboBox(theme_manager)
        for code, name in LANGUAGES:
            if code != "auto":
                self._tgt_combo.addItem(f"{name} ({code})", code)
        self._tgt_combo.setCurrentIndex(self._tgt_combo.findData("zh-TW"))

        self._service_combo = ThemedComboBox(theme_manager)
        self._method_combo = ThemedComboBox(theme_manager)
        self._service_combo.currentIndexChanged.connect(self._refresh_methods)

        for label_text, combo in (
            ("原文語言", self._src_combo),
            ("目標語言", self._tgt_combo),
            ("服務", self._service_combo),
            ("獲取方式", self._method_combo),
        ):
            # 四個下拉並排時，QComboBox 預設以「最長項目」當最小寬度，
            # 整頁會被撐到 1000px 以上，QSplitter 就拖不動側欄。
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            combo.setMinimumContentsLength(4)
            group = QVBoxLayout()
            group.setSpacing(6)
            label = QLabel(label_text)
            label.setObjectName("FieldLabel")
            group.addWidget(label)
            group.addWidget(combo)
            param_layout.addLayout(group, 1)
        root.addWidget(param_card)

        body = QHBoxLayout()
        body.setSpacing(16)
        self._input = QPlainTextEdit()
        self._input.setPlaceholderText("請輸入要翻譯的文字…")
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setPlaceholderText("翻譯結果將顯示於此…")
        for title, editor in (("原文", self._input), ("譯文", self._output)):
            card = CardWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 12, 16, 16)
            card_layout.setSpacing(8)
            label = QLabel(title)
            label.setObjectName("SectionLabel")
            card_layout.addWidget(label)
            card_layout.addWidget(editor, 1)
            body.addWidget(card, 1)
        root.addLayout(body, 1)

        bottom = QHBoxLayout()
        self._status = QLabel("")
        self._status.setObjectName("StatusLabel")
        # 狀態文字是整句中文、沒有空格，QLabel 的最小寬度會等於整串文字寬度，
        # 把整頁撐到拖不動；標成 Ignored 讓它可以縮。
        self._status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        bottom.addWidget(self._status, 1)
        self._translate_btn = AnimatedButton("開始翻譯")
        self._translate_btn.setObjectName("PrimaryButton")
        self._translate_btn.clicked.connect(self._on_translate)
        bottom.addWidget(self._translate_btn)
        root.addLayout(bottom)

    # ------------------------------------------------------------------
    # 服務選單
    # ------------------------------------------------------------------

    def _refresh_services(self) -> None:
        """依 ProviderManager 的可用清單重建選單，並盡量保留原選擇。"""
        previous_service = self._service_combo.currentData()
        previous_method = self._method_combo.currentData()

        self._service_combo.clear()
        seen: list[str] = []
        for provider in self._manager.get_available_methods():
            if provider.display_name in seen:
                continue
            seen.append(provider.display_name)
            self._service_combo.add_themed_item(
                provider.display_name, provider.display_name, SERVICE_ICON
            )

        if not seen:
            self._method_combo.clear()
            self._status.setText("目前沒有已啟用的翻譯服務，請至設定頁開啟。")
            return

        index = self._service_combo.findData(previous_service)
        self._service_combo.setCurrentIndex(index if index >= 0 else 0)
        self._refresh_methods(keep_id=previous_method)

    def _refresh_methods(self, keep_id: str | None = None) -> None:
        self._method_combo.clear()
        service = self._service_combo.currentData()
        for provider in self._manager.get_available_methods():
            if provider.display_name == service:
                self._method_combo.add_themed_item(
                    provider.method_name, provider.provider_id, METHOD_ICON
                )
        if keep_id is not None:
            index = self._method_combo.findData(keep_id)
            if index >= 0:
                self._method_combo.setCurrentIndex(index)

    def _current_provider(self) -> BaseProvider | None:
        provider_id = self._method_combo.currentData()
        return self._manager.get_provider(provider_id) if provider_id else None

    # ------------------------------------------------------------------
    # 翻譯流程
    # ------------------------------------------------------------------

    def _on_translate(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            self._status.setText("請先輸入要翻譯的文字。")
            return
        provider = self._current_provider()
        if provider is None:
            self._status.setText("目前沒有可用的翻譯服務。")
            return

        self._translate_btn.setEnabled(False)
        self._status.setText("翻譯中…")
        self._worker = TranslateWorker(
            provider,
            text,
            self._src_combo.currentData(),
            self._tgt_combo.currentData(),
            self._config,
            self,
        )
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.fallback_used.connect(self._on_fallback_used)
        self._worker.rate_limited.connect(self._on_rate_limited)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_succeeded(self, result: str) -> None:
        self._output.setPlainText(result)
        if self._fallback_language:
            self._status.setText(f"目標語言不支援，已降級為 {self._fallback_language}。")
            self._fallback_language = None
        else:
            self._status.setText("翻譯完成。")

    def _on_fallback_used(self, language: str) -> None:
        self._fallback_language = language

    def _on_rate_limited(self) -> None:
        self._output.clear()
        self._status.setText(RATE_LIMIT_MESSAGE)

    def _on_failed(self, message: str) -> None:
        self._output.clear()
        self._status.setText(f"翻譯失敗：{message}")

    def _on_finished(self) -> None:
        self._translate_btn.setEnabled(True)
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def wait_for_worker(self, timeout_ms: int = 3000) -> None:
        """視窗關閉時等待背景翻譯結束，避免 QThread 仍在執行就被銷毀。"""
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(timeout_ms)
