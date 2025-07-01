# GitCommitAI

An AI-powered Git Commit Message Generator with Multi-Repository Support that works with OpenAI, Anthropic Claude, and Google Gemini APIs.

## Features

- Generate meaningful commit messages based on staged changes
- Support for multiple AI providers (OpenAI, Anthropic Claude, Google Gemini)
- Multi-repository management
- Configurable prompts
- User-friendly GUI interface

## Requirements

- Python 3.6+
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
pip install google-generativeai
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

## License

MIT
