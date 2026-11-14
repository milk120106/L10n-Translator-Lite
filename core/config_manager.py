"""設定檔讀寫：所有需要跨啟動保留的偏好都收斂在這裡。

單一儲存點：介面語言、翻譯降級與主題模式共用同一份 JSON，
避免「有些設定會記、有些重開就忘」的雙軌狀態。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / ".l10n-translator" / "config.json"

UI_LANGUAGES: list[tuple[str, str]] = [
    ("zh-TW", "繁體中文"),
    ("zh-CN", "簡體中文"),
    ("en", "English"),
    ("ja", "日本語"),
]

FALLBACK_LANGUAGES: list[tuple[str, str]] = [
    ("en", "英文 (en)"),
    ("zh-TW", "繁體中文 (zh-TW)"),
    ("ja", "日文 (ja)"),
]

THEME_MODES: tuple[str, str, str] = ("auto", "dark", "light")

DEFAULTS: dict[str, Any] = {
    "theme_mode": "auto",
    "ui_language": "zh-TW",
    "enable_lang_fallback": False,
    "fallback_language": "en",
    # 0 代表尚未拖曳過：首次啟動用固定 160px，拖過之後才改存比例。
    "sidebar_ratio": 0.0,
    "sidebar_collapsed": False,
}


class ConfigManager:
    """JSON 設定檔；寫入採暫存檔換名，避免中途損毀留下半截檔案。"""

    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self._path = path
        self._data: dict[str, Any] = {**DEFAULTS, **self._read()}

    # ------------------------------------------------------------------
    # 讀寫
    # ------------------------------------------------------------------

    def _read(self) -> dict[str, Any]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            # 檔案不存在或損毀都退回預設值，不讓啟動卡死。
            return {}
        return raw if isinstance(raw, dict) else {}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(self._path)

    def get(self, key: str) -> Any:
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        if self._data.get(key) == value:
            return
        self._data[key] = value
        self.save()

    # ------------------------------------------------------------------
    # 型別化欄位
    # ------------------------------------------------------------------

    @property
    def theme_mode(self) -> str:
        mode = self._data.get("theme_mode", DEFAULTS["theme_mode"])
        return mode if mode in THEME_MODES else "auto"

    @theme_mode.setter
    def theme_mode(self, mode: str) -> None:
        self.set("theme_mode", mode)

    @property
    def ui_language(self) -> str:
        return self._data.get("ui_language", DEFAULTS["ui_language"])

    @ui_language.setter
    def ui_language(self, code: str) -> None:
        self.set("ui_language", code)

    @property
    def enable_lang_fallback(self) -> bool:
        return bool(
            self._data.get("enable_lang_fallback", DEFAULTS["enable_lang_fallback"])
        )

    @enable_lang_fallback.setter
    def enable_lang_fallback(self, enabled: bool) -> None:
        self.set("enable_lang_fallback", bool(enabled))

    @property
    def fallback_language(self) -> str:
        return self._data.get("fallback_language", DEFAULTS["fallback_language"])

    @fallback_language.setter
    def fallback_language(self, code: str) -> None:
        self.set("fallback_language", code)

    @property
    def sidebar_ratio(self) -> float:
        ratio = self._data.get("sidebar_ratio", DEFAULTS["sidebar_ratio"])
        if not isinstance(ratio, (int, float)):
            return 0.0
        if ratio == 0 or 0.05 <= ratio <= 0.95:
            return float(ratio)
        return 0.0

    @sidebar_ratio.setter
    def sidebar_ratio(self, ratio: float) -> None:
        self.set("sidebar_ratio", round(float(ratio), 4))

    @property
    def sidebar_collapsed(self) -> bool:
        return bool(
            self._data.get("sidebar_collapsed", DEFAULTS["sidebar_collapsed"])
        )

    @sidebar_collapsed.setter
    def sidebar_collapsed(self, collapsed: bool) -> None:
        self.set("sidebar_collapsed", bool(collapsed))
