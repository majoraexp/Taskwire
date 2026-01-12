import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import threading
import os
import sys
import shutil
import time
import random
import ctypes

class SetupWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Taskwire Setup")
        self.geometry("600x450")
        self.resizable(False, False)
        
        # --- THEME CONFIGURATION ---
        self.bg_color = "#121212"
        self.fg_color = "#ffffff"
        self.widget_bg = "#1e1e2e"
        self.accent_color = "#bd93f9"
        
        self.configure(bg=self.bg_color)
        
        # Apply Dark Mode to Title Bar (Windows 10/11)
        try:
            # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.windll.user32.GetParent(self.winfo_id()), 
                20, 
                ctypes.byref(ctypes.c_int(2)), 
                4
            )
        except Exception:
            pass

        # Set Icon
        icon_path = "app_icon.png"
        if hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, icon_path)
        
        if os.path.exists(icon_path):
            try:
                icon_img = tk.PhotoImage(file=icon_path)
                self.iconphoto(False, icon_img)
            except Exception:
                pass

        # Configure Styles
        self.style = ttk.Style()
        self.style.theme_use('clam') # 'clam' allows better color customization than 'vista'
        
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("TLabel", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground=self.accent_color)
        
        self.style.configure("TButton", 
            background=self.widget_bg, 
            foreground=self.fg_color, 
            borderwidth=0, 
            focuscolor=self.accent_color
        )
        self.style.map("TButton", 
            background=[("active", self.accent_color), ("disabled", "#333333")],
            foreground=[("active", "#000000"), ("disabled", "#888888")]
        )
        
        self.style.configure("Horizontal.TProgressbar", 
            background=self.accent_color, 
            troughcolor=self.widget_bg,
            borderwidth=0
        )

        # Variables
        self.current_step = 0
        self.is_running = False
        
        # Container
        self.container = ttk.Frame(self, padding=20)
        self.container.pack(fill=tk.BOTH, expand=True)
        
        # Header
        self.header_lbl = ttk.Label(self.container, text="Taskwire Installer", style="Header.TLabel")
        self.header_lbl.pack(pady=(0, 20), anchor="w")
        
        # Content Area
        self.content_frame = ttk.Frame(self.container)
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Footer (Buttons)
        self.footer = ttk.Frame(self.container)
        self.footer.pack(fill=tk.X, pady=(20, 0))
        
        self.btn_next = ttk.Button(self.footer, text="Install", command=self.start_installation)
        self.btn_next.pack(side=tk.RIGHT)
        
        self.btn_cancel = ttk.Button(self.footer, text="Cancel", command=self.destroy)
        self.btn_cancel.pack(side=tk.RIGHT, padx=10)
        
        # Initial View
        self.show_welcome()

    def show_welcome(self):
        lbl = ttk.Label(self.content_frame, text=(
            "Welcome to the Taskwire Setup Wizard.\n\n"
            "This installer will:\n"
            "1. Set up a secure Python environment.\n"
            "2. Install necessary dependencies.\n"
            "3. Compile the application executable.\n"
            "4. Configure hardware sensors (LibreHardwareMonitor).\n\n"
            "Click 'Install' to begin."
        ), wraplength=550)
        lbl.pack(anchor="nw", pady=10)

    def show_progress(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
            
        self.btn_next.config(state=tk.DISABLED)
        self.btn_cancel.config(state=tk.DISABLED)
        
        self.status_lbl = ttk.Label(self.content_frame, text="Preparing...")
        self.status_lbl.pack(anchor="w", pady=(0, 5))
        
        self.progress = ttk.Progressbar(self.content_frame, mode='determinate', length=550, style="Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(0, 15))
        
        # Customizing Text Area Colors
        self.log_area = scrolledtext.ScrolledText(
            self.content_frame, 
            height=12, 
            font=("Consolas", 9),
            bg=self.widget_bg,
            fg=self.fg_color,
            insertbackground=self.fg_color, # Cursor color
            relief=tk.FLAT
        )
        self.log_area.pack(fill=tk.BOTH, expand=True)
        self.log_area.tag_config("err", foreground="#ff5555") # Red
        self.log_area.tag_config("succ", foreground="#50fa7b") # Green

    def log(self, msg, tag=None):
        self.log_area.insert(tk.END, msg + "\n", tag)
        self.log_area.see(tk.END)
        self.status_lbl.config(text=msg)

    def start_installation(self):
        self.show_progress()
        self.progress['value'] = 0
        threading.Thread(target=self.run_install_steps, daemon=True).start()

    def run_command(self, cmd, shell=False):
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, # Merge stderr into stdout
                text=True, 
                shell=shell,
                startupinfo=startupinfo,
                cwd=os.getcwd(),
                bufsize=1, # Line buffered
                universal_newlines=True
            )
            
            # Read output line by line as it comes
            for line in process.stdout:
                self.log(line.strip())
                # Force UI update to keep it responsive
                self.update_idletasks()
            
            process.wait()
            
            if process.returncode != 0:
                self.log(f"Error: Process exited with code {process.returncode}", "err")
                return False
            return True
        except Exception as e:
            self.log(f"Exception: {e}", "err")
            return False

    def run_install_steps(self):
        try:
            # 1. Kill LHM
            self.progress['value'] = 5
            self.log("Step 1/5: Stopping background sensors...")
            ps_cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", "kill_lhm.ps1"]
            if not self.run_command(ps_cmd):
                self.log("Warning: Could not stop background sensors. Build might fail if files are locked.", "err")
            self.progress['value'] = 15

            # 2. Clean Build
            self.log("Step 2/5: Cleaning build directories...")
            
            def safe_clean(folder):
                if os.path.exists(folder):
                    self.log(f"Cleaning {folder}...")
                    trash_name = f"{folder}_trash_{random.randint(1000, 9999)}"
                    try:
                        os.rename(folder, trash_name)
                        # Try to delete trash in background (fire and forget)
                        subprocess.Popen(f"rmdir /s /q {trash_name}", shell=True)
                    except OSError:
                        self.log(f"Could not rename/delete '{folder}'. Files locked by Kernel. Please Reboot.", "err")
                        return False
                return True

            if not safe_clean("build"): return
            if not safe_clean("dist"): return
            self.progress['value'] = 30

            # 3. Venv
            self.log("Step 3/5: Setting up Python Virtual Environment...")
            if not os.path.exists("venv"):
                if not self.run_command([sys.executable, "-m", "venv", "venv"]):
                    self.log("Failed to create venv", "err")
                    return
            self.progress['value'] = 50

            # 4. Requirements
            self.log("Step 4/5: Installing dependencies...")
            pip_exe = os.path.join("venv", "Scripts", "pip.exe")
            if not self.run_command([pip_exe, "install", "--upgrade", "pip"]): return
            if not self.run_command([pip_exe, "install", "-r", "requirements.txt"]): return
            if not self.run_command([pip_exe, "install", "pyinstaller"]): return
            self.progress['value'] = 75

            # 5. Build
            self.log("Step 5/5: Compiling executable (This may take a minute)...")
            pyinstaller_exe = os.path.join("venv", "Scripts", "pyinstaller.exe")
            build_cmd = [
                pyinstaller_exe, "--noconfirm", "--onedir", "--windowed", 
                "--uac-admin", "--name", "Taskwire", 
                "--icon", "app_icon.png", 
                "--add-data", "app_icon.png;.", 
                "main.py"
            ]
            if not self.run_command(build_cmd):
                self.log("Build Failed!", "err")
                return
            self.progress['value'] = 95

            self.installation_complete()

        except Exception as e:
            self.log(f"Critical Error: {e}", "err")
            self.progress.stop()

    def installation_complete(self):
        self.progress['value'] = 100
        self.log("Installation Complete!", "succ")
        self.btn_next.config(text="Launch Taskwire", command=self.launch_app, state=tk.NORMAL)
        self.btn_cancel.config(text="Exit", state=tk.NORMAL)
        messagebox.showinfo("Success", "Taskwire has been installed successfully.")

    def launch_app(self):
        try:
            # Use absolute path to avoid cwd issues
            exe_path = os.path.abspath(os.path.join("dist", "Taskwire", "Taskwire.exe"))
            cwd_path = os.path.dirname(exe_path)
            
            if os.path.exists(exe_path):
                self.log(f"Launching (Elevated): {exe_path}")
                
                # Use ShellExecute with 'runas' to prompt UAC
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None, 
                    "runas", 
                    exe_path, 
                    None, 
                    cwd_path, 
                    1 # SW_SHOWNORMAL
                )
                
                if ret > 32: # Success
                    self.destroy()
                else:
                    messagebox.showerror("Launch Error", f"Failed to launch app. ShellExecute returned {ret}.")
            else:
                messagebox.showerror("Error", f"Executable not found at:\n{exe_path}")
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to launch app: {e}")

if __name__ == "__main__":
    if not os.path.exists("main.py"):
        messagebox.showerror("Error", "main.py not found.\nPlease run this from the source directory.")
    else:
        app = SetupWizard()
        app.mainloop()