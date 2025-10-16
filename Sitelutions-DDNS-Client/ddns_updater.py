#
# An advanced GUI application for automatically updating Sitelutions DDNS records.
#
# Version 3 Changes:
# - Removed fixed window size for better adaptability.
# - Switched to Sitelutions' own IP service (api2.sitelutions.com/myip).
# - Added support for custom application and tray icons (icon.ico, icon.png).
#
# Author: Alper Akpınar
# Date: 2025-10-16
#

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
import json
import os
import sys
import threading
from datetime import datetime
from PIL import Image
import pystray

# --- Configuration ---
APP_NAME = "SitelutionsDDNSUpdater"
CONFIG_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME)
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
# --- Icon files must be in the same directory as the script/exe ---
ICON_ICO_PATH = "icon.ico"
ICON_PNG_PATH = "icon.png"

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class DDNSUpdaterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sitelutions DDNS Updater")
        # self.root.geometry("550x450") # REMOVED for dynamic sizing

        # Set Window Icon
        try:
            self.root.iconbitmap(resource_path(ICON_ICO_PATH))
        except tk.TclError:
            print(f"Warning: Could not find window icon file: {ICON_ICO_PATH}")
            
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.after_id = None
        self.is_running = False

        self.create_widgets()
        self.load_settings()
        
        self.tray_thread = threading.Thread(target=self.setup_tray_icon, daemon=True)
        self.tray_thread.start()

    # ... (create_widgets and other methods remain the same as before) ...
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        settings_frame.columnconfigure(1, weight=1)

        ttk.Label(settings_frame, text="Record ID:").grid(row=0, column=0, sticky="w", pady=2)
        self.id_entry = ttk.Entry(settings_frame)
        self.id_entry.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(settings_frame, text="Email:").grid(row=1, column=0, sticky="w", pady=2)
        self.email_entry = ttk.Entry(settings_frame)
        self.email_entry.grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(settings_frame, text="API Key:").grid(row=2, column=0, sticky="w", pady=2)
        self.apikey_entry = ttk.Entry(settings_frame, show="*")
        self.apikey_entry.grid(row=2, column=1, sticky="ew", pady=2)

        ttk.Label(settings_frame, text="Update Interval:").grid(row=3, column=0, sticky="w", pady=2)
        self.interval_var = tk.StringVar()
        self.interval_combo = ttk.Combobox(settings_frame, textvariable=self.interval_var, state="readonly")
        self.interval_combo['values'] = ("60 minutes", "4 hours", "6 hours", "24 hours")
        self.interval_combo.grid(row=3, column=1, sticky="ew", pady=2)

        controls_frame = ttk.Frame(main_frame)
        controls_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=10)
        controls_frame.columnconfigure(0, weight=1)
        controls_frame.columnconfigure(1, weight=1)
        controls_frame.columnconfigure(2, weight=1)

        self.start_button = ttk.Button(controls_frame, text="Start Auto-Update", command=self.start_auto_update)
        self.start_button.grid(row=0, column=0, padx=5, sticky="ew")

        self.stop_button = ttk.Button(controls_frame, text="Stop Auto-Update", command=self.stop_auto_update, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=5, sticky="ew")
        
        self.manual_button = ttk.Button(controls_frame, text="Update Now", command=self.perform_update)
        self.manual_button.grid(row=0, column=2, padx=5, sticky="ew")
        
        log_frame = ttk.LabelFrame(main_frame, text="Logs", padding="10")
        log_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        main_frame.rowconfigure(2, weight=1)
        main_frame.columnconfigure(0, weight=1)

        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state="disabled", height=10)
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def log_message(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"
        
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, full_message)
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")

    def perform_update(self):
        record_id = self.id_entry.get()
        email = self.email_entry.get()
        api_key = self.apikey_entry.get()

        if not all([record_id, email, api_key]):
            self.log_message("ERROR: Record ID, Email, and API Key fields are required.")
            return

        # UPDATED to use Sitelutions' IP service
        self.log_message("Fetching public IP address from api2.sitelutions.com/myip...")
        try:
            public_ip = requests.get('https://api2.sitelutions.com/myip', timeout=10).text.strip()
            self.log_message(f"Public IP found: {public_ip}")
        except requests.RequestException as e:
            self.log_message(f"ERROR: Could not get public IP. Details: {e}")
            return

        self.log_message("Sending DNS update request to Sitelutions API...")
        base_url = "https://api2.sitelutions.com/dnsup"
        params = {'user': email, 'pass': api_key, 'id': record_id, 'ip': public_ip, 'ttl': '60'}

        try:
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            response_text = response.text.strip()
            self.log_message(f"SUCCESS: Server Response: {response_text}")
        except requests.RequestException as e:
            self.log_message(f"ERROR: API request failed. Details: {e}")

    # --- System Tray Functions ---
    def setup_tray_icon(self):
        try:
            # UPDATED to load icon from file
            icon_image = Image.open(resource_path(ICON_PNG_PATH))
        except FileNotFoundError:
            print(f"Warning: Could not find tray icon file: {ICON_PNG_PATH}. Using a default icon.")
            # Create a simple default icon if the file is not found
            icon_image = Image.new('RGB', (64, 64), "orange")
            dc = ImageDraw.Draw(icon_image)
            dc.rectangle((16, 16, 48, 48), fill="blue")
            
        menu = (pystray.MenuItem('Show', self.show_window, default=True),
                pystray.MenuItem('Exit', self.exit_app))
        self.tray_icon = pystray.Icon("ddns_updater", icon_image, "DDNS Updater", menu)
        self.tray_icon.run()

    # --- Other methods (auto_update_loop, start_auto_update, stop_auto_update, etc.) ---
    # These methods are unchanged from the previous version. For brevity, they are not repeated.
    # Just copy them from the previous code block.
    # ...
    def auto_update_loop(self):
        self.perform_update()
        interval_ms = self.get_interval_ms()
        if interval_ms > 0 and self.is_running:
            self.after_id = self.root.after(interval_ms, self.auto_update_loop)

    def start_auto_update(self):
        if not self.interval_var.get():
            self.log_message("ERROR: Please select an update interval.")
            return
        self.is_running = True
        self.set_controls_state("running")
        self.save_settings()
        self.log_message(f"Automatic updates started with interval: {self.interval_var.get()}.")
        self.auto_update_loop()

    def stop_auto_update(self):
        self.is_running = False
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.set_controls_state("stopped")
        self.log_message("Automatic updates stopped.")

    def set_controls_state(self, state):
        if state == "running":
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.manual_button.config(state="disabled")
            self.id_entry.config(state="disabled")
            self.email_entry.config(state="disabled")
            self.apikey_entry.config(state="disabled")
            self.interval_combo.config(state="disabled")
        else: # stopped
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")
            self.manual_button.config(state="normal")
            self.id_entry.config(state="normal")
            self.email_entry.config(state="normal")
            self.apikey_entry.config(state="normal")
            self.interval_combo.config(state="readonly")

    def get_interval_ms(self):
        interval_map = { "60 minutes": 3600000, "4 hours": 14400000, "6 hours": 21600000, "24 hours": 86400000 }
        return interval_map.get(self.interval_var.get(), 0)

    def save_settings(self):
        settings = { "record_id": self.id_entry.get(), "email": self.email_entry.get(), "api_key": self.apikey_entry.get(), "interval": self.interval_var.get() }
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f: json.dump(settings, f)
        self.log_message("Settings saved.")

    def load_settings(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    settings = json.load(f)
                    self.id_entry.insert(0, settings.get("record_id", ""))
                    self.email_entry.insert(0, settings.get("email", ""))
                    self.apikey_entry.insert(0, settings.get("api_key", ""))
                    interval = settings.get("interval", "")
                    if interval in self.interval_combo['values']: self.interval_var.set(interval)
                self.log_message("Settings loaded successfully.")
        except Exception as e:
            self.log_message(f"Could not load settings file. {e}")
            
    def show_window(self): self.root.deiconify()
    def hide_window(self): self.root.withdraw()
    def exit_app(self):
        if self.is_running: self.stop_auto_update()
        if hasattr(self, 'tray_icon') and self.tray_icon.visible: self.tray_icon.stop()
        self.root.quit() # Use quit instead of destroy for cleaner exit

if __name__ == "__main__":
    from PIL import Image, ImageDraw # Add ImageDraw here for the default icon case
    root = tk.Tk()
    app = DDNSUpdaterApp(root)
    root.mainloop()