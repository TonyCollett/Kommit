#!/usr/bin/env python3
"""
AI-powered Git Commit Message Generator – PySide6 Edition
Supports OpenAI, Anthropic Claude, Google Gemini, and Ollama APIs
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.config_manager import ConfigManager
from ui.main_window import MainWindow


def main():
    app_root = Path(__file__).resolve().parent
    config_path = app_root / "git_commit_ai_config.ini"

    config = ConfigManager(config_path)

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("AI Git Commit Message Generator")

    window = MainWindow(config)
    window.show()

    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
