"""翻譯供應者的例外分級。

UI 只依賴這裡的類別，不直接 import 第三方套件的例外型別，
因此更换或新增供應方法時，畫面層不需要跟着改。
"""

from __future__ import annotations


class TranslationError(Exception):
    """翻譯失敗基底例外；字串內容為可直接顯示給使用者的短句。"""


class RateLimitedError(TranslationError):
    """免費端點回傳 429／要求過多。"""


class LanguageNotSupportedError(TranslationError):
    """來源或目標語言不被該服務支援。"""


class ProviderUnavailableError(TranslationError):
    """目前沒有已啟用且可用的翻譯服務。"""


def to_display_error(exc: Exception) -> TranslationError:
    """把未預期的例外收斂成一行短文，避免把原始錯誤訊息整段丢進 UI。"""
    text = str(exc).strip()
    first_line = text.splitlines()[0] if text else ""
    return TranslationError(first_line[:160] or exc.__class__.__name__)
