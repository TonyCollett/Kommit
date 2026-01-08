# GitCommitAI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

An AI-powered Git Commit Message Generator with Multi-Repository Support that works with OpenAI, Anthropic Claude, and Google Gemini APIs.

**Note:** This tool is designed to be used alongside other Git clients or the Git CLI. It does not replace a full Git client but provides enhanced commit message generation capabilities.

## Features

- Generate meaningful commit messages based on staged changes
- Support for multiple AI providers (OpenAI, Anthropic Claude, Google Gemini)
- Multi-repository management
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
3. Configure your API keys in the Configuration dialog
4. Click "Generate Commit Message" to analyze staged changes and create a commit message
5. Use "Copy to Clipboard" to copy the message for use in your terminal
6. Or click "Open in Terminal" to open a terminal in your repository directory

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
