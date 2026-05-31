"""Tkinter signup/login window.

Returns the username on success, or None if the user closed the window.

The login window owns the NetworkClient: it does the handshake, then sends
SIGNUP or LOGIN messages and waits for the matching result. After a
successful login it hands the connected NetworkClient off to the caller.
"""

import tkinter as tk
from tkinter import ttk

from shared import protocol as P
from shared.protocol import make_message

from client.network import NetworkClient


class LoginWindow:
    """Simple tkinter window with username/password fields and two buttons."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Codenames — Login")
        self.root.geometry("360x360")
        self.root.resizable(True, True)

        self.network = None       # set after successful connect()
        self.username = None      # set after successful login
        self._waiting_for = None  # "SIGNUP" or "LOGIN" while a request is pending

        self._build_ui()
        self._connect_to_server()

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Codenames", font=("Helvetica", 18, "bold")).pack(pady=(0, 12))

        ttk.Label(frame, text="Username:").pack(anchor="w")
        self.username_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.username_var).pack(fill="x", pady=(2, 8))

        ttk.Label(frame, text="Password:").pack(anchor="w")
        self.password_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.password_var, show="*").pack(fill="x", pady=(2, 8))

        button_row = ttk.Frame(frame)
        button_row.pack(pady=8)
        ttk.Button(button_row, text="Sign up", command=self._on_signup).pack(side="left", padx=4)
        ttk.Button(button_row, text="Log in", command=self._on_login).pack(side="left", padx=4)

        self.status_var = tk.StringVar(value="Connecting...")
        ttk.Label(frame, textvariable=self.status_var, foreground="#555").pack(pady=(8, 0))

    def _connect_to_server(self):
        self.status_var.set("Generating keys + connecting...")
        # Tkinter normally would freeze here, but key gen + TCP connect is
        # fast enough on localhost that we do it inline for simplicity.
        # ~1-2 seconds.
        self.root.update_idletasks()
        try:
            self.network = NetworkClient()
            self.network.connect()
            self.status_var.set("Connected. Sign up or log in.")
        except Exception as exc:
            self.status_var.set(f"Connection failed: {exc}")

    # -- button handlers ---------------------------------------------------

    def _on_signup(self):
        if not self._ready():
            return
        self._waiting_for = P.SIGNUP
        self.status_var.set("Signing up...")
        self.network.send(make_message(
            P.SIGNUP, username=self.username_var.get(), password=self.password_var.get()))

    def _on_login(self):
        if not self._ready():
            return
        self._waiting_for = P.LOGIN
        self.status_var.set("Logging in...")
        self.network.send(make_message(
            P.LOGIN, username=self.username_var.get(), password=self.password_var.get()))

    def _ready(self):
        if self.network is None or self.network.error is not None:
            self.status_var.set("Not connected — try restarting the client.")
            return False
        return True

    # -- poll loop ---------------------------------------------------------

    def _poll(self):
        """Drain the incoming queue and react to results."""
        if self.network is not None:
            while True:
                msg = self.network.get_message()
                if msg is None:
                    break
                self._handle_message(msg)
            if self.network.error is not None:
                self.status_var.set(f"Disconnected: {self.network.error}")

        self.root.after(50, self._poll)

    def _handle_message(self, msg):
        msg_type = msg.get("type")
        data = msg.get("data", {}) or {}

        if msg_type == P.SIGNUP_RESULT:
            if data.get("ok"):
                self.status_var.set("Account created! You can now log in.")
            else:
                self.status_var.set(f"Sign up failed: {data.get('error')}")
            self._waiting_for = None

        elif msg_type == P.LOGIN_RESULT:
            if data.get("ok"):
                self.username = self.username_var.get().strip()
                self.status_var.set(f"Welcome, {self.username}!")
                self.root.after(150, self.root.destroy)
            else:
                self.status_var.set(f"Login failed: {data.get('error')}")
            self._waiting_for = None

        elif msg_type == P.ERROR:
            self.status_var.set(f"Server error: {data.get('message')}")

    # -- run ---------------------------------------------------------------

    def run(self):
        """Show the window. Returns (username, network) or (None, None)."""
        self.root.after(50, self._poll)
        self.root.mainloop()
        if self.username is None:
            # User closed the window before logging in.
            if self.network is not None:
                self.network.close()
            return None, None
        return self.username, self.network
