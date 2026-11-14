"""Provider 調度中心。

負責註冊、設定與查詢所有可用的翻譯供應方法。
未來新增供應商時，只需在此註冊，UI 層無需修改。
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from .base import BaseProvider
from .google_web_method import GoogleWebMethod


class ProviderManager(QObject):
    """供應方法註冊表；設定頁更動啟用狀態或金鑰時發出 providers_changed。"""

    providers_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._providers: dict[str, BaseProvider] = {}
        self.register(GoogleWebMethod())

    def register(self, provider: BaseProvider) -> None:
        self._providers[provider.provider_id] = provider

    def all_providers(self) -> list[BaseProvider]:
        """包含未啟用與未設定的全部供應方法（供設定頁列表使用）。"""
        return list(self._providers.values())

    def get_available_methods(self) -> list[BaseProvider]:
        """回傳已啟用且已完成設定、可立即使用的供應方法。"""
        return [p for p in self._providers.values() if p.is_available()]

    def get_provider(self, provider_id: str) -> BaseProvider | None:
        return self._providers.get(provider_id)

    def set_enabled(self, provider_id: str, enabled: bool) -> None:
        provider = self._providers.get(provider_id)
        if provider is None or provider.enabled == enabled:
            return
        provider.enabled = enabled
        self.providers_changed.emit()

    def set_api_key(self, provider_id: str, api_key: str) -> None:
        provider = self._providers.get(provider_id)
        if provider is None or provider.api_key == api_key:
            return
        was_available = provider.is_available()
        provider.api_key = api_key
        # 只在可用性真的翻轉時通知，避免每次鍵入都重建下拉選單。
        if provider.is_available() != was_available:
            self.providers_changed.emit()
