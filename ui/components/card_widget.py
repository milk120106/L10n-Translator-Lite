"""卡片容器：圓角 14px、無邊框、無陰影。

表面色由全域 QSS 的 QFrame#CardWidget 規則提供，深淺主題自動切換。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QWidget


class CardWidget(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CardWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)