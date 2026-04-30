"""AI provider integration for commit message and code review generation."""

import re
import subprocess
import sys
from typing import List, Optional, Tuple

from core.config_manager import ConfigManager
from core.models import GitInfo, ReviewInfo


def _is_package_installed(package_name: str) -> bool:
    """Check if a Python package is importable."""
    try:
        if package_name == "google.genai":
            try:
                __import__("google")
            except ImportError:
                return False
        __import__(package_name)
        return True
    except (ImportError, ModuleNotFoundError):
        return False


# Module-level availability flags
OPENAI_AVAILABLE = _is_package_installed("openai")
ANTHROPIC_AVAILABLE = _is_package_installed("anthropic")
GEMINI_AVAILABLE = _is_package_installed("google.genai")
OLLAMA_AVAILABLE = _is_package_installed("ollama")

# Maps provider key → (pip package name, display name, available flag)
PROVIDER_PACKAGES = {
    "openai": ("openai", "OpenAI", OPENAI_AVAILABLE),
    "anthropic": ("anthropic", "Anthropic Claude", ANTHROPIC_AVAILABLE),
    "gemini": ("google-genai", "Google Gemini", GEMINI_AVAILABLE),
    "ollama": ("ollama", "Ollama", OLLAMA_AVAILABLE),
}


def provider_available(provider: str) -> bool:
    """Return whether the SDK for *provider* is installed."""
    info = PROVIDER_PACKAGES.get(provider)
    return info[2] if info else False


class AIService:
    """Handles AI-powered text generation across multiple providers."""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.openai_client = None
        self.anthropic_client = None
        self.gemini_client = None
        self.ollama_client = None
        self.setup_clients()

    # ── Client initialisation ────────────────────────────────────────

    def setup_clients(self):
        """(Re)initialise API clients based on current configuration."""
        self.openai_client = None
        self.anthropic_client = None
        self.gemini_client = None
        self.ollama_client = None

        provider = self.config.provider

        if provider == "openai" and OPENAI_AVAILABLE:
            import openai

            api_key = self.config.get("API", "openai_api_key")
            if api_key:
                self.openai_client = openai.OpenAI(api_key=api_key)

        elif provider == "anthropic" and ANTHROPIC_AVAILABLE:
            from anthropic import Anthropic

            api_key = self.config.get("API", "anthropic_api_key")
            if api_key:
                self.anthropic_client = Anthropic(api_key=api_key)

        elif provider == "gemini" and GEMINI_AVAILABLE:
            import google.genai as genai

            api_key = self.config.get("API", "gemini_api_key")
            if api_key:
                self.gemini_client = genai.Client(api_key=api_key)

        elif provider == "ollama" and OLLAMA_AVAILABLE:
            from ollama import Client as OllamaClient

            host = self.config.get("API", "ollama_host", fallback="http://localhost:11434")
            self.ollama_client = OllamaClient(host=host)

    # ── Status helpers ───────────────────────────────────────────────

    def get_missing_packages(self) -> List[Tuple[str, str]]:
        """Return ``[(pip_name, display_name)]`` for the missing provider package."""
        info = PROVIDER_PACKAGES.get(self.config.provider)
        if info and not info[2]:
            return [(info[0], info[1])]
        return []

    def get_provider_status(self) -> Optional[str]:
        """Return a warning string if the current provider SDK is missing."""
        missing = self.get_missing_packages()
        if missing:
            return f"Warning: {missing[0][1]} package not installed"
        return None

    @staticmethod
    def install_package(pip_name: str):
        """Install a Python package via pip."""
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])

    # ── Placeholder replacement ──────────────────────────────────────

    @staticmethod
    def replace_placeholders(text: str, info: dict) -> str:
        """Replace ``{{key}}`` placeholders in *text* with values from *info*."""

        def _replace(match):
            key = match.group(1)
            return str(info.get(key, f"{{{{ {key} }}}}"))

        return re.sub(r"\{\{(\w+)\}\}", _replace, text)

    # ── Generation entry points ──────────────────────────────────────

    def generate_commit_message(self, git_info: GitInfo) -> str:
        system_prompt = self.config.get("PROMPT", "system_prompt")
        user_prompt = self.replace_placeholders(
            self.config.get("PROMPT", "user_prompt"), git_info.__dict__
        )
        return self._generate(system_prompt, user_prompt, max_tokens=200)

    def generate_code_review(self, review_info: ReviewInfo) -> str:
        system_prompt = self.config.get("CODE_REVIEW", "system_prompt")
        user_prompt = (
            "Review the following uncommitted git changes and provide an actionable code review.\n\n"
            f"Repository: {review_info.repo_name}\n"
            f"Branch: {review_info.branch_name}\n"
            f"Date: {review_info.date}\n"
            f"Changed files: {review_info.files_changed}\n\n"
            "Response requirements:\n"
            "1. Start with a one-line overall assessment.\n"
            "2. List findings in priority order with file references when possible.\n"
            "3. Explain the impact of each issue briefly.\n"
            "4. If no significant issues are found, explicitly say that.\n\n"
            f"Git changes:\n{review_info.git_diff}"
        )
        return self._generate(system_prompt, user_prompt, max_tokens=7000)

    # ── Internal dispatch ────────────────────────────────────────────

    def _generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 200) -> str:
        provider = self.config.provider

        try:
            if provider == "openai" and self.openai_client:
                return self._generate_openai(system_prompt, user_prompt, max_tokens)
            elif provider == "anthropic" and self.anthropic_client:
                return self._generate_anthropic(system_prompt, user_prompt, max_tokens)
            elif provider == "gemini" and self.gemini_client:
                return self._generate_gemini(system_prompt, user_prompt, max_tokens)
            elif provider == "ollama" and self.ollama_client:
                return self._generate_ollama(system_prompt, user_prompt, max_tokens)
            else:
                raise Exception(
                    f"Provider '{provider}' not available or not configured"
                )
        except Exception as e:
            raise Exception(f"Error generating AI response: {e}")

    # ── Provider implementations ─────────────────────────────────────

    def _generate_openai(self, system_prompt, user_prompt, max_tokens):
        model = self.config.get("API", "model", fallback="gpt-3.5-turbo")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
            )
        except Exception as e:
            error_str = str(e)
            if "max_tokens" in error_str and "max_completion_tokens" in error_str:
                try:
                    response = self.openai_client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_completion_tokens=max_tokens,
                        temperature=0.7,
                    )
                except Exception as e2:
                    if "temperature" in str(e2):
                        response = self.openai_client.chat.completions.create(
                            model=model,
                            messages=messages,
                            max_completion_tokens=max_tokens,
                            temperature=1,
                        )
                    else:
                        raise e2
            elif "temperature" in error_str:
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=1,
                )
            else:
                raise
        return response.choices[0].message.content.strip()

    def _generate_anthropic(self, system_prompt, user_prompt, max_tokens):
        model = self.config.get("API", "model", fallback="claude-3-haiku-20240307")
        response = self.anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text.strip()

    def _generate_gemini(self, system_prompt, user_prompt, max_tokens):
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        model_name = self.config.get("API", "model", fallback="gemini-1.5-flash")
        response = self.gemini_client.models.generate_content(
            model=model_name, contents=full_prompt
        )
        return response.text.strip()

    def _generate_ollama(self, system_prompt, user_prompt, max_tokens):
        model = self.config.get("API", "model", fallback="llama3")
        try:
            response = self.ollama_client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response["message"]["content"].strip()
        except Exception as e:
            raise Exception(f"Ollama generation failed: {e}")
