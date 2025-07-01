#!/usr/bin/env python3
"""
AI-powered Git Commit Message Generator with Multi-Repository Support
Supports OpenAI, Anthropic Claude, and Google Gemini APIs
"""

import subprocess
import json
import os
import re
import tkinter as tk
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
        # For packages with dots, try importing directly
        # For Google's package, we need to use the import name, not the pip name
        pkg_to_check = package_name
        if package_name == 'google.generativeai':
            # First check if the parent module exists
            try:
                __import__('google')
            except ImportError:
                return False
        
        # Try to import the package
        __import__(pkg_to_check)
        return True
    except (ImportError, ModuleNotFoundError):
        return False

# API clients
OPENAI_AVAILABLE = is_package_installed('openai')
ANTHROPIC_AVAILABLE = is_package_installed('anthropic')
# For Google's package, pip install name is 'google-generativeai' but import name is 'google.generativeai'
GEMINI_AVAILABLE = is_package_installed('google.generativeai')

# Import available clients
if OPENAI_AVAILABLE:
    import openai

if ANTHROPIC_AVAILABLE:
    from anthropic import Anthropic

if GEMINI_AVAILABLE:
    import google.generativeai as genai


class GitCommitAI:
    def __init__(self):
        self.config_file = Path.home() / '.git_commit_ai_config.ini'
        self.config = configparser.ConfigParser()
        self.current_repo_path = None
        self.restart_needed = False
        self.load_config()
        
        # Initialize API clients
        self.openai_client = None
        self.anthropic_client = None
        self.gemini_model = None
        
        # Create GUI before checking packages (needed for message boxes)
        self.setup_gui()
        
        # Check required packages based on configured provider
        self.check_required_packages()
        self.setup_api_clients()
        self.refresh_repositories()

    def load_config(self):
        """Load configuration from file or create default"""
        default_config = {
            'API': {
                'provider': 'openai',  # openai, anthropic, or gemini
                'openai_api_key': '',
                'anthropic_api_key': '',
                'gemini_api_key': '',
                'model': 'gpt-3.5-turbo'  # or claude-3-sonnet-20240229, gemini-pro
            },
            'REPOSITORIES': {
                'paths': '',  # JSON string of repository paths
                'current_repo': ''  # Currently selected repository path
            },
            'PROMPT': {
                'system_prompt': '''You are a helpful assistant that generates concise, clear git commit messages. 
Follow conventional commit format when appropriate (feat:, fix:, docs:, etc.).
Be specific about what changed and why.''',
                'user_prompt': '''Based on the following git diff and context, generate a commit message:

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
4. Is under 72 characters for the first line'''
            },
            'GUI': {
                'always_on_top': 'true'
            }
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
        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def get_repository_paths(self):
        """Get list of repository paths from config"""
        paths_json = self.config.get('REPOSITORIES', 'paths', fallback='[]')
        try:
            return json.loads(paths_json) if paths_json else []
        except json.JSONDecodeError:
            return []

    def save_repository_paths(self, paths):
        """Save repository paths to config"""
        self.config.set('REPOSITORIES', 'paths', json.dumps(paths))
        self.save_config()

    def is_valid_git_repo(self, path):
        """Check if path contains a valid git repository"""
        try:
            if not os.path.exists(path):
                return False
            result = subprocess.run(['git', 'status'], 
                                  cwd=path, capture_output=True, text=True)
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
        provider = self.config.get('API', 'provider')
        missing_packages = []
        
        if provider == 'openai' and not OPENAI_AVAILABLE:
            missing_packages.append(('openai', 'OpenAI'))
        elif provider == 'anthropic' and not ANTHROPIC_AVAILABLE:
            missing_packages.append(('anthropic', 'Anthropic Claude'))
        elif provider == 'gemini' and not GEMINI_AVAILABLE:
            missing_packages.append(('google-generativeai', 'Google Gemini'))
            
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
            info_label = ttk.Label(progress_window, text="Installing required packages. This may take a moment...")
            info_label.pack(pady=(20, 10))
            
            progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
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
                        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_name])
                    except Exception as e:
                        success = False
                        failed_packages.append(display_name)
                
                # Close progress window
                progress_window.after(500, progress_window.destroy)
                
                # Show result
                if success:
                    messagebox.showinfo("Installation Complete", 
                                      "Packages installed successfully.\nPlease restart the application to use the new packages.")
                else:
                    failed_list = ", ".join(failed_packages)
                    messagebox.showerror("Installation Failed", 
                                       f"Failed to install: {failed_list}\n\nPlease install manually using pip.")
                
                # Set restart flag
                self.restart_needed = True
            
            # Start installation in background thread
            self.restart_needed = False
            threading.Thread(target=install_thread, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to install packages: {str(e)}")
            
    def setup_api_clients(self):
        """Initialize API clients based on configuration"""
        provider = self.config.get('API', 'provider')
        
        if provider == 'openai' and OPENAI_AVAILABLE:
            api_key = self.config.get('API', 'openai_api_key')
            if api_key:
                self.openai_client = openai.OpenAI(api_key=api_key)
        
        elif provider == 'anthropic' and ANTHROPIC_AVAILABLE:
            api_key = self.config.get('API', 'anthropic_api_key')
            if api_key:
                self.anthropic_client = Anthropic(api_key=api_key)
        
        elif provider == 'gemini' and GEMINI_AVAILABLE:
            api_key = self.config.get('API', 'gemini_api_key')
            if api_key:
                genai.configure(api_key=api_key)
                model_name = self.config.get('API', 'model', fallback='gemini-pro')
                self.gemini_model = genai.GenerativeModel(model_name)

    def get_git_info(self):
        """Get git repository information"""
        if not self.current_repo_path:
            raise Exception("No repository selected")
        
        if not self.is_valid_git_repo(self.current_repo_path):
            raise Exception(f"Invalid git repository: {self.current_repo_path}")
        
        try:
            # Get current branch
            branch_result = subprocess.run(['git', 'branch', '--show-current'], 
                                         cwd=self.current_repo_path,
                                         capture_output=True, text=True, check=True)
            branch_name = branch_result.stdout.strip()
            
            # Get repository name
            repo_result = subprocess.run(['git', 'remote', 'get-url', 'origin'], 
                                       cwd=self.current_repo_path,
                                       capture_output=True, text=True)
            repo_url = repo_result.stdout.strip() if repo_result.returncode == 0 else ""
            repo_name = Path(repo_url).stem.replace('.git', '') if repo_url else Path(self.current_repo_path).name
            
            # Get staged files
            staged_result = subprocess.run(['git', 'diff', '--cached', '--name-only'], 
                                         cwd=self.current_repo_path,
                                         capture_output=True, text=True, check=True)
            staged_files = staged_result.stdout.strip().split('\n') if staged_result.stdout.strip() else []
            
            # Get diff of staged files
            diff_result = subprocess.run(['git', 'diff', '--cached'], 
                                       cwd=self.current_repo_path,
                                       capture_output=True, text=True, check=True)
            git_diff = diff_result.stdout
            
            # Get repository status for additional context
            status_result = subprocess.run(['git', 'status', '--porcelain'], 
                                         cwd=self.current_repo_path,
                                         capture_output=True, text=True, check=True)
            
            return {
                'branch_name': branch_name,
                'repo_name': repo_name,
                'repo_path': self.current_repo_path,
                'staged_files': staged_files,
                'git_diff': git_diff,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'files_changed': ', '.join(staged_files)
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
        
        return re.sub(r'\{\{(\w+)\}\}', replace_func, text)

    def generate_commit_message(self, git_info):
        """Generate commit message using configured AI provider"""
        provider = self.config.get('API', 'provider')
        system_prompt = self.config.get('PROMPT', 'system_prompt')
        user_prompt = self.replace_placeholders(self.config.get('PROMPT', 'user_prompt'), git_info)
        
        try:
            if provider == 'openai' and self.openai_client:
                return self.generate_openai(system_prompt, user_prompt)
            elif provider == 'anthropic' and self.anthropic_client:
                return self.generate_anthropic(system_prompt, user_prompt)
            elif provider == 'gemini' and self.gemini_model:
                return self.generate_gemini(system_prompt, user_prompt)
            else:
                raise Exception(f"Provider '{provider}' not available or not configured")
        
        except Exception as e:
            raise Exception(f"Error generating commit message: {e}")

    def generate_openai(self, system_prompt, user_prompt):
        """Generate using OpenAI API"""
        if not OPENAI_AVAILABLE:
            raise Exception("OpenAI package not installed. Please install it first.")
            
        model = self.config.get('API', 'model', fallback='gpt-3.5-turbo')
        response = self.openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=200,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()

    def generate_anthropic(self, system_prompt, user_prompt):
        """Generate using Anthropic API"""
        if not ANTHROPIC_AVAILABLE:
            raise Exception("Anthropic package not installed. Please install it first.")
            
        model = self.config.get('API', 'model', fallback='claude-3-haiku-20240307')
        response = self.anthropic_client.messages.create(
            model=model,
            max_tokens=200,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return response.content[0].text.strip()

    def generate_gemini(self, system_prompt, user_prompt):
        """Generate using Gemini API"""
        if not GEMINI_AVAILABLE:
            raise Exception("Google Generative AI package not installed. Please install it first.")
            
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        response = self.gemini_model.generate_content(full_prompt)
        return response.text.strip()

    def setup_gui(self):
        """Setup the GUI window"""
        self.root = tk.Tk()
        self.root.title("AI Git Commit Message Generator")
        self.root.geometry("700x430")  # Fixed window size
        self.root.resizable(False, False)  # Prevent resizing
        
        if self.config.getboolean('GUI', 'always_on_top'):
            self.root.attributes('-topmost', True)
        
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Repository selection frame
        repo_frame = ttk.LabelFrame(main_frame, text="Repository Selection", padding="5")
        repo_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        repo_frame.columnconfigure(1, weight=1)
        
        ttk.Label(repo_frame, text="Repository:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        
        self.repo_var = tk.StringVar()
        self.repo_combo = ttk.Combobox(repo_frame, textvariable=self.repo_var, state="readonly")
        self.repo_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        self.repo_combo.bind('<<ComboboxSelected>>', self.on_repo_selected)
        
        ttk.Button(repo_frame, text="Manage Repos", 
                  command=self.manage_repositories).grid(row=0, column=2, padx=(5, 0))
        
        # Repository info frame
        info_frame = ttk.Frame(main_frame)
        info_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        info_frame.columnconfigure(1, weight=1)
        
        # Create a frame for repo info with refresh button
        repo_info_subframe = ttk.Frame(info_frame)
        repo_info_subframe.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.repo_info_label = ttk.Label(repo_info_subframe, text="No repository selected", foreground="gray")
        self.repo_info_label.pack(side=tk.LEFT)
        
        # Add refresh button with "⟳" as the refresh symbol
        refresh_button = ttk.Button(repo_info_subframe, text="⟳", width=2,
                                    command=self.refresh_repo_status)
        refresh_button.pack(side=tk.LEFT, padx=(5, 0))
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready")
        self.status_label.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(buttons_frame, text="Generate Commit Message", 
                  command=self.generate_clicked).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Configure", 
                  command=self.configure_clicked).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Copy to Clipboard", 
                  command=self.copy_clicked).pack(side=tk.LEFT, padx=(0, 5))
        
        # Create dropdown menu button for terminal/explorer actions
        self.repo_actions_button = ttk.Button(buttons_frame, text="Repository Actions ▼", 
                                             command=self.show_repo_actions_menu)
        self.repo_actions_button.pack(side=tk.LEFT)
        
        # Create the dropdown menu (but don't show it yet)
        self.repo_actions_menu = tk.Menu(buttons_frame, tearoff=0)
        self.repo_actions_menu.add_command(label="Open in Terminal", command=self.open_terminal)
        self.repo_actions_menu.add_command(label="Open in Explorer", command=self.open_in_explorer)
        
        # Text area for commit message
        self.text_area = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=15)
        self.text_area.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))

    def refresh_repositories(self):
        """Refresh the repository dropdown"""
        paths = self.get_repository_paths()
        valid_paths = self.validate_repositories(paths)
        
        # Update dropdown
        self.repo_combo['values'] = [f"{Path(p).name} ({p})" for p in valid_paths]
        
        # Set current selection
        current_repo = self.config.get('REPOSITORIES', 'current_repo', fallback='')
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
            self.config.set('REPOSITORIES', 'current_repo', valid_paths[0])
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
            path = selection[selection.rfind('(') + 1:-1]
            self.current_repo_path = path
            self.config.set('REPOSITORIES', 'current_repo', path)
            self.save_config()
            self.update_repo_info()

    def update_repo_info(self):
        """Update repository information display"""
        if not self.current_repo_path:
            self.repo_info_label.config(text="No repository selected", foreground="gray")
            return
        
        try:
            # Get branch info
            branch_result = subprocess.run(['git', 'branch', '--show-current'], 
                                         cwd=self.current_repo_path,
                                         capture_output=True, text=True, check=True)
            branch = branch_result.stdout.strip()
            
            # Get status
            status_result = subprocess.run(['git', 'status', '--porcelain'], 
                                         cwd=self.current_repo_path,
                                         capture_output=True, text=True, check=True)
            status_lines = status_result.stdout.strip().split('\n') if status_result.stdout.strip() else []
            staged_count = len([line for line in status_lines if line and line[0] in 'AMDR'])
            unstaged_count = len([line for line in status_lines if line and line[1] in 'AMD'])
            
            info_text = f"Branch: {branch} | Staged: {staged_count} | Unstaged: {unstaged_count}"
            self.repo_info_label.config(text=info_text, foreground="black")
            
        except Exception as e:
            self.repo_info_label.config(text=f"Error reading repository: {str(e)}", foreground="red")
    
    def update_api_status(self):
        """Update the API status in the UI"""
        provider = self.config.get('API', 'provider')
        
        if provider == 'openai' and not OPENAI_AVAILABLE:
            self.status_label.config(text="Warning: OpenAI package not installed", foreground="orange")
        elif provider == 'anthropic' and not ANTHROPIC_AVAILABLE:
            self.status_label.config(text="Warning: Anthropic package not installed", foreground="orange")
        elif provider == 'gemini' and not GEMINI_AVAILABLE:
            self.status_label.config(text="Warning: Google Generative AI package not installed", foreground="orange")
        else:
            self.status_label.config(text="Ready", foreground="black")

    def manage_repositories(self):
        """Open repository management window"""
        RepositoryManager(self)

    def open_terminal(self):
        """Open terminal in the current repository directory"""
        if not self.current_repo_path:
            messagebox.showwarning("Warning", "No repository selected")
            return
        
        try:
            if platform.system() == "Windows":
                subprocess.run(["start", "powershell"], cwd=self.current_repo_path, shell=True)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", "-a", "Terminal", self.current_repo_path])
            else:  # Linux
                subprocess.run(["xdg-open", self.current_repo_path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open terminal: {str(e)}")
            
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
            messagebox.showerror("Error", f"Could not open explorer: {str(e)}")

    def generate_clicked(self):
        """Handle generate button click"""
        if not self.current_repo_path:
            messagebox.showwarning("Warning", "Please select a repository first")
            return
        
        def generate_thread():
            try:
                self.update_status("Getting git information...")
                git_info = self.get_git_info()
                
                if not git_info['staged_files'] or not any(git_info['staged_files']):
                    self.update_status("No staged files found")
                    messagebox.showwarning("Warning", "No staged files found. Please stage some files first.")
                    return
                
                self.update_status("Generating commit message...")
                commit_message = self.generate_commit_message(git_info)
                
                self.text_area.delete(1.0, tk.END)
                self.text_area.insert(1.0, commit_message)
                self.update_status("Commit message generated successfully")
                
                # Refresh repo info to show updated status
                self.update_repo_info()
                
            except Exception as e:
                self.update_status(f"Error: {str(e)}")
                messagebox.showerror("Error", str(e))
        
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
            self.update_status("Repository status refreshed")
        else:
            self.update_status("No repository selected")

    def run(self):
        """Start the GUI"""
        # Check if we need to restart after package installation
        if self.restart_needed:
            self.root.destroy()
            python = sys.executable
            os.execl(python, python, *sys.argv)
        else:
            self.root.mainloop()


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
        ttk.Label(main_frame, text="Manage Git Repositories", 
                 font=('TkDefaultFont', 12, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        # Repository list
        list_frame = ttk.LabelFrame(main_frame, text="Configured Repositories", padding="5")
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
        
        ttk.Button(button_frame, text="Add Repository", 
                  command=self.add_repository).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Remove Selected", 
                  command=self.remove_repository).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Validate All", 
                  command=self.validate_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Auto-Detect", 
                  command=self.auto_detect).pack(side=tk.LEFT)
        
        # Close button
        ttk.Button(main_frame, text="Close", 
                  command=self.close_window).pack(side=tk.RIGHT)

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
                    messagebox.showwarning("Warning", "Repository already exists in the list")
            else:
                messagebox.showerror("Error", "Selected folder is not a valid git repository")

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
            messagebox.showinfo("Validation Complete", 
                              f"Removed {removed_count} invalid repository/ies")
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
                messagebox.showinfo("Auto-Detection Complete", 
                                  f"Found and added {len(new_repos)} new repositories")
            else:
                messagebox.showinfo("Auto-Detection Complete", 
                                  "No new repositories found")
        else:
            messagebox.showinfo("Auto-Detection Complete", 
                              "No git repositories found in common locations")

    def close_window(self):
        """Close the repository manager window"""
        self.window.destroy()


class ConfigWindow:
    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent.root)
        self.window.title("Configuration")
        self.window.geometry("800x300")
        self.window.resizable(False, False)  # Prevent resizing
        self.window.transient(parent.root)
        self.window.grab_set()
        
        self.setup_config_gui()

    def setup_config_gui(self):
        """Setup configuration GUI"""
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # API Configuration Tab
        api_frame = ttk.Frame(notebook)
        notebook.add(api_frame, text="API Settings")
        
        # Provider selection
        ttk.Label(api_frame, text="AI Provider:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.provider_var = tk.StringVar(value=self.parent.config.get('API', 'provider'))
        provider_combo = ttk.Combobox(api_frame, textvariable=self.provider_var, 
                                    values=['openai', 'anthropic', 'gemini'])
        provider_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Package installation status
        package_frame = ttk.Frame(api_frame)
        package_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        openai_status = "✓ Installed" if OPENAI_AVAILABLE else "✗ Not installed"
        anthropic_status = "✓ Installed" if ANTHROPIC_AVAILABLE else "✗ Not installed"
        gemini_status = "✓ Installed" if GEMINI_AVAILABLE else "✗ Not installed"
        
        ttk.Label(package_frame, text="Package Status:").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(package_frame, text=f"OpenAI: {openai_status}").grid(row=0, column=1, sticky=tk.W, padx=(10, 5))
        ttk.Label(package_frame, text=f"Anthropic: {anthropic_status}").grid(row=0, column=2, sticky=tk.W, padx=5)
        ttk.Label(package_frame, text=f"Gemini: {gemini_status}").grid(row=0, column=3, sticky=tk.W, padx=5)
        
        if not (OPENAI_AVAILABLE and ANTHROPIC_AVAILABLE and GEMINI_AVAILABLE):
            ttk.Button(package_frame, text="Install Packages", 
                      command=self.install_missing_packages).grid(row=0, column=4, padx=5)
        
        # API Keys
        ttk.Label(api_frame, text="OpenAI API Key:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.openai_key_var = tk.StringVar(value=self.parent.config.get('API', 'openai_api_key'))
        ttk.Entry(api_frame, textvariable=self.openai_key_var, show="*", width=50).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Label(api_frame, text="Anthropic API Key:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.anthropic_key_var = tk.StringVar(value=self.parent.config.get('API', 'anthropic_api_key'))
        ttk.Entry(api_frame, textvariable=self.anthropic_key_var, show="*", width=50).grid(row=3, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Label(api_frame, text="Gemini API Key:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.gemini_key_var = tk.StringVar(value=self.parent.config.get('API', 'gemini_api_key'))
        ttk.Entry(api_frame, textvariable=self.gemini_key_var, show="*", width=50).grid(row=4, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Label(api_frame, text="Model:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_var = tk.StringVar(value=self.parent.config.get('API', 'model'))
        ttk.Entry(api_frame, textvariable=self.model_var, width=50).grid(row=5, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Model suggestions based on provider
        model_info = ttk.Label(api_frame, text="Common models: OpenAI: gpt-3.5-turbo, gpt-4 | Anthropic: claude-3-haiku-20240307 | Gemini: gemini-pro", 
                              font=('TkDefaultFont', 8), foreground='gray')
        model_info.grid(row=6, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)
        
        api_frame.columnconfigure(1, weight=1)
        
        # Prompt Configuration Tab
        prompt_frame = ttk.Frame(notebook)
        notebook.add(prompt_frame, text="Prompt Settings")
        
        ttk.Label(prompt_frame, text="System Prompt:").pack(anchor=tk.W, padx=5, pady=(5, 0))
        self.system_prompt_text = scrolledtext.ScrolledText(prompt_frame, height=8)
        self.system_prompt_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.system_prompt_text.insert(1.0, self.parent.config.get('PROMPT', 'system_prompt'))
        
        ttk.Label(prompt_frame, text="User Prompt (use {{placeholder}} for variables):").pack(anchor=tk.W, padx=5, pady=(5, 0))
        self.user_prompt_text = scrolledtext.ScrolledText(prompt_frame, height=8)
        self.user_prompt_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.user_prompt_text.insert(1.0, self.parent.config.get('PROMPT', 'user_prompt'))
        
        # Available placeholders info
        placeholders_info = """Available placeholders:
{{branch_name}} - Current git branch
{{repo_name}} - Repository name
{{repo_path}} - Full path to repository
{{date}} - Current date and time
{{files_changed}} - List of changed files
{{git_diff}} - Full git diff of staged changes"""
        
        ttk.Label(prompt_frame, text=placeholders_info, font=('TkDefaultFont', 8), foreground='gray').pack(anchor=tk.W, padx=5, pady=5)
        
        # GUI Settings Tab
        gui_frame = ttk.Frame(notebook)
        notebook.add(gui_frame, text="GUI Settings")
        
        self.always_on_top_var = tk.BooleanVar(value=self.parent.config.getboolean('GUI', 'always_on_top'))
        ttk.Checkbutton(gui_frame, text="Always on top", variable=self.always_on_top_var).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save", command=self.save_config).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=self.window.destroy).pack(side=tk.RIGHT)

    def install_missing_packages(self):
        """Install all missing AI API packages"""
        missing_packages = []
        
        if not OPENAI_AVAILABLE:
            missing_packages.append(('openai', 'OpenAI'))
        if not ANTHROPIC_AVAILABLE:
            missing_packages.append(('anthropic', 'Anthropic Claude'))
        if not GEMINI_AVAILABLE:
            missing_packages.append(('google-generativeai', 'Google Gemini'))
            
        if missing_packages:
            self.parent.offer_package_installation(missing_packages)
            self.window.destroy()
        else:
            messagebox.showinfo("Packages", "All API packages are already installed.")

    def save_config(self):
        """Save configuration"""
        # Check if provider changed
        old_provider = self.parent.config.get('API', 'provider')
        new_provider = self.provider_var.get()
        provider_changed = old_provider != new_provider
        
        # Update config
        self.parent.config.set('API', 'provider', new_provider)
        self.parent.config.set('API', 'openai_api_key', self.openai_key_var.get())
        self.parent.config.set('API', 'anthropic_api_key', self.anthropic_key_var.get())
        self.parent.config.set('API', 'gemini_api_key', self.gemini_key_var.get())
        self.parent.config.set('API', 'model', self.model_var.get())
        self.parent.config.set('PROMPT', 'system_prompt', self.system_prompt_text.get(1.0, tk.END).strip())
        self.parent.config.set('PROMPT', 'user_prompt', self.user_prompt_text.get(1.0, tk.END).strip())
        self.parent.config.set('GUI', 'always_on_top', str(self.always_on_top_var.get()))
        
        # Save to file
        self.parent.save_config()
        
        # Reinitialize API clients
        self.parent.setup_api_clients()
        
        # Check required packages if provider changed
        if provider_changed:
            self.window.destroy()
            self.parent.check_required_packages()
        else:
            messagebox.showinfo("Success", "Configuration saved successfully!\nRestart the application for GUI changes to take effect.")
            self.window.destroy()


if __name__ == "__main__":
    app = GitCommitAI()
    app.run()