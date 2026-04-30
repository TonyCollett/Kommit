"""Configuration dialog with tabs for API, Code Review, and GUI settings."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QProgressDialog,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.ai_service import (
    AIService,
    OPENAI_AVAILABLE,
    ANTHROPIC_AVAILABLE,
    GEMINI_AVAILABLE,
    OLLAMA_AVAILABLE,
)
from core.config_manager import ConfigManager
from ui.widgets.worker import WorkerThread


class ConfigDialog(QDialog):
    """Modal dialog for editing application configuration."""

    def __init__(self, parent, config: ConfigManager, ai: AIService):
        super().__init__(parent)
        self.config = config
        self.ai = ai
        self._active_thread = None

        self.setWindowTitle("Configuration")
        self.resize(800, 640)
        self.setMinimumSize(600, 400)

        self._setup_ui()
        self._on_provider_changed()

    # ── UI construction ──────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_api_tab(), "API Settings")
        tabs.addTab(self._build_review_tab(), "Code Review")
        tabs.addTab(self._build_root_cause_tab(), "Root Cause")
        tabs.addTab(self._build_gui_tab(), "GUI Settings")
        layout.addWidget(tabs, stretch=1)

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ── API Settings tab ─────────────────────────────────────────────

    def _build_api_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)

        # Provider row
        prov_row = QHBoxLayout()
        prov_row.addWidget(QLabel("AI Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["openai", "anthropic", "gemini", "ollama"])
        self.provider_combo.setCurrentText(self.config.provider)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        prov_row.addWidget(self.provider_combo, stretch=1)

        self.pkg_status_label = QLabel()
        self.pkg_status_label.setStyleSheet("color: #CC0000;")
        prov_row.addWidget(self.pkg_status_label)

        self.pkg_install_btn = QPushButton("Install Package")
        self.pkg_install_btn.clicked.connect(self._install_missing)
        self.pkg_install_btn.hide()
        prov_row.addWidget(self.pkg_install_btn)

        lay.addLayout(prov_row)

        # API key / host fields (stacked; visibility toggled)
        self.openai_key = QLineEdit(self.config.get("API", "openai_api_key"))
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_key = QLineEdit(self.config.get("API", "anthropic_api_key"))
        self.anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key = QLineEdit(self.config.get("API", "gemini_api_key"))
        self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ollama_host = QLineEdit(
            self.config.get("API", "ollama_host", fallback="http://localhost:11434")
        )

        self._key_rows = {}
        for label_text, widget, key in [
            ("OpenAI API Key:", self.openai_key, "openai"),
            ("Anthropic API Key:", self.anthropic_key, "anthropic"),
            ("Gemini API Key:", self.gemini_key, "gemini"),
            ("Ollama Host URL:", self.ollama_host, "ollama"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(130)
            row.addWidget(lbl)
            row.addWidget(widget, stretch=1)
            container = QWidget()
            container.setLayout(row)
            lay.addWidget(container)
            self._key_rows[key] = container

        # Model
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self.model_edit = QLineEdit(self.config.model)
        model_row.addWidget(self.model_edit, stretch=1)
        lay.addLayout(model_row)

        hint = QLabel(
            "Common models:  OpenAI: gpt-4.1-mini, gpt-4o  |  "
            "Anthropic: claude-3-haiku-20240307  |  Gemini: gemini-1.5-flash  |  "
            "Ollama: llama3, mistral"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        lay.addWidget(hint)

        # Prompt settings
        prompt_grp = QGroupBox("Commit Message Prompts")
        prompt_lay = QVBoxLayout(prompt_grp)

        prompt_lay.addWidget(QLabel("System Prompt:"))
        self.sys_prompt = QPlainTextEdit(self.config.get("PROMPT", "system_prompt"))
        self.sys_prompt.setMaximumHeight(120)
        prompt_lay.addWidget(self.sys_prompt)

        prompt_lay.addWidget(
            QLabel("User Prompt  (use {{placeholder}} for variables):")
        )
        self.usr_prompt = QPlainTextEdit(self.config.get("PROMPT", "user_prompt"))
        self.usr_prompt.setMaximumHeight(120)
        prompt_lay.addWidget(self.usr_prompt)

        ph_hint = QLabel(
            "Available placeholders: {{branch_name}}, {{repo_name}}, "
            "{{repo_path}}, {{date}}, {{files_changed}}, {{git_diff}}"
        )
        ph_hint.setWordWrap(True)
        ph_hint.setStyleSheet("color: gray; font-size: 11px;")
        prompt_lay.addWidget(ph_hint)

        lay.addWidget(prompt_grp, stretch=1)
        return page

    # ── Code Review tab ──────────────────────────────────────────────

    def _build_review_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addWidget(QLabel("Code Review System Prompt:"))
        self.review_prompt = QPlainTextEdit(
            self.config.get("CODE_REVIEW", "system_prompt")
        )
        lay.addWidget(self.review_prompt, stretch=1)
        hint = QLabel(
            "Used by the AI Code Review button.  Reviews staged, unstaged, "
            "and untracked changes from the selected repository."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        lay.addWidget(hint)
        return page

    # ── Root Cause tab ───────────────────────────────────────────────

    def _build_root_cause_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addWidget(QLabel("Root Cause Summary System Prompt:"))
        self.root_cause_prompt = QPlainTextEdit(
            self.config.get("ROOT_CAUSE", "system_prompt")
        )
        lay.addWidget(self.root_cause_prompt, stretch=1)
        hint = QLabel(
            "Used by the Root Cause Summary action in the Generate Actions menu.  "
            "Analyses the staged changes and produces a root cause summary."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        lay.addWidget(hint)
        return page

    # ── GUI tab ──────────────────────────────────────────────────────

    def _build_gui_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        self.on_top_cb = QCheckBox("Always on top")
        self.on_top_cb.setChecked(self.config.always_on_top)
        lay.addWidget(self.on_top_cb)
        lay.addStretch()
        return page

    # ── Provider visibility ──────────────────────────────────────────

    def _on_provider_changed(self):
        provider = self.provider_combo.currentText()

        for key, widget in self._key_rows.items():
            widget.setVisible(key == provider)

        # Package status
        avail_map = {
            "openai": OPENAI_AVAILABLE,
            "anthropic": ANTHROPIC_AVAILABLE,
            "gemini": GEMINI_AVAILABLE,
            "ollama": OLLAMA_AVAILABLE,
        }
        name_map = {
            "openai": "OpenAI",
            "anthropic": "Anthropic",
            "gemini": "Google Gemini",
            "ollama": "Ollama",
        }
        if avail_map.get(provider, True):
            self.pkg_status_label.setText("")
            self.pkg_install_btn.hide()
        else:
            self.pkg_status_label.setText(
                f"{name_map[provider]} package not installed"
            )
            self.pkg_install_btn.show()

    # ── Package installation ─────────────────────────────────────────

    def _install_missing(self):
        provider = self.provider_combo.currentText()
        pip_map = {
            "openai": ("openai", "OpenAI"),
            "anthropic": ("anthropic", "Anthropic Claude"),
            "gemini": ("google-genai", "Google Gemini"),
            "ollama": ("ollama", "Ollama"),
        }
        pip_name, display_name = pip_map.get(provider, (None, None))
        if not pip_name:
            return

        result = QMessageBox.question(
            self,
            "Missing Package",
            f"The {display_name} package is required but not installed.\n\n"
            "Would you like to install it now?",
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        progress = QProgressDialog(
            f"Installing {display_name}...", None, 0, 0, self
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        def work():
            AIService.install_package(pip_name)

        def ok(_):
            progress.close()
            QMessageBox.information(
                self,
                "Installation Complete",
                "Package installed successfully.\n"
                "Please restart the application.",
            )
            self.reject()

        def fail(msg):
            progress.close()
            QMessageBox.critical(
                self,
                "Installation Failed",
                f"Failed to install {display_name}:\n{msg}",
            )

        thread = WorkerThread(work, parent=self)
        thread.result_ready.connect(ok)
        thread.error_occurred.connect(fail)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        self._active_thread = thread

    # ── Save ─────────────────────────────────────────────────────────

    def _save(self):
        self.config.set("API", "provider", self.provider_combo.currentText())
        self.config.set("API", "openai_api_key", self.openai_key.text())
        self.config.set("API", "anthropic_api_key", self.anthropic_key.text())
        self.config.set("API", "gemini_api_key", self.gemini_key.text())
        self.config.set("API", "ollama_host", self.ollama_host.text())
        self.config.set("API", "model", self.model_edit.text())
        self.config.set(
            "PROMPT", "system_prompt", self.sys_prompt.toPlainText().strip()
        )
        self.config.set(
            "PROMPT", "user_prompt", self.usr_prompt.toPlainText().strip()
        )
        self.config.set(
            "CODE_REVIEW",
            "system_prompt",
            self.review_prompt.toPlainText().strip(),
        )
        self.config.set(
            "ROOT_CAUSE",
            "system_prompt",
            self.root_cause_prompt.toPlainText().strip(),
        )
        self.config.set("GUI", "always_on_top", str(self.on_top_cb.isChecked()))
        self.config.save_config()

        QMessageBox.information(
            self,
            "Success",
            "Configuration saved successfully!\n"
            "Restart the application for GUI changes to take effect.",
        )
        self.accept()
