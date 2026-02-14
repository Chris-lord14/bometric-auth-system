import tkinter as tk
from tkinter import messagebox
import hashlib
import os

# We use hashlib (built-in) so no extra install needed.
# SHA-256 + random salt stored alongside the hash.

SEPARATOR = "$"   # salt$hash stored in DB


def _hash_pin(pin: str, salt: str = None) -> str:
    """Returns 'salt$sha256hash' string."""
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.sha256((salt + pin).encode()).hexdigest()
    return f"{salt}{SEPARATOR}{digest}"


def verify_pin(pin: str, stored: str) -> bool:
    """Verify a plain PIN against a stored 'salt$hash' value."""
    try:
        salt, _ = stored.split(SEPARATOR, 1)
        return _hash_pin(pin, salt) == stored
    except Exception:
        return False


def prompt_set_pin(username: str) -> str | None:
    """
    Opens a Tkinter dialog for the user to set a 4–8 digit PIN.
    Returns the hashed PIN string, or None if cancelled.
    """
    result = {"hash": None}

    win = tk.Toplevel()
    win.title("Set Your PIN")
    win.geometry("320x260")
    win.config(bg="#0f172a")
    win.grab_set()
    win.resizable(False, False)

    tk.Label(win, text=f"Set PIN for '{username}'",
             font=("Arial", 13, "bold"), fg="white", bg="#0f172a").pack(pady=(18, 4))
    tk.Label(win, text="Enter a 4–8 digit PIN",
             font=("Arial", 10), fg="#94a3b8", bg="#0f172a").pack(pady=(0, 12))

    frame = tk.Frame(win, bg="#1e293b", padx=16, pady=12)
    frame.pack(padx=20, fill="x")

    tk.Label(frame, text="PIN:", font=("Arial", 11), fg="#e2e8f0", bg="#1e293b").grid(
        row=0, column=0, sticky="w", pady=6)
    pin_entry = tk.Entry(frame, font=("Arial", 12), width=18, show="●",
                         bg="#334155", fg="white", insertbackground="white", relief="flat", bd=4)
    pin_entry.grid(row=0, column=1, pady=6, padx=(8, 0))
    pin_entry.focus()

    tk.Label(frame, text="Confirm:", font=("Arial", 11), fg="#e2e8f0", bg="#1e293b").grid(
        row=1, column=0, sticky="w", pady=6)
    confirm_entry = tk.Entry(frame, font=("Arial", 12), width=18, show="●",
                             bg="#334155", fg="white", insertbackground="white", relief="flat", bd=4)
    confirm_entry.grid(row=1, column=1, pady=6, padx=(8, 0))

    err_var = tk.StringVar()
    tk.Label(win, textvariable=err_var, font=("Arial", 9),
             fg="#f87171", bg="#0f172a").pack()

    def on_confirm():
        pin = pin_entry.get().strip()
        confirm = confirm_entry.get().strip()

        if not pin.isdigit():
            err_var.set("PIN must contain digits only.")
            return
        if not (4 <= len(pin) <= 8):
            err_var.set("PIN must be 4–8 digits.")
            return
        if pin != confirm:
            err_var.set("PINs do not match.")
            return

        result["hash"] = _hash_pin(pin)
        win.destroy()

    def on_cancel():
        win.destroy()

    btn_f = tk.Frame(win, bg="#0f172a")
    btn_f.pack(pady=10)
    tk.Button(btn_f, text="Set PIN", font=("Arial", 11, "bold"),
              bg="#22c55e", fg="white", width=10, relief="flat",
              command=on_confirm).grid(row=0, column=0, padx=8)
    tk.Button(btn_f, text="Cancel", font=("Arial", 11, "bold"),
              bg="#64748b", fg="white", width=10, relief="flat",
              command=on_cancel).grid(row=0, column=1, padx=8)

    confirm_entry.bind("<Return>", lambda e: on_confirm())
    win.wait_window()
    return result["hash"]


def prompt_verify_pin(username: str, stored_hash: str, attempts_left: int = 3) -> bool:
    """
    Opens a Tkinter dialog asking user to enter their PIN.
    Returns True if correct, False otherwise.
    """
    result = {"ok": False}

    win = tk.Toplevel()
    win.title("Enter PIN")
    win.geometry("300x230")
    win.config(bg="#0f172a")
    win.grab_set()
    win.resizable(False, False)

    tk.Label(win, text="PIN Verification",
             font=("Arial", 13, "bold"), fg="white", bg="#0f172a").pack(pady=(18, 4))
    tk.Label(win, text=f"Welcome, {username}. Enter your PIN to continue.",
             font=("Arial", 9), fg="#94a3b8", bg="#0f172a", wraplength=260).pack(pady=(0, 10))

    frame = tk.Frame(win, bg="#1e293b", padx=16, pady=12)
    frame.pack(padx=20, fill="x")

    tk.Label(frame, text="PIN:", font=("Arial", 11), fg="#e2e8f0", bg="#1e293b").grid(
        row=0, column=0, sticky="w")
    pin_entry = tk.Entry(frame, font=("Arial", 13), width=16, show="●",
                         bg="#334155", fg="white", insertbackground="white", relief="flat", bd=4)
    pin_entry.grid(row=0, column=1, padx=(8, 0))
    pin_entry.focus()

    err_var = tk.StringVar(value=f"Attempts remaining: {attempts_left}")
    err_label = tk.Label(win, textvariable=err_var, font=("Arial", 9),
                         fg="#facc15", bg="#0f172a")
    err_label.pack(pady=6)

    remaining = {"count": attempts_left}

    def on_submit():
        pin = pin_entry.get().strip()
        if verify_pin(pin, stored_hash):
            result["ok"] = True
            win.destroy()
        else:
            remaining["count"] -= 1
            pin_entry.delete(0, tk.END)
            if remaining["count"] <= 0:
                err_var.set("Too many wrong attempts.")
                err_label.config(fg="#f87171")
                win.after(1000, win.destroy)
            else:
                err_var.set(f"Wrong PIN. Attempts remaining: {remaining['count']}")
                err_label.config(fg="#f87171")

    def on_cancel():
        win.destroy()

    btn_f = tk.Frame(win, bg="#0f172a")
    btn_f.pack(pady=8)
    tk.Button(btn_f, text="Confirm", font=("Arial", 11, "bold"),
              bg="#f97316", fg="white", width=10, relief="flat",
              command=on_submit).grid(row=0, column=0, padx=8)
    tk.Button(btn_f, text="Cancel", font=("Arial", 11, "bold"),
              bg="#64748b", fg="white", width=10, relief="flat",
              command=on_cancel).grid(row=0, column=1, padx=8)

    pin_entry.bind("<Return>", lambda e: on_submit())
    win.wait_window()
    return result["ok"]