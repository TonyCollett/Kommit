#!/usr/bin/env python3
"""
Kommit – AI-powered Git assistant
Supports OpenAI, Anthropic Claude, Google Gemini, and Ollama APIs
"""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.config_manager import ConfigManager
from ui.main_window import MainWindow


def main():
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller bundle
        app_root = Path(sys._MEIPASS)
    else:
        app_root = Path(__file__).resolve().parent

    config_path = app_root / "kommit_config.ini"

    config = ConfigManager(config_path)

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Kommit")

    icon_path = app_root / "ui" / "assets" / "icon-512.png"
    if icon_path.exists():
        qt_app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow(config)
    window.show()

    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
