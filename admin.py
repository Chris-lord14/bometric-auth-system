"""
admin.py
────────
Password-protected Admin Panel GUI.
Allows: view users, delete users, reset PINs,
        unlock accounts, view audit log, export CSV,
        view active sessions, retrain model.
"""

import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, simpledialog
import os
import hashlib
from database import connect_db, reset_failures, save_pin_hash
from audit    import log_action, export_to_csv, get_audit_log
from session  import get_active_sessions, invalidate_session
from train_model import train_model
from pin_auth import prompt_set_pin

# ── Admin PIN (SHA-256 hashed) ────────────────────────────────────────────────
# Default admin password: admin1234
# To change: python -c "import hashlib; print(hashlib.sha256('newpassword'.encode()).hexdigest())"
ADMIN_HASH = hashlib.sha256("admin1234".encode()).hexdigest()


def _check_admin_password() -> bool:
    """Show password dialog. Returns True if correct."""
    win = tk.Toplevel()
    win.title("Admin Access")
    win.geometry("300x180")
    win.config(bg="#0f172a")
    win.grab_set()
    win.resizable(False, False)

    tk.Label(win, text="🛡  Admin Panel", font=("Arial", 13, "bold"),
             fg="white", bg="#0f172a").pack(pady=(18, 4))
    tk.Label(win, text="Enter admin password to continue",
             font=("Arial", 9), fg="#94a3b8", bg="#0f172a").pack()

    entry = tk.Entry(win, font=("Arial", 12), show="●", width=22,
                     bg="#334155", fg="white", insertbackground="white",
                     relief="flat", bd=4)
    entry.pack(pady=12)
    entry.focus()

    result = {"ok": False}
    err_var = tk.StringVar()
    tk.Label(win, textvariable=err_var, font=("Arial", 9),
             fg="#f87171", bg="#0f172a").pack()

    def submit():
        pw = entry.get()
        if hashlib.sha256(pw.encode()).hexdigest() == ADMIN_HASH:
            result["ok"] = True
            log_action("ADMIN_LOGIN", performed_by="ADMIN")
            win.destroy()
        else:
            err_var.set("Wrong password.")
            entry.delete(0, tk.END)

    entry.bind("<Return>", lambda e: submit())
    tk.Button(win, text="Enter", font=("Arial", 11, "bold"),
              bg="#3b82f6", fg="white", width=12, relief="flat",
              command=submit).pack(pady=6)

    win.wait_window()
    return result["ok"]


def _style_tree(tree):
    style = ttk.Style()
    style.theme_use("default")
    style.configure("Treeview", background="#1e293b", foreground="white",
                    fieldbackground="#1e293b", rowheight=26)
    style.configure("Treeview.Heading", background="#334155",
                    foreground="white", font=("Arial", 10, "bold"))
    style.map("Treeview", background=[("selected", "#3b82f6")])


# ── Users Tab ─────────────────────────────────────────────────────────────────
def _build_users_tab(nb):
    frame = tk.Frame(nb, bg="#0f172a")

    cols = ("ID", "Full Name", "Username", "Registered", "PIN Set", "Locked")
    tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
    _style_tree(tree)

    widths = {"ID": 40, "Full Name": 140, "Username": 120,
              "Registered": 155, "PIN Set": 70, "Locked": 70}
    for col in cols:
        tree.heading(col, text=col)
        tree.column(col, width=widths[col], anchor="center")

    tree.tag_configure("locked", background="#450a0a", foreground="#fca5a5")
    tree.tag_configure("no_pin", background="#422006", foreground="#fde68a")

    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)

    def refresh():
        for row in tree.get_children():
            tree.delete(row)
        conn   = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.fullname, u.username, u.date_registered,
                   CASE WHEN u.pin_hash IS NOT NULL THEN 'Yes' ELSE 'No' END,
                   CASE WHEN l.locked_until > datetime('now') THEN 'Yes' ELSE 'No' END
            FROM users u
            LEFT JOIN lockouts l ON l.identifier = 'login'
            ORDER BY u.id DESC
        """)
        for row in cursor.fetchall():
            tag = "locked" if row[5] == "Yes" else ("no_pin" if row[4] == "No" else "")
            tree.insert("", "end", values=row, tags=(tag,))
        conn.close()

    def delete_user():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select User", "Please select a user first.")
            return
        values   = tree.item(sel[0])["values"]
        username = values[2]
        if not messagebox.askyesno("Confirm Delete",
                                   f"Delete user '{username}'?\n\nThis removes their database record and dataset folder."):
            return
        conn   = connect_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        conn.close()

        import shutil
        ds = f"datasets/{username}"
        if os.path.exists(ds):
            shutil.rmtree(ds)

        log_action("USER_DELETED", performed_by="ADMIN", target_user=username)
        refresh()

        # Auto retrain
        ok, msg = train_model()
        if ok:
            messagebox.showinfo("Done", f"User '{username}' deleted.\nModel retrained.")
        else:
            messagebox.showwarning("Deleted", f"User deleted.\nRetraining failed: {msg}")

    def reset_pin():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select User", "Please select a user first.")
            return
        username = tree.item(sel[0])["values"][2]
        pin_hash = prompt_set_pin(username)
        if pin_hash:
            save_pin_hash(username, pin_hash)
            log_action("PIN_RESET", performed_by="ADMIN", target_user=username)
            messagebox.showinfo("PIN Reset", f"PIN for '{username}' updated.")
            refresh()

    def unlock_user():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select User", "Please select a user first.")
            return
        username = tree.item(sel[0])["values"][2]
        reset_failures("login")
        log_action("LOCKOUT_RESET", performed_by="ADMIN", target_user=username,
                   details="Manually unlocked via admin panel")
        messagebox.showinfo("Unlocked", "Account lockout cleared.")
        refresh()

    # Layout
    btn_f = tk.Frame(frame, bg="#0f172a")
    btn_f.pack(fill="x", padx=10, pady=(10, 4))

    updated_var = tk.StringVar(value="")
    tk.Label(btn_f, textvariable=updated_var, font=("Arial", 8),
             fg="#475569", bg="#0f172a").pack(side="right", padx=10)

    original_refresh = refresh
    def refresh():
        original_refresh()
        updated_var.set(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    for text, color, cmd in [
        ("🔄  Refresh",     "#334155", refresh),
        ("🗑  Delete User", "#dc2626", delete_user),
        ("🔑  Reset PIN",   "#7c3aed", reset_pin),
        ("🔓  Unlock",      "#22c55e", unlock_user),
    ]:
        tk.Button(btn_f, text=text, font=("Arial", 10, "bold"),
                  bg=color, fg="white", relief="flat", padx=10, pady=4,
                  command=cmd).pack(side="left", padx=4)

    tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
    sb.pack(side="right", fill="y", padx=(0, 10), pady=(0, 10))

    def auto_refresh_users():
        """Re-run refresh every 5 seconds if the frame still exists."""
        try:
            if frame.winfo_exists():
                refresh()
                frame.after(5000, auto_refresh_users)
        except tk.TclError:
            pass  # window was closed

    refresh()
    frame.after(5000, auto_refresh_users)
    return frame


# ── Audit Tab ─────────────────────────────────────────────────────────────────
def _build_audit_tab(nb):
    frame = tk.Frame(nb, bg="#0f172a")

    cols = ("Timestamp", "Action", "By", "Target", "Details")
    tree = ttk.Treeview(frame, columns=cols, show="headings", height=14)
    _style_tree(tree)

    widths = {"Timestamp": 155, "Action": 160, "By": 100, "Target": 100, "Details": 200}
    for col in cols:
        tree.heading(col, text=col)
        tree.column(col, width=widths[col], anchor="w")

    tree.tag_configure("admin",   background="#1e3a5f", foreground="#93c5fd")
    tree.tag_configure("delete",  background="#450a0a", foreground="#fca5a5")
    tree.tag_configure("success", background="#14532d", foreground="#86efac")

    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)

    def refresh():
        for row in tree.get_children():
            tree.delete(row)
        for entry in get_audit_log(200):
            tag = ("admin"   if "ADMIN"   in entry["action"]
                   else "delete"  if "DELETE"  in entry["action"]
                   else "success" if "SUCCESS" in entry["action"]
                   else "")
            tree.insert("", "end", values=(
                entry["timestamp"], entry["action"],
                entry["performed_by"], entry["target_user"], entry["details"]
            ), tags=(tag,))

    def do_export():
        path = export_to_csv()
        messagebox.showinfo("Exported", f"Audit log exported to:\n{path}")

    btn_f = tk.Frame(frame, bg="#0f172a")
    btn_f.pack(fill="x", padx=10, pady=(10, 4))

    audit_updated_var = tk.StringVar(value="")
    tk.Label(btn_f, textvariable=audit_updated_var, font=("Arial", 8),
             fg="#475569", bg="#0f172a").pack(side="right", padx=10)

    original_refresh = refresh
    def refresh():
        original_refresh()
        audit_updated_var.set(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    for text, color, cmd in [
        ("🔄  Refresh",       "#334155", refresh),
        ("📥  Export CSV",    "#0ea5e9", do_export),
    ]:
        tk.Button(btn_f, text=text, font=("Arial", 10, "bold"),
                  bg=color, fg="white", relief="flat", padx=10, pady=4,
                  command=cmd).pack(side="left", padx=4)

    tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
    sb.pack(side="right", fill="y", padx=(0, 10), pady=(0, 10))

    def auto_refresh_audit():
        try:
            if frame.winfo_exists():
                refresh()
                frame.after(5000, auto_refresh_audit)
        except tk.TclError:
            pass

    refresh()
    frame.after(5000, auto_refresh_audit)
    return frame


# ── Sessions Tab ──────────────────────────────────────────────────────────────
def _build_sessions_tab(nb):
    frame = tk.Frame(nb, bg="#0f172a")

    cols = ("Username", "Created At", "Expires At")
    tree = ttk.Treeview(frame, columns=cols, show="headings", height=14)
    _style_tree(tree)

    for col in cols:
        tree.heading(col, text=col)
        tree.column(col, width=190, anchor="center")

    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)

    # Store token mapping for revoke action
    token_map = {}

    def refresh():
        token_map.clear()
        for row in tree.get_children():
            tree.delete(row)
        conn   = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, created_at, expires_at, token
            FROM sessions WHERE active = 1
            ORDER BY created_at DESC
        """)
        for row in cursor.fetchall():
            iid = tree.insert("", "end", values=row[:3])
            token_map[iid] = row[3]
        conn.close()

    def revoke_session():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a session to revoke.")
            return
        iid   = sel[0]
        token = token_map.get(iid)
        if token:
            invalidate_session(token)
            log_action("SESSION_REVOKED", performed_by="ADMIN",
                       details="Manually revoked via admin panel")
            refresh()

    btn_f = tk.Frame(frame, bg="#0f172a")
    btn_f.pack(fill="x", padx=10, pady=(10, 4))

    sess_updated_var = tk.StringVar(value="")
    tk.Label(btn_f, textvariable=sess_updated_var, font=("Arial", 8),
             fg="#475569", bg="#0f172a").pack(side="right", padx=10)

    original_refresh = refresh
    def refresh():
        original_refresh()
        sess_updated_var.set(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    for text, color, cmd in [
        ("🔄  Refresh",        "#334155", refresh),
        ("❌  Revoke Session", "#dc2626", revoke_session),
    ]:
        tk.Button(btn_f, text=text, font=("Arial", 10, "bold"),
                  bg=color, fg="white", relief="flat", padx=10, pady=4,
                  command=cmd).pack(side="left", padx=4)

    tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
    sb.pack(side="right", fill="y", padx=(0, 10), pady=(0, 10))

    def auto_refresh_sessions():
        try:
            if frame.winfo_exists():
                refresh()
                frame.after(5000, auto_refresh_sessions)
        except tk.TclError:
            pass

    refresh()
    frame.after(5000, auto_refresh_sessions)
    return frame


# ── Main entry point ──────────────────────────────────────────────────────────
def open_admin_panel():
    if not _check_admin_password():
        return

    win = tk.Toplevel()
    win.title("🛡  Admin Panel")
    win.geometry("780x520")
    win.config(bg="#0f172a")
    win.resizable(True, True)

    tk.Label(win, text="🛡  Admin Panel",
             font=("Arial", 15, "bold"), fg="white", bg="#0f172a").pack(pady=(14, 6))

    style = ttk.Style()
    style.theme_use("default")
    style.configure("TNotebook",           background="#0f172a", borderwidth=0)
    style.configure("TNotebook.Tab",       background="#1e293b", foreground="#94a3b8",
                                           padding=[14, 6], font=("Arial", 10))
    style.map("TNotebook.Tab",
              background=[("selected", "#3b82f6")],
              foreground=[("selected", "white")])

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    nb.add(_build_users_tab(nb),    text="👤  Users")
    nb.add(_build_audit_tab(nb),    text="📋  Audit Trail")
    nb.add(_build_sessions_tab(nb), text="🎟  Sessions")