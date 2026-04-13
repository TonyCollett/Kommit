# GitCommitAI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

An AI-powered Git Commit Message Generator with Multi-Repository Support that works with OpenAI, Anthropic Claude, and Google Gemini APIs.

**Note:** This tool is designed to be used alongside other Git clients or the Git CLI. It does not replace a full Git client but provides enhanced commit message generation capabilities.

## Features

- Generate meaningful commit messages based on staged changes
- Support for multiple AI providers (OpenAI, Anthropic Claude, Google Gemini)
- Multi-repository management
- Built-in changes dialog with staged/unstaged diff preview
- Commit action button for commit, commit and push, or commit and sync workflows
- Configurable prompts
- User-friendly GUI interface

## Requirements

- Python 3.8+
- Git

## Installation

1. Clone or download the repository
2. Install the required packages:

```bash
pip install -r requirements.txt
```

Or you can install individual packages as needed:

```bash
# For OpenAI support
pip install openai

# For Anthropic Claude support
pip install anthropic

# For Google Gemini support
pip install google-genai
```

You can also install packages directly from the app's configuration interface.

## Usage

Run the application:

```bash
python git_commit_ai.py
```

1. Add your repositories via the "Manage Repos" button
2. Select a repository from the dropdown
3. Click "Changes" to open the diff viewer and inspect changed files
4. In the diff viewer, select one or more files to preview their diffs, then use "Stage Selected", "Unstage Selected", or "Discard Unstaged" as needed
5. Configure your API keys in the Configuration dialog
6. Click "Generate Commit Message" to analyze the currently staged changes and create a commit message
7. Use the "Commit Staged Files" button to run the commit directly from the app, or open its dropdown to choose "Commit and Push" or "Commit and Sync"
8. Use "Copy to Clipboard" to copy the message for use in your terminal
9. Or click "Open in Terminal" to open a terminal in your repository directory

### Diff Viewer

- Open the viewer with the "Changes" button beside the selected repository
- Review staged, unstaged, and new files in one list
- Select multiple files with Ctrl or Shift to preview combined diffs
- Use the viewer to prepare the exact staged set before generating a commit message

### Commit Button

- The commit action button stays disabled until a commit message has been generated
- Click the main button to commit the current staged files with the generated message
- Use the dropdown arrow to switch to "Commit and Push" or "Commit and Sync" when you want the app to continue with remote operations after committing

## Configuration

Click the "Configure" button to set up:

- AI provider and API keys
- Model selection
- System and user prompts
- UI settings

## Troubleshooting

- Ensure your API keys are correctly configured
- Check that required packages are installed
- Make sure you have staged changes in your Git repository

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
