# Contributing to GitCommitAI

Thank you for your interest in contributing to GitCommitAI! We welcome contributions from the community.

## How to Contribute

1. **Fork the repository** and create your branch from `main`.
2. **Make your changes** following our coding standards.
3. **Test your changes** to ensure they work correctly.
4. **Submit a pull request** with a clear description of your changes.

## Project Structure

```
main.py              # Application entry point
core/
  config_manager.py  # INI-based configuration management
  ai_service.py      # AI provider integration (OpenAI, Anthropic, Gemini, Ollama)
  git_service.py     # Git CLI operations
  models.py          # Data models (GitInfo, ReviewInfo, StatusEntry)
ui/
  main_window.py     # Primary application window
  config_dialog.py   # Configuration dialog with tabs
  changes_dialog.py  # Diff viewer and staging dialog
  repo_manager.py    # Repository management dialog
  widgets/
    diff_viewer.py   # Syntax-highlighted diff viewer widget
    text_dialog.py   # Reusable text/markdown display dialog
    worker.py        # Background thread helper
```

## Coding Standards

- Follow PEP 8 style guidelines (enforced via [Ruff](https://docs.astral.sh/ruff/) with a line length of 88).
- Use descriptive variable and function names.
- Add docstrings to modules, classes, and public methods.
- Add comments for complex logic.
- Ensure code is compatible with Python 3.9+.

## Development Setup

```bash
# Install all dependencies including dev tools
pip install -e ".[dev]"

# Run the linter
ruff check .

# Run the formatter
ruff format .
```

## Reporting Issues

If you find a bug or have a feature request:
- Check existing issues first.
- Open a new issue with a clear title and description.
- Include steps to reproduce for bugs.

## Code of Conduct

Please follow our [Code of Conduct](CODE_OF_CONDUCT.md) in all interactions.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
