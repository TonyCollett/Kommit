#!/usr/bin/env python3
"""
AI-powered Git Commit Message Generator with Multi-Repository Support
Supports OpenAI, Anthropic Claude, and Google Gemini APIs
"""

import subprocess
import json
import os
import re
import shutil
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
from datetime import datetime
from pathlib import Path
import configparser
import sys
import importlib.util
import platform


# Check API client packages
def is_package_installed(package_name):
    """Check if a Python package is installed"""
    try:
        pkg_to_check = package_name
        if package_name == "google.genai":
            try:
                __import__("google")
            except ImportError:
                return False

        # Try to import the package
        __import__(pkg_to_check)
        return True
    except (ImportError, ModuleNotFoundError):
        return False


OPENAI_AVAILABLE = is_package_installed("openai")
ANTHROPIC_AVAILABLE = is_package_installed("anthropic")
GEMINI_AVAILABLE = is_package_installed("google.genai")
OLLAMA_AVAILABLE = is_package_installed("ollama")

# Import available clients
if OPENAI_AVAILABLE:
    import openai

if ANTHROPIC_AVAILABLE:
    from anthropic import Anthropic

if GEMINI_AVAILABLE:
    import google.genai as genai

if OLLAMA_AVAILABLE:
    from ollama import Client as OllamaClient


class GitCommitAI:
    def __init__(self):
        self.config_file = Path(__file__).parent / "git_commit_ai_config.ini"
        self.config = configparser.ConfigParser()
        self.current_repo_path = None
        self.restart_needed = False
        self.commit_action = "commit"
        self.changes_dialog = None
        self.load_config()

        # Initialize API clients
        self.openai_client = None
        self.anthropic_client = None
        self.gemini_client = None
        self.ollama_client = None

        # Create GUI before checking packages (needed for message boxes)
        self.setup_gui()

        # Check required packages based on configured provider
        self.check_required_packages()
        self.setup_api_clients()
        self.refresh_repositories()

    def load_config(self):
        """Load configuration from file or create default"""
        default_config = {
            "API": {
                "provider": "openai",  # openai, anthropic, gemini, or ollama
                "openai_api_key": "",
                "anthropic_api_key": "",
                "gemini_api_key": "",
                "ollama_host": "http://localhost:11434",
                "model": "gpt-4.1-mini",  # or claude-3-sonnet-20240229, gemini-pro, llama3
            },
            "REPOSITORIES": {
                "paths": "",  # JSON string of repository paths
                "current_repo": "",  # Currently selected repository path
            },
            "PROMPT": {
                "system_prompt": """You are a helpful assistant that generates concise, clear git commit messages. 
Follow conventional commit format when appropriate (feat:, fix:, docs:, etc.).
Be specific about what changed and why.""",
                "user_prompt": """Based on the following git diff and context, generate a commit message:

Repository: {{repo_name}}
Branch: {{branch_name}}
Date: {{date}}
Files changed: {{files_changed}}

Git diff:
{{git_diff}}

Generate a commit message that is:
1. Clear and concise
2. Explains what changed and why
3. Uses conventional commit format if appropriate
4. Is under 72 characters for the first line""",
            },
            "GUI": {"always_on_top": "true"},
        }

        if self.config_file.exists():
            self.config.read(self.config_file)
            # Add missing sections/keys
            for section, options in default_config.items():
                if not self.config.has_section(section):
                    self.config.add_section(section)
                for key, value in options.items():
                    if not self.config.has_option(section, key):
                        self.config.set(section, key, value)
        else:
            for section, options in default_config.items():
                self.config.add_section(section)
                for key, value in options.items():
                    self.config.set(section, key, value)

        self.save_config()

    def save_config(self):
        """Save configuration to file"""
        with open(self.config_file, "w") as f:
            self.config.write(f)

    def get_repository_paths(self):
        """Get list of repository paths from config"""
        paths_json = self.config.get("REPOSITORIES", "paths", fallback="[]")
        try:
            return json.loads(paths_json) if paths_json else []
        except json.JSONDecodeError:
            return []

    def save_repository_paths(self, paths):
        """Save repository paths to config"""
        self.config.set("REPOSITORIES", "paths", json.dumps(paths))
        self.save_config()

    def is_valid_git_repo(self, path):
        """Check if path contains a valid git repository"""
        try:
            if not os.path.exists(path):
                return False
            result = subprocess.run(
                ["git", "status"], cwd=path, capture_output=True, text=True
            )
            return result.returncode == 0
        except:
            return False

    def validate_repositories(self, paths):
        """Validate and return only valid git repositories"""
        valid_repos = []
        for path in paths:
            if self.is_valid_git_repo(path):
                valid_repos.append(path)
        return valid_repos

    def check_required_packages(self):
        """Check if required packages are installed based on selected provider and offer installation"""
        provider = self.config.get("API", "provider")
        missing_packages = []

        if provider == "openai" and not OPENAI_AVAILABLE:
            missing_packages.append(("openai", "OpenAI"))
        elif provider == "anthropic" and not ANTHROPIC_AVAILABLE:
            missing_packages.append(("anthropic", "Anthropic Claude"))
        elif provider == "gemini" and not GEMINI_AVAILABLE:
            missing_packages.append(("google-generativeai", "Google Gemini"))
        elif provider == "ollama" and not OLLAMA_AVAILABLE:
            missing_packages.append(("ollama", "Ollama"))

        if missing_packages:
            self.offer_package_installation(missing_packages)

    def offer_package_installation(self, missing_packages):
        """Offer to install missing packages"""
        package_list = ", ".join([f"{name}" for pkg, name in missing_packages])
        message = f"The following packages are required but not installed: {package_list}\n\nWould you like to install them now?"

        if messagebox.askyesno("Missing Packages", message):
            self.install_packages(missing_packages)

    def install_packages(self, packages):
        """Install Python packages"""
        try:
            # Create a progress window
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Installing Packages")
            progress_window.geometry("400x150")
            progress_window.transient(self.root)
            progress_window.grab_set()

            # Add progress information
            info_label = ttk.Label(
                progress_window,
                text="Installing required packages. This may take a moment...",
            )
            info_label.pack(pady=(20, 10))

            progress_bar = ttk.Progressbar(progress_window, mode="indeterminate")
            progress_bar.pack(fill=tk.X, padx=20, pady=10)
            progress_bar.start()

            status_label = ttk.Label(progress_window, text="")
            status_label.pack(pady=10)

            # Update function for background thread
            def update_status(text):
                status_label.config(text=text)
                progress_window.update_idletasks()

            def install_thread():
                success = True
                failed_packages = []

                for pkg_name, display_name in packages:
                    try:
                        update_status(f"Installing {display_name} package...")
                        subprocess.check_call(
                            [sys.executable, "-m", "pip", "install", pkg_name]
                        )
                    except Exception as e:
                        success = False
                        failed_packages.append(display_name)

                # Close progress window
                progress_window.after(500, progress_window.destroy)

                # Show result
                if success:
                    messagebox.showinfo(
                        "Installation Complete",
                        "Packages installed successfully.\nPlease restart the application to use the new packages.",
                    )
                else:
                    failed_list = ", ".join(failed_packages)
                    self.show_error_dialog(
                        "Installation Failed",
                        f"Failed to install: {failed_list}\n\nPlease install manually using pip.",
                    )

                # Set restart flag
                self.restart_needed = True

            # Start installation in background thread
            self.restart_needed = False
            threading.Thread(target=install_thread, daemon=True).start()

        except Exception as e:
            self.show_error_dialog("Error", f"Failed to install packages: {str(e)}")

    def setup_api_clients(self):
        """Initialize API clients based on configuration"""
        provider = self.config.get("API", "provider")

        if provider == "openai" and OPENAI_AVAILABLE:
            api_key = self.config.get("API", "openai_api_key")
            if api_key:
                self.openai_client = openai.OpenAI(api_key=api_key)

        elif provider == "anthropic" and ANTHROPIC_AVAILABLE:
            api_key = self.config.get("API", "anthropic_api_key")
            if api_key:
                self.anthropic_client = Anthropic(api_key=api_key)

        elif provider == "gemini" and GEMINI_AVAILABLE:
            api_key = self.config.get("API", "gemini_api_key")
            if api_key:
                self.gemini_client = genai.Client(api_key=api_key)

        elif provider == "ollama" and OLLAMA_AVAILABLE:
            host = self.config.get(
                "API", "ollama_host", fallback="http://localhost:11434"
            )
            self.ollama_client = OllamaClient(host=host)

    def get_git_info(self):
        """Get git repository information"""
        if not self.current_repo_path:
            raise Exception("No repository selected")

        if not self.is_valid_git_repo(self.current_repo_path):
            raise Exception(f"Invalid git repository: {self.current_repo_path}")

        try:
            # Get current branch
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.current_repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            branch_name = branch_result.stdout.strip()

            # Get repository name
            repo_result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.current_repo_path,
                capture_output=True,
                text=True,
            )
            repo_url = repo_result.stdout.strip() if repo_result.returncode == 0 else ""
            repo_name = (
                Path(repo_url).stem.replace(".git", "")
                if repo_url
                else Path(self.current_repo_path).name
            )

            # Get staged files
            staged_result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=self.current_repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            staged_files = (
                staged_result.stdout.strip().split("\n")
                if staged_result.stdout.strip()
                else []
            )

            # Get diff of staged files
            diff_result = subprocess.run(
                ["git", "diff", "--cached"],
                cwd=self.current_repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            git_diff = diff_result.stdout

            # Get repository status for additional context
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.current_repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            return {
                "branch_name": branch_name,
                "repo_name": repo_name,
                "repo_path": self.current_repo_path,
                "staged_files": staged_files,
                "git_diff": git_diff,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "files_changed": ", ".join(staged_files),
            }

        except subprocess.CalledProcessError as e:
            raise Exception(f"Git command failed: {e}")
        except Exception as e:
            raise Exception(f"Error getting git info: {e}")

    def replace_placeholders(self, text, git_info):
        """Replace placeholder values in text"""

        def replace_func(match):
            key = match.group(1)
            return str(git_info.get(key, f"{{{{ {key} }}}}"))

        return re.sub(r"\{\{(\w+)\}\}", replace_func, text)

    def generate_commit_message(self, git_info):
        """Generate commit message using configured AI provider"""
        provider = self.config.get("API", "provider")
        system_prompt = self.config.get("PROMPT", "system_prompt")
        user_prompt = self.replace_placeholders(
            self.config.get("PROMPT", "user_prompt"), git_info
        )

        try:
            if provider == "openai" and self.openai_client:
                return self.generate_openai(system_prompt, user_prompt)
            elif provider == "anthropic" and self.anthropic_client:
                return self.generate_anthropic(system_prompt, user_prompt)
            elif provider == "gemini" and self.gemini_client:
                return self.generate_gemini(system_prompt, user_prompt)
            elif provider == "ollama" and self.ollama_client:
                return self.generate_ollama(system_prompt, user_prompt)
            else:
                raise Exception(
                    f"Provider '{provider}' not available or not configured"
                )

        except Exception as e:
            raise Exception(f"Error generating commit message: {e}")

    def generate_openai(self, system_prompt, user_prompt):
        """Generate using OpenAI API"""
        if not OPENAI_AVAILABLE:
            raise Exception("OpenAI package not installed. Please install it first.")

        model = self.config.get("API", "model", fallback="gpt-3.5-turbo")
        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=200,
                temperature=0.7,
            )
        except Exception as e:
            error_str = str(e)
            if "max_tokens" in error_str and "max_completion_tokens" in error_str:
                # Retry with max_completion_tokens for newer models
                try:
                    response = self.openai_client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        max_completion_tokens=200,
                        temperature=0.7,
                    )
                except Exception as e2:
                    error_str2 = str(e2)
                    if "temperature" in error_str2:
                        # Retry with temperature=1
                        response = self.openai_client.chat.completions.create(
                            model=model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            max_completion_tokens=200,
                            temperature=1,
                        )
                    else:
                        raise e2
            elif "temperature" in error_str:
                # Retry with temperature=1
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=200,
                    temperature=1,
                )
            else:
                raise e
        return response.choices[0].message.content.strip()

    def generate_anthropic(self, system_prompt, user_prompt):
        """Generate using Anthropic API"""
        if not ANTHROPIC_AVAILABLE:
            raise Exception("Anthropic package not installed. Please install it first.")

        model = self.config.get("API", "model", fallback="claude-3-haiku-20240307")
        response = self.anthropic_client.messages.create(
            model=model,
            max_tokens=200,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text.strip()

    def generate_gemini(self, system_prompt, user_prompt):
        """Generate using Gemini API"""
        if not GEMINI_AVAILABLE:
            raise Exception(
                "Google Generative AI package not installed. Please install it first."
            )

        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        model_name = self.config.get("API", "model", fallback="gemini-1.5-flash")
        response = self.gemini_client.models.generate_content(
            model=model_name, contents=full_prompt
        )
        return response.text.strip()

    def generate_ollama(self, system_prompt, user_prompt):
        """Generate using Ollama API"""
        if not OLLAMA_AVAILABLE:
            raise Exception("Ollama package not installed. Please install it first.")

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

    def setup_gui(self):
        """Setup the GUI window"""
        self.root = tk.Tk()
        self.root.title("AI Git Commit Message Generator")
        self.root.geometry("700x430")  # Fixed window size
        self.root.resizable(False, False)  # Prevent resizing

        if self.config.getboolean("GUI", "always_on_top"):
            self.root.attributes("-topmost", True)

        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

        # Repository selection frame
        repo_frame = ttk.LabelFrame(
            main_frame, text="Repository Selection", padding="5"
        )
        repo_frame.grid(
            row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10)
        )
        repo_frame.columnconfigure(1, weight=1)

        ttk.Label(repo_frame, text="Repository:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5)
        )

        self.repo_var = tk.StringVar()
        self.repo_combo = ttk.Combobox(
            repo_frame, textvariable=self.repo_var, state="readonly"
        )
        self.repo_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        self.repo_combo.bind("<<ComboboxSelected>>", self.on_repo_selected)

        ttk.Button(
            repo_frame, text="Manage Repos", command=self.manage_repositories
        ).grid(row=0, column=2, padx=(5, 0))

        # Repository info frame
        info_frame = ttk.Frame(main_frame)
        info_frame.grid(
            row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10)
        )
        info_frame.columnconfigure(1, weight=1)

        # Create a frame for repo info with refresh button
        repo_info_subframe = ttk.Frame(info_frame)
        repo_info_subframe.grid(row=0, column=0, sticky=(tk.W, tk.E))

        self.repo_info_label = ttk.Label(
            repo_info_subframe, text="No repository selected", foreground="gray"
        )
        self.repo_info_label.pack(side=tk.LEFT)

        self.changes_button = ttk.Button(
            repo_info_subframe, text="Changes", command=self.open_changes_dialog
        )
        self.changes_button.pack(side=tk.LEFT, padx=(5, 0))

        # Add refresh button with "⟳" as the refresh symbol
        self.refresh_button = ttk.Button(
            repo_info_subframe, text="⟳", width=2, command=self.refresh_repo_status
        )
        self.refresh_button.pack(side=tk.LEFT, padx=(5, 0))

        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready")
        self.status_label.grid(
            row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10)
        )

        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(
            row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10)
        )

        ttk.Button(
            buttons_frame, text="Generate Commit Message", command=self.generate_clicked
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            buttons_frame, text="Configure", command=self.configure_clicked
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            buttons_frame, text="Copy to Clipboard", command=self.copy_clicked
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.commit_action_button = ttk.Button(
            buttons_frame,
            text="Commit Staged Files ▼",
            command=self.show_commit_actions_menu,
            state=tk.DISABLED,
        )
        self.commit_action_button.pack(side=tk.LEFT, padx=(0, 5))

        self.commit_actions_menu = tk.Menu(buttons_frame, tearoff=0)
        self.commit_actions_menu.add_command(
            label="Commit Staged Files",
            command=lambda: self.run_commit_action("commit"),
        )
        self.commit_actions_menu.add_command(
            label="Commit and Push",
            command=lambda: self.run_commit_action("push"),
        )
        self.commit_actions_menu.add_command(
            label="Commit and Sync",
            command=lambda: self.run_commit_action("sync"),
        )

        # Create dropdown menu button for terminal/explorer actions
        self.repo_actions_button = ttk.Button(
            buttons_frame,
            text="Repository Actions ▼",
            command=self.show_repo_actions_menu,
        )
        self.repo_actions_button.pack(side=tk.LEFT)

        # Create the dropdown menu (but don't show it yet)
        self.repo_actions_menu = tk.Menu(buttons_frame, tearoff=0)
        self.repo_actions_menu.add_command(
            label="Open in Terminal", command=self.open_terminal
        )
        self.repo_actions_menu.add_command(
            label="Open in Explorer", command=self.open_in_explorer
        )

        # Text area for commit message
        self.text_area = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=15)
        self.text_area.grid(
            row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S)
        )

    def refresh_repositories(self):
        """Refresh the repository dropdown"""
        paths = self.get_repository_paths()
        valid_paths = self.validate_repositories(paths)

        # Update dropdown
        self.repo_combo["values"] = [f"{Path(p).name} ({p})" for p in valid_paths]

        # Set current selection
        current_repo = self.config.get("REPOSITORIES", "current_repo", fallback="")
        if current_repo and current_repo in valid_paths:
            self.current_repo_path = current_repo
            display_name = f"{Path(current_repo).name} ({current_repo})"
            self.repo_var.set(display_name)
            self.update_repo_info()
        elif valid_paths:
            # Select first valid repo if current is not valid
            self.current_repo_path = valid_paths[0]
            display_name = f"{Path(valid_paths[0]).name} ({valid_paths[0]})"
            self.repo_var.set(display_name)
            self.config.set("REPOSITORIES", "current_repo", valid_paths[0])
            self.save_config()
            self.update_repo_info()
        else:
            self.current_repo_path = None
            self.repo_var.set("")
            self.update_repo_info()

        # Update API status
        self.update_api_status()

    def on_repo_selected(self, event=None):
        """Handle repository selection"""
        selection = self.repo_var.get()
        if selection:
            # Extract path from "Name (path)" format
            path = selection[selection.rfind("(") + 1 : -1]
            self.current_repo_path = path
            self.config.set("REPOSITORIES", "current_repo", path)
            self.save_config()
            self.update_repo_info()
            if self.changes_dialog and self.changes_dialog.window.winfo_exists():
                self.changes_dialog.refresh_contents()
            self.reset_commit_action_state()

    def update_repo_info(self):
        """Update repository information display"""
        if not self.current_repo_path:
            self.repo_info_label.config(
                text="No repository selected", foreground="gray"
            )
            self.changes_button.config(state=tk.DISABLED)
            self.refresh_button.config(state=tk.DISABLED)
            return

        # Check if the repository path still exists
        if not os.path.exists(self.current_repo_path):
            self.repo_info_label.config(text="Repository not found", foreground="red")
            self.changes_button.config(state=tk.DISABLED)
            self.refresh_button.config(state=tk.DISABLED)
            return

        try:
            # Get branch info
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.current_repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            branch = branch_result.stdout.strip()

            status_entries = self.get_repo_status_entries()
            staged_count = sum(1 for entry in status_entries if entry["has_staged"])
            unstaged_count = sum(1 for entry in status_entries if entry["has_unstaged"])

            info_text = f"Branch: {branch} | Staged: {staged_count} | Unstaged: {unstaged_count}"
            self.repo_info_label.config(text=info_text, foreground="black")
            self.changes_button.config(state=tk.NORMAL)
            self.refresh_button.config(state=tk.NORMAL)

        except Exception as e:
            self.repo_info_label.config(
                text=f"Error reading repository: {str(e)}", foreground="red"
            )
            self.changes_button.config(state=tk.DISABLED)
            self.refresh_button.config(state=tk.DISABLED)

    def update_api_status(self):
        """Update the API status in the UI"""
        provider = self.config.get("API", "provider")

        if provider == "openai" and not OPENAI_AVAILABLE:
            self.status_label.config(
                text="Warning: OpenAI package not installed", foreground="orange"
            )
        elif provider == "anthropic" and not ANTHROPIC_AVAILABLE:
            self.status_label.config(
                text="Warning: Anthropic package not installed", foreground="orange"
            )
        elif provider == "gemini" and not GEMINI_AVAILABLE:
            self.status_label.config(
                text="Warning: Google Generative AI package not installed",
                foreground="orange",
            )
        elif provider == "ollama" and not OLLAMA_AVAILABLE:
            self.status_label.config(
                text="Warning: Ollama package not installed", foreground="orange"
            )
        else:
            self.status_label.config(text="Ready", foreground="black")

    def get_commit_action_label(self):
        """Get the current commit action button label"""
        labels = {
            "commit": "Commit Staged Files",
            "push": "Commit and Push",
            "sync": "Commit and Sync",
        }
        return labels.get(self.commit_action, "Commit Staged Files")

    def set_commit_action(self, action):
        """Set the current commit action"""
        self.commit_action = action
        self.commit_action_button.config(text=f"{self.get_commit_action_label()} ▼")

    def set_commit_action_enabled(self, enabled):
        """Enable or disable the commit action button"""
        state = tk.NORMAL if enabled else tk.DISABLED
        self.commit_action_button.config(state=state)

    def reset_commit_action_state(self):
        """Reset commit action button to its default disabled state"""
        self.set_commit_action("commit")
        self.set_commit_action_enabled(False)

    def run_git_command(self, args, check=True):
        """Run a git command in the current repository"""
        return subprocess.run(
            ["git", *args],
            cwd=self.current_repo_path,
            capture_output=True,
            text=True,
            check=check,
        )

    def get_repo_status_entries(self):
        """Return parsed git status entries for the current repository."""
        status_result = self.run_git_command(["status", "--porcelain"])
        staged_states = {"M", "A", "D", "R", "C", "T", "U"}
        worktree_states = {"M", "A", "D", "R", "C", "T", "U"}
        entries = []

        for raw_line in status_result.stdout.splitlines():
            if not raw_line:
                continue

            index_status = raw_line[0]
            worktree_status = raw_line[1]
            raw_path = raw_line[3:]
            old_path = None
            path = raw_path

            if " -> " in raw_path and (
                index_status in {"R", "C"} or worktree_status in {"R", "C"}
            ):
                old_path, path = raw_path.split(" -> ", 1)

            is_untracked = raw_line.startswith("??")
            entries.append(
                {
                    "raw_line": raw_line,
                    "index_status": index_status,
                    "worktree_status": worktree_status,
                    "path": path,
                    "old_path": old_path,
                    "display_path": raw_path,
                    "is_untracked": is_untracked,
                    "has_staged": index_status in staged_states,
                    "has_unstaged": is_untracked or worktree_status in worktree_states,
                }
            )

        return entries

    def get_file_diff_sections(self, status_entry, context_lines=4):
        """Return diff sections for a single changed file."""
        sections = []
        file_path = status_entry["path"]
        context_arg = f"--unified={context_lines}"

        if status_entry["has_staged"]:
            staged_diff = self.run_git_command(
                ["diff", "--cached", context_arg, "--", file_path]
            ).stdout
            if staged_diff.strip():
                sections.append(("Staged Changes", staged_diff))

        if status_entry["is_untracked"]:
            sections.append(("Untracked File", self.build_untracked_diff(file_path)))
        elif status_entry["has_unstaged"]:
            unstaged_diff = self.run_git_command(
                ["diff", context_arg, "--", file_path]
            ).stdout
            if unstaged_diff.strip():
                sections.append(("Unstaged Changes", unstaged_diff))

        return sections

    def build_untracked_diff(self, relative_path, max_lines=500):
        """Build a synthetic diff preview for an untracked file."""
        full_path = Path(self.current_repo_path) / relative_path
        diff_header = [
            f"diff --git a/{relative_path} b/{relative_path}",
            "new file mode 100644",
            "--- /dev/null",
            f"+++ b/{relative_path}",
        ]

        try:
            file_bytes = full_path.read_bytes()
        except Exception as e:
            return (
                "\n".join(diff_header + [f"[Unable to read file contents: {e}]"]) + "\n"
            )

        if b"\x00" in file_bytes:
            return "\n".join(diff_header + ["[Binary file preview unavailable]"]) + "\n"

        file_text = file_bytes.decode("utf-8", errors="replace")
        content_lines = file_text.splitlines()
        displayed_lines = content_lines[:max_lines]
        hunk_size = len(displayed_lines)
        diff_body = [f"@@ -0,0 +1,{hunk_size} @@"]
        diff_body.extend(f"+{line}" for line in displayed_lines)

        if len(content_lines) > max_lines:
            diff_body.append(
                f"+[... truncated {len(content_lines) - max_lines} more lines ...]"
            )

        if file_text.endswith("\n"):
            return "\n".join(diff_header + diff_body) + "\n"

        return (
            "\n".join(diff_header + diff_body + [r"\ No newline at end of file"]) + "\n"
        )

    def stage_file(self, relative_path):
        """Stage all current changes for a file."""
        self.run_git_command(["add", "--", relative_path])

    def unstage_file(self, relative_path):
        """Unstage a file while keeping working tree changes."""
        try:
            self.run_git_command(["restore", "--staged", "--", relative_path])
        except subprocess.CalledProcessError:
            self.run_git_command(["reset", "HEAD", "--", relative_path])

    def discard_unstaged_changes(self, status_entry):
        """Discard only unstaged changes for a file, preserving staged content."""
        relative_path = status_entry["path"]
        full_path = Path(self.current_repo_path) / relative_path

        if status_entry["is_untracked"]:
            if full_path.is_dir():
                shutil.rmtree(full_path)
            elif full_path.exists():
                full_path.unlink()
            return

        try:
            self.run_git_command(["restore", "--worktree", "--", relative_path])
        except subprocess.CalledProcessError:
            self.run_git_command(["checkout", "--", relative_path])

    def commit_staged_files(self, commit_message):
        """Create a commit for staged files"""
        self.run_git_command(["commit", "-m", commit_message])

    def push_current_branch(self):
        """Push current branch to its remote"""
        self.run_git_command(["push"])

    def sync_current_branch(self):
        """Pull with rebase and then push the current branch"""
        self.run_git_command(["pull", "--rebase"])
        self.run_git_command(["push"])

    def run_selected_commit_action(self):
        """Run the selected commit workflow"""
        self.run_commit_action(self.commit_action)

    def run_commit_action(self, action):
        """Run a specific commit workflow"""
        if not self.current_repo_path:
            messagebox.showwarning("Warning", "Please select a repository first")
            return

        commit_message = self.text_area.get(1.0, tk.END).strip()
        if not commit_message:
            messagebox.showwarning("Warning", "No commit message to use")
            return

        if str(self.commit_action_button.cget("state")) == tk.DISABLED:
            messagebox.showwarning(
                "Warning", "Generate a commit message before running git actions"
            )
            return

        self.commit_action = action
        action_label = self.get_commit_action_label()
        self.set_commit_action_enabled(False)

        def action_thread():
            try:
                self.update_status(f"Running {action_label.lower()}...")

                git_info = self.get_git_info()
                if not git_info["staged_files"] or not any(git_info["staged_files"]):
                    raise Exception(
                        "No staged files found. Please stage some files first."
                    )

                self.commit_staged_files(commit_message)

                if self.commit_action == "push":
                    self.push_current_branch()
                elif self.commit_action == "sync":
                    self.sync_current_branch()

                def on_success():
                    self.text_area.delete(1.0, tk.END)
                    self.update_repo_info()
                    if (
                        self.changes_dialog
                        and self.changes_dialog.window.winfo_exists()
                    ):
                        self.changes_dialog.refresh_contents()
                    self.reset_commit_action_state()
                    self.update_status(f"{action_label} completed successfully")
                    messagebox.showinfo(
                        "Success", f"{action_label} completed successfully."
                    )

                self.root.after(0, on_success)

            except subprocess.CalledProcessError as e:
                error_output = (e.stderr or e.stdout or str(e)).strip()

                def on_failure():
                    self.update_repo_info()
                    self.set_commit_action_enabled(True)
                    self.update_status(f"Error: {error_output}")
                    self.show_error_dialog("Git Error", error_output)

                self.root.after(0, on_failure)

            except Exception as e:
                error_message = str(e)

                def on_failure():
                    self.update_repo_info()
                    self.set_commit_action_enabled(True)
                    self.update_status(f"Error: {error_message}")
                    self.show_error_dialog("Error", error_message)

                self.root.after(0, on_failure)

        threading.Thread(target=action_thread, daemon=True).start()

    def show_commit_actions_menu(self):
        """Show the commit actions dropdown menu"""
        if str(self.commit_action_button.cget("state")) == tk.DISABLED:
            return

        x = self.commit_action_button.winfo_rootx()
        y = (
            self.commit_action_button.winfo_rooty()
            + self.commit_action_button.winfo_height()
        )
        self.commit_actions_menu.post(x, y)

    def manage_repositories(self):
        """Open repository management window"""
        RepositoryManager(self)

    def open_changes_dialog(self):
        """Open the changed files and diff dialog."""
        if not self.current_repo_path:
            messagebox.showwarning("Warning", "Please select a repository first")
            return

        if self.changes_dialog and self.changes_dialog.window.winfo_exists():
            self.changes_dialog.window.lift()
            self.changes_dialog.window.focus_force()
            self.changes_dialog.refresh_contents()
            return

        self.changes_dialog = GitChangesDialog(self)

    def open_terminal(self):
        """Open terminal in the current repository directory"""
        if not self.current_repo_path:
            messagebox.showwarning("Warning", "No repository selected")
            return

        try:
            if platform.system() == "Windows":
                subprocess.run(
                    ["start", "powershell"], cwd=self.current_repo_path, shell=True
                )
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", "-a", "Terminal", self.current_repo_path])
            else:  # Linux
                subprocess.run(["xdg-open", self.current_repo_path])
        except Exception as e:
            self.show_error_dialog("Error", f"Could not open terminal: {str(e)}")

    def open_in_explorer(self):
        """Open repository folder in file explorer"""
        if not self.current_repo_path:
            messagebox.showwarning("Warning", "No repository selected")
            return

        import platform

        system = platform.system()

        try:
            if system == "Windows":
                subprocess.run(["explorer", self.current_repo_path])
            elif system == "Darwin":  # macOS
                subprocess.run(["open", self.current_repo_path])
            else:  # Linux
                subprocess.run(["xdg-open", self.current_repo_path])
        except Exception as e:
            self.show_error_dialog("Error", f"Could not open explorer: {str(e)}")

    def generate_clicked(self):
        """Handle generate button click"""
        if not self.current_repo_path:
            messagebox.showwarning("Warning", "Please select a repository first")
            return

        self.reset_commit_action_state()

        def generate_thread():
            try:
                self.update_status("Getting git information...")
                git_info = self.get_git_info()

                if not git_info["staged_files"] or not any(git_info["staged_files"]):
                    self.update_status("No staged files found")
                    messagebox.showwarning(
                        "Warning",
                        "No staged files found. Please stage some files first.",
                    )
                    return

                self.update_status("Generating commit message...")
                commit_message = self.generate_commit_message(git_info)

                self.text_area.delete(1.0, tk.END)
                self.text_area.insert(1.0, commit_message)
                self.set_commit_action_enabled(True)
                self.update_status("Commit message generated successfully")

                # Refresh repo info to show updated status
                self.update_repo_info()

            except Exception as e:
                self.update_status(f"Error: {str(e)}")
                self.show_error_dialog("Error", str(e))

        threading.Thread(target=generate_thread, daemon=True).start()

    def configure_clicked(self):
        """Open configuration window"""
        ConfigWindow(self)

    def copy_clicked(self):
        """Copy commit message to clipboard"""
        commit_message = self.text_area.get(1.0, tk.END).strip()
        if commit_message:
            self.root.clipboard_clear()
            self.root.clipboard_append(commit_message)
            self.update_status("Copied to clipboard")
        else:
            messagebox.showwarning("Warning", "No commit message to copy")

    def update_status(self, message):
        """Update status label"""
        self.status_label.config(text=message)
        self.root.update_idletasks()

    def show_repo_actions_menu(self, event=None):
        """Show the repository actions dropdown menu"""
        # Display the menu below the button
        button = self.repo_actions_button
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        self.repo_actions_menu.post(x, y)

    def refresh_repo_status(self):
        """Refresh the repository status when refresh button is clicked"""
        if self.current_repo_path:
            self.update_status("Refreshing repository status...")
            self.update_repo_info()
            if self.changes_dialog and self.changes_dialog.window.winfo_exists():
                self.changes_dialog.refresh_contents()
            self.reset_commit_action_state()
            self.update_status("Repository status refreshed")
        else:
            self.update_status("No repository selected")

    def show_error_dialog(self, title, message):
        """Show a custom error dialog with copyable message"""
        error_window = tk.Toplevel(self.root)
        error_window.title(title)
        error_window.geometry("500x300")
        error_window.resizable(True, True)
        error_window.transient(self.root)
        error_window.grab_set()

        # Create frame
        frame = ttk.Frame(error_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # Error message in scrolled text (read-only)
        text_area = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=10)
        text_area.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        text_area.insert(1.0, message)
        text_area.config(state=tk.DISABLED)  # Make read-only but selectable

        # OK button
        ttk.Button(frame, text="OK", command=error_window.destroy).pack(side=tk.RIGHT)

    def run(self):
        """Start the GUI"""
        # Check if we need to restart after package installation
        if self.restart_needed:
            self.root.destroy()
            python = sys.executable
            os.execl(python, python, *sys.argv)
        else:
            self.root.mainloop()


class GitChangesDialog:
    def __init__(self, parent):
        self.parent = parent
        self.status_entries = []
        self.window = tk.Toplevel(parent.root)
        self.window.title("Repository Changes")
        self.window.geometry("1120x720")
        self.window.minsize(860, 520)
        self.window.transient(parent.root)
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

        self.diff_font = self.build_diff_font()
        self.setup_gui()
        self.refresh_contents()

    def build_diff_font(self):
        """Create a monospace font for diff output."""
        preferred_fonts = ["Cascadia Code", "Consolas", "Courier New", "TkFixedFont"]
        available_fonts = set(tkfont.families())
        family = next(
            (name for name in preferred_fonts if name in available_fonts), "TkFixedFont"
        )
        return tkfont.Font(family=family, size=10)

    def setup_gui(self):
        """Build the changed files dialog UI."""
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.window, padding="10 10 10 0")
        toolbar.grid(row=0, column=0, sticky=(tk.W, tk.E))
        toolbar.columnconfigure(0, weight=1)

        self.summary_label = ttk.Label(toolbar, text="Loading changes...")
        self.summary_label.grid(row=0, column=0, sticky=tk.W)

        action_frame = ttk.Frame(toolbar)
        action_frame.grid(row=0, column=1, sticky=tk.E)

        self.stage_button = ttk.Button(
            action_frame,
            text="Stage Selected",
            command=self.stage_selected,
            state=tk.DISABLED,
        )
        self.stage_button.pack(side=tk.LEFT, padx=(0, 5))

        self.unstage_button = ttk.Button(
            action_frame,
            text="Unstage Selected",
            command=self.unstage_selected,
            state=tk.DISABLED,
        )
        self.unstage_button.pack(side=tk.LEFT, padx=(0, 5))

        self.discard_button = ttk.Button(
            action_frame,
            text="Discard Unstaged",
            command=self.discard_selected,
            state=tk.DISABLED,
        )
        self.discard_button.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(action_frame, text="Refresh", command=self.refresh_contents).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(action_frame, text="Close", command=self.close_window).pack(
            side=tk.LEFT
        )

        content = ttk.PanedWindow(self.window, orient=tk.HORIZONTAL)
        content.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)

        left_panel = ttk.Frame(content, padding="0")
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(1, weight=1)
        content.add(left_panel, weight=1)

        ttk.Label(left_panel, text="Changed Files").grid(
            row=0, column=0, sticky=tk.W, pady=(0, 5)
        )

        files_frame = ttk.Frame(left_panel)
        files_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        files_frame.columnconfigure(0, weight=1)
        files_frame.rowconfigure(0, weight=1)

        self.files_listbox = tk.Listbox(
            files_frame,
            selectmode=tk.EXTENDED,
            exportselection=False,
            activestyle="none",
        )
        self.files_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.files_listbox.bind("<<ListboxSelect>>", self.on_selection_changed)

        files_scrollbar = ttk.Scrollbar(
            files_frame, orient=tk.VERTICAL, command=self.files_listbox.yview
        )
        files_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.files_listbox.config(yscrollcommand=files_scrollbar.set)

        ttk.Label(
            left_panel,
            text="Tip: use Ctrl/Shift to select multiple files.",
            foreground="gray",
        ).grid(row=2, column=0, sticky=tk.W, pady=(6, 0))

        right_panel = ttk.Frame(content, padding="0")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)
        content.add(right_panel, weight=3)

        self.diff_title_label = ttk.Label(right_panel, text="Diff Preview")
        self.diff_title_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        diff_frame = ttk.Frame(right_panel)
        diff_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        diff_frame.columnconfigure(0, weight=1)
        diff_frame.rowconfigure(0, weight=1)

        self.diff_text = tk.Text(
            diff_frame,
            wrap=tk.NONE,
            font=self.diff_font,
            state=tk.DISABLED,
            undo=False,
        )
        self.diff_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        diff_y_scroll = ttk.Scrollbar(
            diff_frame, orient=tk.VERTICAL, command=self.diff_text.yview
        )
        diff_y_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        diff_x_scroll = ttk.Scrollbar(
            diff_frame, orient=tk.HORIZONTAL, command=self.diff_text.xview
        )
        diff_x_scroll.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.diff_text.config(
            yscrollcommand=diff_y_scroll.set, xscrollcommand=diff_x_scroll.set
        )

        self.configure_diff_tags()

    def configure_diff_tags(self):
        """Configure text tags used to colorize diff output."""
        self.diff_text.tag_configure(
            "file_title", font=(self.diff_font.actual("family"), 11, "bold")
        )
        self.diff_text.tag_configure("section_title", foreground="#6b7280", spacing1=8)
        self.diff_text.tag_configure("diff_meta", foreground="#1d4ed8")
        self.diff_text.tag_configure("hunk", foreground="#7c3aed")
        self.diff_text.tag_configure("added", foreground="#15803d")
        self.diff_text.tag_configure("removed", foreground="#b91c1c")
        self.diff_text.tag_configure(
            "note",
            foreground="#6b7280",
            font=(self.diff_font.actual("family"), 10, "italic"),
        )

    def close_window(self):
        """Close the dialog and clear the parent reference."""
        self.parent.changes_dialog = None
        self.window.destroy()

    def format_entry_label(self, entry):
        """Format a status entry for the changed files list."""
        flags = []
        if entry["has_staged"]:
            flags.append("S")
        if entry["has_unstaged"]:
            flags.append("U")
        if entry["is_untracked"]:
            flags.append("NEW")

        flag_text = "/".join(flags) if flags else "-"
        return f"[{flag_text}] {entry['display_path']}"

    def get_listbox_color(self, entry):
        """Return an item color based on staged/unstaged state."""
        if entry["has_staged"] and entry["has_unstaged"]:
            return "#1d4ed8"
        if entry["has_staged"]:
            return "#15803d"
        return "#b45309"

    def refresh_contents(self):
        """Reload repository status and refresh the dialog."""
        selected_paths = {entry["path"] for entry in self.get_selected_entries()}

        try:
            self.status_entries = self.parent.get_repo_status_entries()
        except Exception as e:
            self.status_entries = []
            self.summary_label.config(text="Unable to load changes")
            self.render_text([(str(e), "note")])
            self.files_listbox.delete(0, tk.END)
            self.update_action_buttons()
            return

        self.files_listbox.delete(0, tk.END)
        for index, entry in enumerate(self.status_entries):
            self.files_listbox.insert(tk.END, self.format_entry_label(entry))
            self.files_listbox.itemconfig(index, fg=self.get_listbox_color(entry))

        staged_count = sum(1 for entry in self.status_entries if entry["has_staged"])
        unstaged_count = sum(
            1 for entry in self.status_entries if entry["has_unstaged"]
        )
        self.summary_label.config(
            text=(
                f"{len(self.status_entries)} changed file(s) | "
                f"Staged: {staged_count} | Unstaged: {unstaged_count}"
            )
        )

        restored = False
        for index, entry in enumerate(self.status_entries):
            if entry["path"] in selected_paths:
                self.files_listbox.selection_set(index)
                restored = True

        if self.status_entries and not restored:
            self.files_listbox.selection_set(0)

        self.render_selected_diffs()
        self.update_action_buttons()

    def get_selected_entries(self):
        """Return the currently selected file entries."""
        return [self.status_entries[i] for i in self.files_listbox.curselection()]

    def on_selection_changed(self, event=None):
        """Update the diff preview when the selection changes."""
        self.render_selected_diffs()
        self.update_action_buttons()

    def update_action_buttons(self):
        """Enable or disable stage/unstage buttons based on selection."""
        selected_entries = self.get_selected_entries()
        can_stage = any(entry["has_unstaged"] for entry in selected_entries)
        can_unstage = any(entry["has_staged"] for entry in selected_entries)
        can_discard = any(
            entry["has_unstaged"] and not entry["has_staged"]
            for entry in selected_entries
        )
        self.stage_button.config(state=tk.NORMAL if can_stage else tk.DISABLED)
        self.unstage_button.config(state=tk.NORMAL if can_unstage else tk.DISABLED)
        self.discard_button.config(state=tk.NORMAL if can_discard else tk.DISABLED)

    def render_text(self, segments):
        """Render tagged text segments into the diff preview."""
        self.diff_text.config(state=tk.NORMAL)
        self.diff_text.delete("1.0", tk.END)

        for text, tag in segments:
            self.diff_text.insert(tk.END, text, tag)

        self.diff_text.config(state=tk.DISABLED)
        self.diff_text.yview_moveto(0)
        self.diff_text.xview_moveto(0)

    def render_selected_diffs(self):
        """Render diffs for the current file selection."""
        selected_entries = self.get_selected_entries()

        if not self.status_entries:
            self.diff_title_label.config(text="Diff Preview")
            self.render_text([("No changed files in this repository.\n", "note")])
            return

        if not selected_entries:
            self.diff_title_label.config(text="Diff Preview")
            self.render_text([("Select a file to preview its diff.\n", "note")])
            return

        self.diff_title_label.config(
            text=f"Diff Preview ({len(selected_entries)} selected)"
        )

        segments = []
        for entry in selected_entries:
            header = self.format_entry_label(entry)
            segments.append((f"{header}\n", "file_title"))

            sections = self.parent.get_file_diff_sections(entry, context_lines=4)
            if not sections:
                segments.append(("No diff available for this file.\n\n", "note"))
                continue

            for section_title, diff_text in sections:
                segments.append((f"{section_title}\n", "section_title"))
                segments.extend(self.colorize_diff(diff_text))
                segments.append(("\n", None))

            segments.append(("\n", None))

        self.render_text(segments)

    def colorize_diff(self, diff_text):
        """Split raw diff text into tagged lines for syntax coloring."""
        segments = []
        for line in diff_text.splitlines(keepends=True):
            tag = None
            if line.startswith("diff --git"):
                tag = "diff_meta"
            elif line.startswith(
                (
                    "index ",
                    "new file mode",
                    "deleted file mode",
                    "similarity index",
                    "rename from ",
                    "rename to ",
                    "copy from ",
                    "copy to ",
                    "--- ",
                    "+++ ",
                )
            ):
                tag = "diff_meta"
            elif line.startswith("@@"):
                tag = "hunk"
            elif line.startswith("+") and not line.startswith("+++"):
                tag = "added"
            elif line.startswith("-") and not line.startswith("---"):
                tag = "removed"
            elif line.startswith("\\"):
                tag = "note"

            segments.append((line, tag))

        return segments

    def stage_selected(self):
        """Stage the selected files."""
        selected_entries = self.get_selected_entries()
        target_entries = [entry for entry in selected_entries if entry["has_unstaged"]]
        if not target_entries:
            return

        try:
            for entry in target_entries:
                self.parent.stage_file(entry["path"])
        except Exception as e:
            self.parent.show_error_dialog("Stage Failed", str(e))
            return

        self.parent.update_repo_info()
        self.parent.reset_commit_action_state()
        self.parent.update_status(f"Staged {len(target_entries)} file(s)")
        self.refresh_contents()

    def unstage_selected(self):
        """Unstage the selected files."""
        selected_entries = self.get_selected_entries()
        target_entries = [entry for entry in selected_entries if entry["has_staged"]]
        if not target_entries:
            return

        try:
            for entry in target_entries:
                self.parent.unstage_file(entry["path"])
        except Exception as e:
            self.parent.show_error_dialog("Unstage Failed", str(e))
            return

        self.parent.update_repo_info()
        self.parent.reset_commit_action_state()
        self.parent.update_status(f"Unstaged {len(target_entries)} file(s)")
        self.refresh_contents()

    def discard_selected(self):
        """Discard only unstaged changes for selected files without staged changes."""
        selected_entries = self.get_selected_entries()
        target_entries = [
            entry
            for entry in selected_entries
            if entry["has_unstaged"] and not entry["has_staged"]
        ]
        if not target_entries:
            return

        file_list = "\n".join(f"- {entry['display_path']}" for entry in target_entries)
        confirmed = messagebox.askyesno(
            "Discard Unstaged Changes",
            "This will permanently discard unstaged changes for the selected files.\n\n"
            f"{file_list}\n\n"
            "Files with staged changes are not affected.",
            parent=self.window,
        )
        if not confirmed:
            return

        try:
            for entry in target_entries:
                self.parent.discard_unstaged_changes(entry)
        except Exception as e:
            self.parent.show_error_dialog("Discard Failed", str(e))
            return

        self.parent.update_repo_info()
        self.parent.reset_commit_action_state()
        self.parent.update_status(
            f"Discarded unstaged changes in {len(target_entries)} file(s)"
        )
        self.refresh_contents()


class RepositoryManager:
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent.root)
        self.window.title("Repository Manager")
        self.window.geometry("600x400")
        self.window.resizable(False, False)  # Prevent resizing
        self.window.transient(parent.root)
        self.window.grab_set()

        self.setup_repo_gui()
        self.refresh_repo_list()

    def setup_repo_gui(self):
        """Setup repository management GUI"""
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Instructions
        ttk.Label(
            main_frame,
            text="Manage Git Repositories",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(anchor=tk.W, pady=(0, 10))

        # Repository list
        list_frame = ttk.LabelFrame(
            main_frame, text="Configured Repositories", padding="5"
        )
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Listbox with scrollbar
        listbox_frame = ttk.Frame(list_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.repo_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set)
        self.repo_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.repo_listbox.yview)

        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            button_frame, text="Add Repository", command=self.add_repository
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            button_frame, text="Remove Selected", command=self.remove_repository
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Validate All", command=self.validate_all).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(button_frame, text="Auto-Detect", command=self.auto_detect).pack(
            side=tk.LEFT
        )

        # Close button
        ttk.Button(main_frame, text="Close", command=self.close_window).pack(
            side=tk.RIGHT
        )

    def refresh_repo_list(self):
        """Refresh the repository list"""
        self.repo_listbox.delete(0, tk.END)
        paths = self.parent.get_repository_paths()

        for path in paths:
            status = "✓" if self.parent.is_valid_git_repo(path) else "✗"
            display_text = f"{status} {Path(path).name} - {path}"
            self.repo_listbox.insert(tk.END, display_text)

    def add_repository(self):
        """Add a new repository"""
        folder_path = filedialog.askdirectory(title="Select Git Repository Folder")
        if folder_path:
            if self.parent.is_valid_git_repo(folder_path):
                paths = self.parent.get_repository_paths()
                if folder_path not in paths:
                    paths.append(folder_path)
                    self.parent.save_repository_paths(paths)
                    self.refresh_repo_list()
                    self.parent.refresh_repositories()
                    messagebox.showinfo("Success", "Repository added successfully!")
                else:
                    messagebox.showwarning(
                        "Warning", "Repository already exists in the list"
                    )
            else:
                self.parent.show_error_dialog(
                    "Error", "Selected folder is not a valid git repository"
                )

    def remove_repository(self):
        """Remove selected repository"""
        selection = self.repo_listbox.curselection()
        if selection:
            paths = self.parent.get_repository_paths()
            if selection[0] < len(paths):
                removed_path = paths.pop(selection[0])
                self.parent.save_repository_paths(paths)
                self.refresh_repo_list()
                self.parent.refresh_repositories()
                messagebox.showinfo("Success", f"Repository removed: {removed_path}")
        else:
            messagebox.showwarning("Warning", "Please select a repository to remove")

    def validate_all(self):
        """Validate all repositories and remove invalid ones"""
        paths = self.parent.get_repository_paths()
        valid_paths = self.parent.validate_repositories(paths)

        if len(valid_paths) != len(paths):
            self.parent.save_repository_paths(valid_paths)
            self.refresh_repo_list()
            self.parent.refresh_repositories()
            removed_count = len(paths) - len(valid_paths)
            messagebox.showinfo(
                "Validation Complete", f"Removed {removed_count} invalid repository/ies"
            )
        else:
            messagebox.showinfo("Validation Complete", "All repositories are valid")

    def auto_detect(self):
        """Auto-detect git repositories in common locations"""
        common_paths = [
            Path.home() / "Documents",
            Path.home() / "Projects",
            Path.home() / "Development",
            Path.home() / "dev",
            Path.home() / "src",
            Path.home() / "git",
            Path.home(),
        ]

        found_repos = []
        for base_path in common_paths:
            if base_path.exists():
                for item in base_path.iterdir():
                    if item.is_dir() and self.parent.is_valid_git_repo(str(item)):
                        found_repos.append(str(item))

        if found_repos:
            existing_paths = self.parent.get_repository_paths()
            new_repos = [repo for repo in found_repos if repo not in existing_paths]

            if new_repos:
                all_paths = existing_paths + new_repos
                self.parent.save_repository_paths(all_paths)
                self.refresh_repo_list()
                self.parent.refresh_repositories()
                messagebox.showinfo(
                    "Auto-Detection Complete",
                    f"Found and added {len(new_repos)} new repositories",
                )
            else:
                messagebox.showinfo(
                    "Auto-Detection Complete", "No new repositories found"
                )
        else:
            messagebox.showinfo(
                "Auto-Detection Complete",
                "No git repositories found in common locations",
            )

    def close_window(self):
        """Close the repository manager window"""
        self.window.destroy()


class ConfigWindow:
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent.root)
        self.window.title("Configuration")
        self.window.geometry("800x640")
        self.window.resizable(False, False)  # Prevent resizing
        self.window.transient(parent.root)
        self.window.grab_set()

        self.setup_config_gui()

    def on_provider_change(self, event=None):
        """Update UI based on selected provider"""
        provider = self.provider_var.get()

        # Show/hide API key frames based on selected provider
        self.openai_frame.grid_remove()
        self.anthropic_frame.grid_remove()
        self.gemini_frame.grid_remove()
        self.ollama_frame.grid_remove()

        # Reset package status by default
        self.package_status_label.config(text="")
        self.package_install_button.grid_remove()

        # Show only the selected provider's API key input and check package status
        if provider == "openai":
            self.openai_frame.grid()
            # Show package status only if not installed
            if not OPENAI_AVAILABLE:
                self.package_status_label.config(text="OpenAI package not installed")
                self.package_install_button.grid()
        elif provider == "anthropic":
            self.anthropic_frame.grid()
            # Show package status only if not installed
            if not ANTHROPIC_AVAILABLE:
                self.package_status_label.config(text="Anthropic package not installed")
                self.package_install_button.grid()
        elif provider == "gemini":
            self.gemini_frame.grid()
            # Show package status only if not installed
            if not GEMINI_AVAILABLE:
                self.package_status_label.config(
                    text="Google Generative AI package not installed"
                )
                self.package_install_button.grid()
        elif provider == "ollama":
            self.ollama_frame.grid()
            # Show package status only if not installed
            if not OLLAMA_AVAILABLE:
                self.package_status_label.config(text="Ollama package not installed")
                self.package_install_button.grid()

    def setup_config_gui(self):
        """Setup configuration GUI"""
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        notebook = ttk.Notebook(self.window)
        notebook.grid(
            row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10
        )

        # API Configuration Tab
        api_frame = ttk.Frame(notebook)
        notebook.add(api_frame, text="API Settings")

        # Provider selection with package status message
        provider_frame = ttk.Frame(api_frame)
        provider_frame.grid(
            row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5
        )
        provider_frame.columnconfigure(1, weight=1)

        ttk.Label(provider_frame, text="AI Provider:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5
        )
        self.provider_var = tk.StringVar(
            value=self.parent.config.get("API", "provider")
        )
        provider_combo = ttk.Combobox(
            provider_frame,
            textvariable=self.provider_var,
            values=["openai", "anthropic", "gemini", "ollama"],
        )
        provider_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        provider_combo.bind("<<ComboboxSelected>>", self.on_provider_change)

        # Package status label and button - will be populated in on_provider_change
        self.package_status_label = ttk.Label(
            provider_frame, text="", foreground="#CC0000"
        )
        self.package_status_label.grid(row=0, column=2, padx=(10, 5), pady=5)

        self.package_install_button = ttk.Button(
            provider_frame,
            text="Install Package",
            command=self.install_missing_packages,
        )
        self.package_install_button.grid(row=0, column=3, padx=5, pady=5)
        self.package_install_button.grid_remove()  # Hide by default

        # API Key frames (will show/hide based on provider)
        self.openai_frame = ttk.Frame(api_frame)
        self.openai_frame.grid(
            row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5
        )
        ttk.Label(self.openai_frame, text="OpenAI API Key:").grid(
            row=0, column=0, sticky=tk.W
        )
        self.openai_key_var = tk.StringVar(
            value=self.parent.config.get("API", "openai_api_key")
        )
        ttk.Entry(
            self.openai_frame, textvariable=self.openai_key_var, show="*", width=50
        ).grid(row=0, column=1, sticky=(tk.W, tk.E))

        self.anthropic_frame = ttk.Frame(api_frame)
        self.anthropic_frame.grid(
            row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5
        )
        ttk.Label(self.anthropic_frame, text="Anthropic API Key:").grid(
            row=0, column=0, sticky=tk.W
        )
        self.anthropic_key_var = tk.StringVar(
            value=self.parent.config.get("API", "anthropic_api_key")
        )
        ttk.Entry(
            self.anthropic_frame,
            textvariable=self.anthropic_key_var,
            show="*",
            width=50,
        ).grid(row=0, column=1, sticky=(tk.W, tk.E))

        self.gemini_frame = ttk.Frame(api_frame)
        self.gemini_frame.grid(
            row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5
        )
        ttk.Label(self.gemini_frame, text="Gemini API Key:").grid(
            row=0, column=0, sticky=tk.W
        )
        self.gemini_key_var = tk.StringVar(
            value=self.parent.config.get("API", "gemini_api_key")
        )
        ttk.Entry(
            self.gemini_frame, textvariable=self.gemini_key_var, show="*", width=50
        ).grid(row=0, column=1, sticky=(tk.W, tk.E))

        self.ollama_frame = ttk.Frame(api_frame)
        self.ollama_frame.grid(
            row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5
        )
        ttk.Label(self.ollama_frame, text="Ollama Host URL:").grid(
            row=0, column=0, sticky=tk.W
        )
        self.ollama_host_var = tk.StringVar(
            value=self.parent.config.get(
                "API", "ollama_host", fallback="http://localhost:11434"
            )
        )
        ttk.Entry(self.ollama_frame, textvariable=self.ollama_host_var, width=50).grid(
            row=0, column=1, sticky=(tk.W, tk.E)
        )

        # Model selection
        model_frame = ttk.Frame(api_frame)
        model_frame.grid(
            row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5
        )
        ttk.Label(model_frame, text="Model:").grid(row=0, column=0, sticky=tk.W)
        self.model_var = tk.StringVar(value=self.parent.config.get("API", "model"))
        ttk.Entry(model_frame, textvariable=self.model_var, width=50).grid(
            row=0, column=1, sticky=(tk.W, tk.E)
        )

        # Model suggestions
        model_info = ttk.Label(
            api_frame,
            text="Common models: OpenAI: gpt-3.5-turbo, gpt-4 | Anthropic: claude-3-haiku-20240307 | Gemini: gemini-pro | Ollama: llama3, mistral",
            font=("TkDefaultFont", 8),
            foreground="gray",
        )
        model_info.grid(
            row=6, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(2, 10)
        )

        # Prompt Settings (moved from separate tab to API Settings tab)
        prompt_settings_frame = ttk.LabelFrame(api_frame, text="Prompt Settings")
        prompt_settings_frame.grid(
            row=7,
            column=0,
            columnspan=2,
            sticky=(tk.W, tk.E, tk.N, tk.S),
            padx=5,
            pady=5,
        )
        prompt_settings_frame.columnconfigure(0, weight=1)

        ttk.Label(prompt_settings_frame, text="System Prompt:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=(5, 0)
        )
        self.system_prompt_text = scrolledtext.ScrolledText(
            prompt_settings_frame, height=6
        )
        self.system_prompt_text.grid(
            row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5
        )
        self.system_prompt_text.insert(
            1.0, self.parent.config.get("PROMPT", "system_prompt")
        )

        ttk.Label(
            prompt_settings_frame,
            text="User Prompt (use {{placeholder}} for variables):",
        ).grid(row=2, column=0, sticky=tk.W, padx=5, pady=(5, 0))
        self.user_prompt_text = scrolledtext.ScrolledText(
            prompt_settings_frame, height=6
        )
        self.user_prompt_text.grid(
            row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5
        )
        self.user_prompt_text.insert(
            1.0, self.parent.config.get("PROMPT", "user_prompt")
        )

        # Available placeholders info
        placeholders_info = """Available placeholders:
{{branch_name}} - Current git branch
{{repo_name}} - Repository name
{{repo_path}} - Full path to repository
{{date}} - Current date and time
{{files_changed}} - List of changed files
{{git_diff}} - Full git diff of staged changes"""

        ttk.Label(
            prompt_settings_frame,
            text=placeholders_info,
            font=("TkDefaultFont", 8),
            foreground="gray",
        ).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)

        # Configure grid weights for proper expansion
        api_frame.columnconfigure(1, weight=1)
        api_frame.rowconfigure(7, weight=1)

        # Initial UI update based on selected provider
        self.on_provider_change(None)

        # GUI Settings Tab
        gui_frame = ttk.Frame(notebook)
        notebook.add(gui_frame, text="GUI Settings")

        self.always_on_top_var = tk.BooleanVar(
            value=self.parent.config.getboolean("GUI", "always_on_top")
        )
        ttk.Checkbutton(
            gui_frame, text="Always on top", variable=self.always_on_top_var
        ).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(self.window)
        button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)

        ttk.Button(button_frame, text="Save", command=self.save_config).pack(
            side=tk.RIGHT, padx=(5, 0)
        )
        ttk.Button(button_frame, text="Cancel", command=self.window.destroy).pack(
            side=tk.RIGHT
        )

    def install_missing_packages(self):
        """Install missing AI API package for selected provider"""
        missing_packages = []
        provider = self.provider_var.get()

        if provider == "openai" and not OPENAI_AVAILABLE:
            missing_packages.append(("openai", "OpenAI"))
        elif provider == "anthropic" and not ANTHROPIC_AVAILABLE:
            missing_packages.append(("anthropic", "Anthropic Claude"))
        elif provider == "gemini" and not GEMINI_AVAILABLE:
            missing_packages.append(("google-generativeai", "Google Gemini"))
        elif provider == "ollama" and not OLLAMA_AVAILABLE:
            missing_packages.append(("ollama", "Ollama"))

        if missing_packages:
            if messagebox.askyesno(
                "Missing Package",
                f"The {missing_packages[0][1]} package is required but not installed.\n\nWould you like to install it now?",
            ):
                self.parent.offer_package_installation(missing_packages)
                self.window.destroy()
        else:
            messagebox.showinfo(
                "Packages", "Selected API package is already installed."
            )

    def save_config(self):
        """Save configuration"""
        # Check if provider changed
        old_provider = self.parent.config.get("API", "provider")
        new_provider = self.provider_var.get()
        provider_changed = old_provider != new_provider

        # Update config
        self.parent.config.set("API", "provider", new_provider)
        self.parent.config.set("API", "openai_api_key", self.openai_key_var.get())
        self.parent.config.set("API", "anthropic_api_key", self.anthropic_key_var.get())
        self.parent.config.set("API", "gemini_api_key", self.gemini_key_var.get())
        self.parent.config.set("API", "ollama_host", self.ollama_host_var.get())
        self.parent.config.set("API", "model", self.model_var.get())
        self.parent.config.set(
            "PROMPT", "system_prompt", self.system_prompt_text.get(1.0, tk.END).strip()
        )
        self.parent.config.set(
            "PROMPT", "user_prompt", self.user_prompt_text.get(1.0, tk.END).strip()
        )
        self.parent.config.set(
            "GUI", "always_on_top", str(self.always_on_top_var.get())
        )

        # Save to file
        self.parent.save_config()

        # Reinitialize API clients
        self.parent.setup_api_clients()

        # Check required packages if provider changed
        if provider_changed:
            self.window.destroy()
            self.parent.check_required_packages()
        else:
            messagebox.showinfo(
                "Success",
                "Configuration saved successfully!\nRestart the application for GUI changes to take effect.",
            )
            self.window.destroy()


def main():
    app = GitCommitAI()
    app.run()


if __name__ == "__main__":
    main()
