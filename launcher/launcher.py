#!/usr/bin/env python3
"""Small cross-platform Sonic Shuffle launcher.

This is the player-facing launcher. It deliberately knows only about the original
disc image and the native executable; it has no extension or patch loading path.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

EXPECTED_SHA1 = "1a3b3633ac9f54168246f14828621b14ceceb2c0"


def root_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def settings_file() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library/Application Support/SonicShuffle"
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SonicShuffle"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sonicshuffle"
    base.mkdir(parents=True, exist_ok=True)
    return base / "launcher.json"


def load_settings() -> dict:
    try:
        return json.loads(settings_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    settings_file().write_text(json.dumps(data, indent=2), encoding="utf-8")


def sha1_boot(image: Path) -> str | None:
    # Full disc verification is performed by dreamcomp setup. This lightweight check only
    # confirms that a selected file is readable; the native runtime performs the final check.
    try:
        with image.open("rb") as stream:
            digest = hashlib.sha1()
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


class Launcher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Sonic Shuffle Recompiled")
        self.geometry("720x430")
        self.minsize(620, 380)
        self.configure(bg="#08142e")
        self.data = load_settings()
        self.disc = tk.StringVar(value=self.data.get("disc", ""))
        self.scale = tk.IntVar(value=2 if self.data.get("scale") == 2 else 1)
        self.status = tk.StringVar(value="Select your original disc image to begin.")
        self._build_ui()
        self._refresh_status()

    def _build_ui(self) -> None:
        outer = tk.Frame(self, bg="#08142e", padx=38, pady=28)
        outer.pack(fill="both", expand=True)
        tk.Label(outer, text="SONIC SHUFFLE", fg="#ffffff", bg="#08142e",
                 font=("TkDefaultFont", 28, "bold")).pack(anchor="w")
        tk.Label(outer, text="Recompiled native port", fg="#8ca8d8", bg="#08142e",
                 font=("TkDefaultFont", 12)).pack(anchor="w", pady=(2, 28))

        card = tk.Frame(outer, bg="#10244a", padx=20, pady=18)
        card.pack(fill="x")
        tk.Label(card, text="Original disc image", fg="#e9f0ff", bg="#10244a",
                 font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        row = tk.Frame(card, bg="#10244a")
        row.pack(fill="x", pady=(10, 8))
        tk.Entry(row, textvariable=self.disc, bg="#07132a", fg="#ffffff",
                 insertbackground="#ffffff", relief="flat").pack(side="left", fill="x", expand=True, ipady=7)
        tk.Button(row, text="Browse…", command=self._browse, relief="flat",
                  padx=14).pack(side="left", padx=(10, 0), ipady=3)
        tk.Label(card, textvariable=self.status, fg="#a9bddf", bg="#10244a",
                 anchor="w", justify="left", wraplength=610).pack(fill="x")

        options = tk.Frame(outer, bg="#08142e")
        options.pack(fill="x", pady=(20, 0))
        tk.Label(options, text="Render scale", fg="#b7c9e8", bg="#08142e").pack(side="left")
        ttk.Combobox(options, textvariable=self.scale, values=(1, 2), state="readonly",
                     width=5).pack(side="left", padx=(12, 0))
        tk.Button(options, text="Launch Game", command=self._launch, relief="flat",
                  padx=22, pady=8).pack(side="right")

        tk.Label(outer, text="The launcher uses only the selected original disc image.\n"
                 "Settings are stored in your user profile.", fg="#7188ad", bg="#08142e",
                 justify="left").pack(anchor="w", pady=(28, 0))

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select original Sonic Shuffle disc image",
            filetypes=[("Dreamcast images", "*.chd *.gdi *.cue"), ("All files", "*.*")],
        )
        if path:
            self.disc.set(path)
            self._refresh_status()

    def _refresh_status(self) -> None:
        path = Path(self.disc.get()).expanduser()
        if not self.disc.get():
            self.status.set("No disc image selected.")
        elif not path.is_file():
            self.status.set("File not found.")
        elif sha1_boot(path) is None:
            self.status.set("The selected file could not be read.")
        else:
            self.status.set(f"Ready: {path.name}")

    def _launch(self) -> None:
        image = Path(self.disc.get()).expanduser()
        if not image.is_file():
            messagebox.showerror("Disc image required", "Select a readable original disc image first.")
            return
        exe_name = "sonic-shuffle-recomp.exe" if os.name == "nt" else "sonic-shuffle-recomp"
        candidates = [root_dir() / "build" / "game" / exe_name,
                      root_dir() / "build-macos" / "game" / exe_name,
                      root_dir() / "build-linux" / "game" / exe_name,
                      root_dir() / "build-win" / "game" / exe_name,
                      Path(__file__).resolve().parent / exe_name]
        executable = next((p for p in candidates if p.is_file()), None)
        if executable is None:
            messagebox.showerror("Game not built", "Build the port first, then run the launcher again.")
            return
        self.data.update(disc=str(image), scale=int(self.scale.get()))
        save_settings(self.data)
        try:
            subprocess.Popen([str(executable), "--config", str(root_dir() / "game/sonicshuffle.toml"),
                              "--disc", str(image), "--window", "--scale", str(self.scale.get())],
                             cwd=str(root_dir()))
        except OSError as exc:
            messagebox.showerror("Could not launch game", str(exc))


if __name__ == "__main__":
    Launcher().mainloop()
