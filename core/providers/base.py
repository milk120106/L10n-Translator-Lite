"""翻譯服務的抽象介面。

所有翻譯供應商（Provider）都必須繼承 BaseProvider，
UI 層只依賴此介面，不依賴任何具體實作。
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """單一翻譯供應方法的抽象基底類別。"""

    provider_id: str = ""
    display_name: str = ""
    method_name: str = ""

    api_key: str = ""
    enabled: bool = True

    @abstractmethod
    def is_configured(self) -> bool:
        """回傳此供應方法是否已完成設定（例如 API key 是否備齊）。"""
        raise NotImplementedError

    def is_available(self) -> bool:
        """已啟用且設定齊全，可立即提供翻譯。"""
        return self.enabled and self.is_configured()

    @abstractmethod
    def translate(self, text: str, src: str, tgt: str) -> str:
        """將 text 由 src 語言翻譯為 tgt 語言，回傳譯文。

        src 為 "auto" 時代表自動偵測來源語言。
        此方法為同步阻塞呼叫，必須在背景執行緒中執行。
        """
        raise NotImplementedError