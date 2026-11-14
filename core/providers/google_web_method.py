"""直接打 Google 翻譯免費網頁端點的供應方法。

不經 deep-translator：該套件在「譯文與原文相同」時會刪掉 hl 參數重發同一個
GET，一次點擊變成兩次請求、更容易踩到 429。這裡一次點擊只發一次請求。
"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .base import BaseProvider
from .errors import (
    LanguageNotSupportedError,
    RateLimitedError,
    TranslationError,
    to_display_error,
)

ENDPOINT = "https://translate.googleapis.com/translate_a/single"
TIMEOUT_SECONDS = 15
USER_AGENT = "Mozilla/5.0 (compatible; L10n-Translator-Lite)"


class GoogleWebMethod(BaseProvider):
    """Google 翻譯（免費網頁端點，自行組裝單一 GET）。"""

    provider_id = "google_web"
    display_name = "Google"
    method_name = "web-api"

    def is_configured(self) -> bool:
        # 免費網頁端點不需要 API key 或任何額外設定。
        return True

    def translate(self, text: str, src: str, tgt: str) -> str:
        params = {
            "client": "gtx",
            "sl": src or "auto",
            "tl": tgt,
            "dt": "t",
            "q": text,
        }
        request = Request(
            f"{ENDPOINT}?{urlencode(params)}",
            headers={"User-Agent": USER_AGENT},
        )
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise self._from_http_error(exc) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise TranslationError("無法連線到翻譯服務，請檢查網路後再試。") from exc
        except (ValueError, UnicodeDecodeError) as exc:
            raise TranslationError("翻譯服務回傳格式異常，請稍後再試。") from exc
        except Exception as exc:
            raise to_display_error(exc) from exc
        return self._parse(payload)

    @staticmethod
    def _from_http_error(exc: HTTPError) -> TranslationError:
        if exc.code == 429:
            return RateLimitedError("免費端點限流中（429），請稍後再試。")
        if exc.code == 400:
            return LanguageNotSupportedError("來源或目標語言不被此服務支援。")
        return TranslationError(f"翻譯服務回應異常（HTTP {exc.code}）。")

    @staticmethod
    def _parse(payload: object) -> str:
        # 回傳形如 [[["譯文片段","原文片段",...], ...], null, "en", ...]
        if not isinstance(payload, list) or not payload:
            raise TranslationError("翻譯服務未回傳譯文。")
        segments = payload[0]
        if not isinstance(segments, list):
            raise TranslationError("翻譯服務未回傳譯文。")
        parts = [
            seg[0]
            for seg in segments
            if isinstance(seg, list) and seg and isinstance(seg[0], str)
        ]
        result = "".join(parts)
        if not result:
            raise TranslationError("翻譯服務未回傳譯文。")
        return result
