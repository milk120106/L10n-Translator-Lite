"""以本地 SVG 產生 QIcon：用 QSvgRenderer 讀取 assets/icons，
並將 SVG 內的 currentColor 取代為傳入的主題色。

同一份 SVG 因此可同時服務深／淺主題，不需維護兩套圖示檔。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ICON_DIR = Path(__file__).resolve().parents[2] / "assets" / "icons"


@lru_cache(maxsize=64)
def _render(svg_name: str, color: str, size: int) -> QIcon:
    source = (ICON_DIR / svg_name).read_text(encoding="utf-8")
    colored = source.replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(colored.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError(f"QSvgRenderer 無法解析圖示：{svg_name}")

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0.0, 0.0, float(size), float(size)))
    painter.end()
    return QIcon(pixmap)


def svg_icon(svg_name: str, color: str, size: int = 24) -> QIcon:
    """載入 assets/icons/<svg_name>，以 color 取代 SVG 中的 currentColor。"""
    return _render(svg_name, QColor(color).name(QColor.HexRgb), size)


def has_icon(svg_name: str) -> bool:
    return (ICON_DIR / svg_name).exists()


def optional_icon(svg_name: str, color: str, size: int = 16) -> QIcon | None:
    """選填圖示：檔案還沒放進 assets/icons 時回傳 None，讓呼叫端退回純文字項目。"""
    return svg_icon(svg_name, color, size) if has_icon(svg_name) else None
