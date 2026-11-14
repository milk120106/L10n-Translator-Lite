"""文件翻譯頁：拖曳／選擇單一 .txt／.md → 雙欄預覽 → 背景翻譯 → 另存新檔。

翻譯一律透過 TranslateWorker（QThread）在背景執行，
錯誤與進度只進頁面底部狀態列，不彈窗。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.config_manager import ConfigManager
from core.providers.base import BaseProvider
from core.providers.manager import ProviderManager
from ui.components.animated_button import AnimatedButton
from ui.components.card_widget import CardWidget
from ui.pages.text_page import RATE_LIMIT_MESSAGE, TranslateWorker

SUPPORTED_SUFFIXES = {".txt", ".md"}
MAX_CHARS = 5000
FORMAT_MESSAGE = "不支援的檔案格式，請上傳 .txt 或 .md 檔案"
COUNT_MESSAGE = "一次僅支援單一檔案，請重新拖曳。"
OVER_LIMIT_MESSAGE = "Lite 版不支援超長文件，請使用文字翻譯"
ERROR_FLASH_MS = 1200
DEFAULT_SRC = "auto"
DEFAULT_TGT = "zh-TW"


def char_count(text: str) -> int:
    """字數＝非空白字元數，換行與縮排不計入 Lite 版上限。"""
    return sum(1 for ch in text if not ch.isspace())


class DropArea(QFrame):
    """大型拖曳區：邊框顏色隨拖曳／錯誤狀態切換，錯誤紅框短暫閃現。"""

    file_dropped = Signal(str)
    rejected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DropArea")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAcceptDrops(True)
        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.setInterval(ERROR_FLASH_MS)
        self._error_timer.timeout.connect(lambda: self._set_state(error=False))

    def flash_error(self) -> None:
        self._set_state(error=True)
        self._error_timer.start()

    def _set_state(self, **flags: bool) -> None:
        for name, value in flags.items():
            self.setProperty(name, value)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def dragEnterEvent(self, event) -> None:
        # 格式防呆留到 drop 才做：enter 就拒絕的話使用者看不到錯誤訊息。
        if event.mimeData().hasUrls():
            self._set_state(dragging=True)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self._set_state(dragging=False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self._set_state(dragging=False)
        urls = event.mimeData().urls()
        if len(urls) != 1:
            self.rejected.emit(COUNT_MESSAGE)
            return
        path = Path(urls[0].toLocalFile())
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            self.rejected.emit(FORMAT_MESSAGE)
            return
        self.file_dropped.emit(str(path))


class FilePage(QWidget):
    def __init__(
        self,
        provider_manager: ProviderManager,
        config: ConfigManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._manager = provider_manager
        self._config = config
        self._worker: TranslateWorker | None = None
        self._source_path: Path | None = None
        self._char_count = 0
        self._build_ui()

    # ------------------------------------------------------------------
    # 佈局
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(16)

        header = QVBoxLayout()
        header.setSpacing(4)
        title = QLabel("文件翻譯")
        title.setObjectName("PageTitle")
        subtitle = QLabel("上傳單一 .txt／.md 文件，預覽後翻譯並另存新檔")
        subtitle.setObjectName("PageSubtitle")
        header.addWidget(title)
        header.addWidget(subtitle)
        root.addLayout(header)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_upload_page())
        self._stack.addWidget(self._build_preview_page())
        root.addWidget(self._stack, 1)

        self._status = QLabel("")
        self._status.setObjectName("StatusLabel")
        self._status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        root.addWidget(self._status)

    def _build_upload_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self._drop = DropArea()
        self._drop.setMinimumHeight(280)
        self._drop.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._drop.file_dropped.connect(self._load_path)
        self._drop.rejected.connect(self._on_rejected)
        drop_layout = QVBoxLayout(self._drop)
        drop_layout.setSpacing(10)
        drop_layout.addStretch(1)
        main_hint = QLabel("拖曳檔案至此，或點擊下方按鈕選擇")
        main_hint.setObjectName("PageTitle")
        main_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(main_hint)
        sub_hint = QLabel("支援格式：.txt 與 .md（單一檔案）")
        sub_hint.setObjectName("PageSubtitle")
        sub_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(sub_hint)
        drop_layout.addStretch(1)
        layout.addWidget(self._drop, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        pick = AnimatedButton("選擇檔案")
        pick.setObjectName("PrimaryButton")
        pick.clicked.connect(self._on_pick)
        footer.addWidget(pick)
        layout.addLayout(footer)
        return page

    def _build_preview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        body = QHBoxLayout()
        body.setSpacing(16)
        self._source = QPlainTextEdit()
        self._source.setReadOnly(True)
        self._target = QPlainTextEdit()
        self._target.setReadOnly(True)
        self._target.setPlaceholderText("翻譯結果將顯示於此…")
        for label_text, editor in (("原文", self._source), ("譯文", self._target)):
            card = CardWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 12, 16, 16)
            card_layout.setSpacing(8)
            label = QLabel(label_text)
            label.setObjectName("SectionLabel")
            card_layout.addWidget(label)
            card_layout.addWidget(editor, 1)
            body.addWidget(card, 1)
        layout.addLayout(body, 1)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)
        self._repick_btn = AnimatedButton("重新選擇")
        self._repick_btn.setObjectName("SecondaryButton")
        self._repick_btn.clicked.connect(self._on_repicked)
        toolbar.addWidget(self._repick_btn)
        self._translate_btn = AnimatedButton("開始翻譯")
        self._translate_btn.setObjectName("PrimaryButton")
        self._translate_btn.clicked.connect(self._on_translate)
        toolbar.addWidget(self._translate_btn)
        self._save_btn = AnimatedButton("另存新檔")
        self._save_btn.setObjectName("SecondaryButton")
        self._save_btn.clicked.connect(self._on_save)
        self._save_btn.hide()
        toolbar.addWidget(self._save_btn)
        self._info = QLabel("")
        self._info.setObjectName("StatusLabel")
        self._info.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._info.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(self._info, 1)
        layout.addLayout(toolbar)
        return page

    # ------------------------------------------------------------------
    # 載入與格式防呆
    # ------------------------------------------------------------------

    def _on_pick(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "選擇檔案",
            str(Path.home()),
            "支援格式 (*.txt *.md);;所有檔案 (*)",
        )
        if path:
            self._load_path(path)

    def _on_rejected(self, message: str) -> None:
        self._drop.flash_error()
        self._status.setText(message)

    def _load_path(self, path_str: str) -> None:
        path = Path(path_str)
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            self._on_rejected(FORMAT_MESSAGE)
            return
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            self._status.setText("文件不是 UTF-8 編碼，無法讀取。")
            return
        except OSError as exc:
            self._status.setText(f"無法讀取文件：{exc}")
            return
        self._source_path = path
        self._char_count = char_count(text)
        self._source.setPlainText(text)
        self._target.clear()
        self._info.setText(f"{path.name}（{self._char_count} 字）")
        self._save_btn.hide()
        self._translate_btn.setEnabled(True)
        self._status.setText("")
        self._stack.setCurrentIndex(1)

    def _on_repicked(self) -> None:
        self._source_path = None
        self._char_count = 0
        self._source.clear()
        self._target.clear()
        self._info.setText("")
        self._save_btn.hide()
        self._translate_btn.setEnabled(True)
        self._status.setText("")
        self._stack.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # 翻譯與另存
    # ------------------------------------------------------------------

    def _current_provider(self) -> BaseProvider | None:
        available = self._manager.get_available_methods()
        return available[0] if available else None

    def _on_translate(self) -> None:
        if self._char_count > MAX_CHARS:
            self._translate_btn.setEnabled(False)
            self._status.setText(OVER_LIMIT_MESSAGE)
            return
        if self._char_count == 0:
            self._status.setText("文件內容為空，無法翻譯。")
            return
        provider = self._current_provider()
        if provider is None:
            self._status.setText("目前沒有可用的翻譯服務。")
            return
        self._translate_btn.setEnabled(False)
        self._status.setText("翻譯中...")
        self._worker = TranslateWorker(
            provider,
            self._source.toPlainText(),
            DEFAULT_SRC,
            DEFAULT_TGT,
            self._config,
            self,
        )
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.rate_limited.connect(self._on_rate_limited)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_succeeded(self, result: str) -> None:
        self._target.setPlainText(result)
        self._save_btn.show()
        self._status.setText("翻譯完成。")

    def _on_rate_limited(self) -> None:
        self._target.clear()
        self._save_btn.hide()
        self._status.setText(RATE_LIMIT_MESSAGE)

    def _on_failed(self, message: str) -> None:
        self._target.clear()
        self._save_btn.hide()
        self._status.setText(f"翻譯失敗：{message}")

    def _on_finished(self) -> None:
        self._translate_btn.setEnabled(True)
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _on_save(self) -> None:
        if self._source_path is None:
            return
        default = self._source_path.with_name(self._source_path.stem + "_translated.txt")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "另存新檔",
            str(default),
            "文字檔 (*.txt);;所有檔案 (*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(self._target.toPlainText(), encoding="utf-8")
        except OSError as exc:
            self._status.setText(f"儲存失敗：{exc}")
            return
        self._status.setText(f"已儲存至：{path}")

    def wait_for_worker(self, timeout_ms: int = 3000) -> None:
        """視窗關閉時等待背景翻譯結束，避免 QThread 仍在執行就被銷毀。"""
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(timeout_ms)