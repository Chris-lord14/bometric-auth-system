import tkinter as tk
from tkinter import messagebox, ttk
import os
from database import create_tables, connect_db
from register import register_user
from train_model import train_model
from login import login_user

create_tables()

# ── Main Window ───────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("Smart Biometric Authentication System")
root.geometry("540x520")
root.config(bg="#0f172a")
root.resizable(False, False)

# ── Title ─────────────────────────────────────────────────────────────────────
tk.Label(root, text="Smart Biometric Authentication",
         font=("Arial", 17, "bold"), fg="white", bg="#0f172a").pack(pady=(22, 2))
tk.Label(root, text="Face Recognition  •  Liveness Detection  •  PIN MFA  •  Lockout Protection",
         font=("Arial", 8), fg="#475569", bg="#0f172a").pack(pady=(0, 14))

# ── Input Frame ───────────────────────────────────────────────────────────────
input_frame = tk.Frame(root, bg="#1e293b", pady=12, padx=20)
input_frame.pack(padx=30, fill="x")

tk.Label(input_frame, text="Full Name:", font=("Arial", 11),
         fg="#e2e8f0", bg="#1e293b").grid(row=0, column=0, sticky="w", pady=8)
fullname_entry = tk.Entry(input_frame, font=("Arial", 11), width=28,
                          bg="#334155", fg="white", insertbackground="white",
                          relief="flat", bd=4)
fullname_entry.grid(row=0, column=1, pady=8, padx=(10, 0))

tk.Label(input_frame, text="Username:", font=("Arial", 11),
         fg="#e2e8f0", bg="#1e293b").grid(row=1, column=0, sticky="w", pady=8)
username_entry = tk.Entry(input_frame, font=("Arial", 11), width=28,
                          bg="#334155", fg="white", insertbackground="white",
                          relief="flat", bd=4)
username_entry.grid(row=1, column=1, pady=8, padx=(10, 0))

# ── Status Label ──────────────────────────────────────────────────────────────
status_var = tk.StringVar(value="Ready.")
status_label = tk.Label(root, textvariable=status_var, font=("Arial", 10),
                        fg="#94a3b8", bg="#0f172a", wraplength=480, justify="center")
status_label.pack(pady=(10, 0))

# ── Handlers ──────────────────────────────────────────────────────────────────
def set_status(msg, color="#94a3b8"):
    status_var.set(msg)
    status_label.config(fg=color)
    root.update_idletasks()

def handle_register():
    fullname = fullname_entry.get().strip()
    username = username_entry.get().strip()
    set_status("Opening camera for registration...", "#facc15")
    success, msg = register_user(fullname, username)
    if success:
        set_status(msg, "#22c55e")
        messagebox.showinfo("Registration Successful", msg)
    else:
        set_status(msg, "#f87171")
        messagebox.showerror("Registration Failed", msg)

def handle_train():
    set_status("Training model, please wait...", "#facc15")
    success, msg = train_model()
    if success:
        set_status(msg, "#22c55e")
        messagebox.showinfo("Training Complete", msg)
    else:
        set_status(msg, "#f87171")
        messagebox.showerror("Training Failed", msg)

def handle_login():
    set_status("Starting login sequence...", "#facc15")
    success, msg = login_user()
    if success:
        set_status(msg, "#22c55e")
        messagebox.showinfo("Login Successful", msg)
    else:
        set_status(msg, "#f87171")
        messagebox.showerror("Login Failed", msg)

def show_logs():
    log_win = tk.Toplevel(root)
    log_win.title("Access Logs")
    log_win.geometry("680x380")
    log_win.config(bg="#0f172a")

    tk.Label(log_win, text="Access Logs", font=("Arial", 13, "bold"),
             fg="white", bg="#0f172a").pack(pady=10)

    cols = ("Timestamp", "Username", "Status", "Confidence")
    tree = ttk.Treeview(log_win, columns=cols, show="headings", height=16)

    style = ttk.Style()
    style.theme_use("default")
    style.configure("Treeview", background="#1e293b", foreground="white",
                    fieldbackground="#1e293b", rowheight=24)
    style.configure("Treeview.Heading", background="#334155", foreground="white")
    style.map("Treeview", background=[("selected", "#3b82f6")])

    widths = {"Timestamp": 165, "Username": 140, "Status": 160, "Confidence": 100}
    for col in cols:
        tree.heading(col, text=col)
        tree.column(col, width=widths[col], anchor="center")

    # Colour-code rows
    tree.tag_configure("success",  background="#14532d", foreground="#86efac")
    tree.tag_configure("fail",     background="#450a0a", foreground="#fca5a5")
    tree.tag_configure("intruder", background="#431407", foreground="#fdba74")
    tree.tag_configure("warn",     background="#422006", foreground="#fde68a")

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, username, status, confidence
        FROM logs ORDER BY id DESC LIMIT 100
    """)
    for row in cursor.fetchall():
        status = row[2]
        tag = ("success" if status == "SUCCESS"
               else "intruder" if status == "INTRUDER"
               else "warn" if status in ("LIVENESS_FAIL", "WRONG_PIN", "NO_PIN")
               else "fail")
        tree.insert("", "end",
                    values=(row[0], row[1], status, f"{row[3]:.1f}%"),
                    tags=(tag,))
    conn.close()

    tree.pack(padx=10, pady=5, fill="both", expand=True)


def show_intruders():
    """Show thumbnails of intruder snapshots."""
    from tkinter import PhotoImage
    import glob

    snaps = sorted(glob.glob("intruders/intruder_*.jpg"), reverse=True)

    win = tk.Toplevel(root)
    win.title("Intruder Snapshots")
    win.geometry("500x420")
    win.config(bg="#0f172a")

    tk.Label(win, text=f"Intruder Snapshots ({len(snaps)} found)",
             font=("Arial", 13, "bold"), fg="white", bg="#0f172a").pack(pady=10)

    if not snaps:
        tk.Label(win, text="No intruder snapshots recorded.",
                 font=("Arial", 11), fg="#94a3b8", bg="#0f172a").pack(pady=40)
        return

    canvas = tk.Canvas(win, bg="#0f172a", highlightthickness=0)
    scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
    frame = tk.Frame(canvas, bg="#0f172a")

    frame.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True, padx=10)
    scrollbar.pack(side="right", fill="y")

    # Keep references so images aren't GC'd
    win._imgs = []

    try:
        import cv2
        from PIL import Image, ImageTk
        USE_PIL = True
    except ImportError:
        USE_PIL = False

    for i, path in enumerate(snaps[:20]):   # show latest 20
        ts = os.path.basename(path).replace("intruder_", "").replace(".jpg", "")
        ts_fmt = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}  {ts[9:11]}:{ts[11:13]}:{ts[13:15]}"

        row_f = tk.Frame(frame, bg="#1e293b", pady=6, padx=10)
        row_f.pack(fill="x", pady=4, padx=6)

        if USE_PIL:
            import cv2
            img = cv2.imread(path)
            img = cv2.resize(img, (96, 72))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img)
            tk_img  = ImageTk.PhotoImage(pil_img)
            win._imgs.append(tk_img)
            tk.Label(row_f, image=tk_img, bg="#1e293b").pack(side="left", padx=(0, 10))

        tk.Label(row_f, text=f"🚨  {ts_fmt}", font=("Arial", 10),
                 fg="#fdba74", bg="#1e293b").pack(side="left", anchor="w")


# ── Buttons ───────────────────────────────────────────────────────────────────
btn_frame = tk.Frame(root, bg="#0f172a")
btn_frame.pack(pady=22)

buttons = [
    ("📷  Register",    "#22c55e", handle_register,  0, 0),
    ("🧠  Train Model", "#3b82f6", handle_train,     0, 1),
    ("🔐  Login",       "#f97316", handle_login,     1, 0),
    ("📋  View Logs",   "#8b5cf6", show_logs,        1, 1),
    ("🚨  Intruders",   "#dc2626", show_intruders,   2, 0),
]

for text, color, cmd, row, col in buttons:
    span = 2 if (text == "🚨  Intruders") else 1
    tk.Button(btn_frame, text=text, font=("Arial", 11, "bold"),
              bg=color, fg="white", width=16, relief="flat", cursor="hand2",
              command=cmd).grid(row=row, column=col, padx=10, pady=6,
                                columnspan=span if span > 1 else 1)

# ── Security badges ───────────────────────────────────────────────────────────
badge_frame = tk.Frame(root, bg="#0f172a")
badge_frame.pack(pady=(4, 0))

badges = [
    ("👁  Liveness", "#0f4c75"),
    ("🔑  PIN MFA",  "#1a3a1a"),
    ("🔒  Lockout",  "#3b1f0f"),
    ("📸  Snapshots","#2d1515"),
]
for label, bg in badges:
    tk.Label(badge_frame, text=label, font=("Arial", 8, "bold"),
             fg="#cbd5e1", bg=bg, padx=6, pady=3,
             relief="flat").pack(side="left", padx=4)

# ── Footer ────────────────────────────────────────────────────────────────────
tk.Label(root, text="Biometric Authentication System v2  |  Python + OpenCV",
         font=("Arial", 8), fg="#475569", bg="#0f172a").pack(side="bottom", pady=10)

root.mainloop()