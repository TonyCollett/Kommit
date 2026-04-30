# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-05-01

### Added
- Project renamed to **Kommit**
- Complete rewrite using PySide6 desktop GUI (replacing the previous single-file implementation)
- Modular codebase with `core/` and `ui/` packages
- Ollama provider support for local AI models
- AI Code Review — analyses all uncommitted changes (staged, unstaged, and untracked) and presents findings in a dialog
- Root Cause Summary — generates a root cause analysis from staged changes or a branch diff comparison
- Changes dialog with syntax-highlighted diff preview, multi-file selection, and stage/unstage/discard actions
- Branch panel with local and remote branch tree, double-click to switch branches
- Raise Pull Request action that opens the GitHub compare page for the current branch
- Open in Terminal and Open in Explorer repository actions
- Repository auto-detection across common directories
- Automatic package installation for missing AI provider SDKs
- Always-on-top window option
- Configurable system and user prompts with `{{placeholder}}` support
- Separate configuration tabs for API settings, Code Review prompt, Root Cause prompt, and GUI settings
- Background threading for all AI and git operations to keep the UI responsive
- Auto-refresh on application focus regain

### Changed
- Project renamed from GitCommitAI to Kommit
- Entry point changed from `git_commit_ai.py` to `main.py`
- Configuration file renamed from `git_commit_ai_config.ini` to `kommit_config.ini`
- Minimum Python version raised to 3.9+

### Removed
- Single-file architecture (old implementation preserved in `old/` for reference)

## [1.0.0] - 2024-01-08

### Added
- Initial release (as GitCommitAI)
- Support for OpenAI, Anthropic Claude, and Google Gemini APIs
- GUI interface for commit message generation
- Multi-repository management
- Configurable prompts and settings
