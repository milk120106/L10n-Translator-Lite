"""L10n-Translator-Lite 應用程式入口。"""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from core.config_manager import ConfigManager
from core.providers.manager import ProviderManager
from core.theme_manager import ThemeManager
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("L10n Translator Lite")
    app.setFont(QFont("Microsoft JhengHei UI", 10))

    # 順序固定：先讀設定，ThemeManager 才知道這次要 auto 還是強制深／淺。
    config = ConfigManager()
    theme_manager = ThemeManager(config)
    provider_manager = ProviderManager()

    window = MainWindow(theme_manager, provider_manager, config)
    window.resize(1100, 720)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())