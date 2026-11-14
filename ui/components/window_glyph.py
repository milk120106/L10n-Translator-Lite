"""標題列視窗控制鈕的圖示來源。

優先使用 assets/icons 下的官方 SVG（minimize／maximize／restore／close）；
檔案還沒放進來時退回 QPainter 繪製的線條圖形，
讓視窗控制鈕在任何情況下都辨識得出來、也關得掉。
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from ui.components.svg_icon import has_icon, svg_icon

MINIMIZE = "minimize"
MAXIMIZE = "maximize"
RESTORE = "restore"
CLOSE = "close"

GLYPH_BOX = 10.0
STROKE_WIDTH = 1.4
OVERLAP_OFFSET = 2.0

# 關閉鈕在紅底上必須翻成白色，其餘情境沿用調色盤前景色。
HOVER_FOREGROUND = "#FFFFFF"


@lru_cache(maxsize=32)
def _drawn(name: str, color: str, size: int) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), STROKE_WIDTH)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    box = QRectF(
        (size - GLYPH_BOX) / 2.0, (size - GLYPH_BOX) / 2.0, GLYPH_BOX, GLYPH_BOX
    )
    if name == MINIMIZE:
        y = box.center().y()
        painter.drawLine(QPointF(box.left(), y), QPointF(box.right(), y))
    elif name == MAXIMIZE:
        painter.drawRect(box)
    elif name == RESTORE:
        # 後方方塊只畫被前方方塊遮住的邊以外部分，才會有重疊輪廓。
        front = QPainterPath()
        front.addRect(box)
        canvas = QPainterPath()
        canvas.addRect(QRectF(0.0, 0.0, float(size), float(size)))
        painter.setClipPath(canvas.subtracted(front))
        painter.drawRect(box.translated(OVERLAP_OFFSET, -OVERLAP_OFFSET))
        painter.setClipping(False)
        painter.drawRect(box)
    else:
        painter.drawLine(box.topLeft(), box.bottomRight())
        painter.drawLine(box.topRight(), box.bottomLeft())
    painter.end()
    return QIcon(pixmap)


def window_glyph_icon(name: str, color: str, size: int = 16) -> QIcon:
    """本地 SVG 優先，缺檔退回繪製圖形。"""
    svg_name = f"{name}.svg"
    if has_icon(svg_name):
        return svg_icon(svg_name, color, size)
    return _drawn(name, color, size)
