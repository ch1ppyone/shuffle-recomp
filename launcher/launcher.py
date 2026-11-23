#!/usr/bin/env python3
"""PyQt6 desktop launcher for Sonic Shuffle Recompiled.

The launcher only selects the player's original disc image and starts the native
game executable. It has no mod, patch, or translation loading path.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QComboBox,
    QLineEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


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


class LauncherModel:
    def __init__(self) -> None:
        self.data = self._load()

    @staticmethod
    def _load() -> dict:
        try:
            return json.loads(settings_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save(self, disc: str, scale: int) -> None:
        settings_file().write_text(
            json.dumps({"disc": disc, "scale": scale}, indent=2), encoding="utf-8"
        )

    @staticmethod
    def readable_image(path: Path) -> bool:
        try:
            with path.open("rb") as stream:
                return bool(stream.read(1))
        except OSError:
            return False

    @staticmethod
    def executable() -> Path | None:
        name = "sonic-shuffle-recomp.exe" if os.name == "nt" else "sonic-shuffle-recomp"
        candidates = (
            root_dir() / "build" / "game" / name,
            root_dir() / "build-macos" / "game" / name,
            root_dir() / "build-linux" / "game" / name,
            root_dir() / "build-win" / "game" / name,
            Path(__file__).resolve().parent / name,
        )
        return next((candidate for candidate in candidates if candidate.is_file()), None)

    def launch(self, image: Path, scale: int) -> None:
        executable = self.executable()
        if executable is None:
            raise FileNotFoundError("Build the port before launching the game.")
        self.save(str(image), scale)
        subprocess.Popen(
            [
                str(executable),
                "--config",
                str(root_dir() / "game/sonicshuffle.toml"),
                "--disc",
                str(image),
                "--window",
                "--scale",
                str(scale),
            ],
            cwd=str(root_dir()),
        )


class ImageCheckWorker(QObject):
    finished = pyqtSignal(bool, str)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    @pyqtSlot()
    def run(self) -> None:
        if not self.path.is_file():
            self.finished.emit(False, "File not found.")
            return
        try:
            digest = hashlib.sha1()
            with self.path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            self.finished.emit(True, f"Ready: {self.path.name}  •  SHA-1 {digest.hexdigest()[:12]}…")
        except OSError:
            self.finished.emit(False, "The selected file could not be read.")


class LauncherWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.model = LauncherModel()
        self.check_thread: QThread | None = None
        self.check_worker: ImageCheckWorker | None = None
        self.image_ready = False
        self.setWindowTitle("Sonic Shuffle Recompiled")
        self.setMinimumSize(680, 460)
        self.resize(760, 520)
        self._build_ui()
        self._apply_style()
        saved = self.model.data.get("disc", "")
        self.disc_edit.setText(saved)
        self.scale_box.setCurrentText(str(self.model.data.get("scale", 2)))
        if saved:
            self._check_image()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(52, 42, 52, 38)
        outer.setSpacing(0)

        title = QLabel("SONIC SHUFFLE")
        title.setObjectName("title")
        title.setFont(QFont(" sans-serif", 28, QFont.Weight.Bold))
        outer.addWidget(title)
        subtitle = QLabel("RECOMPILED NATIVE PORT")
        subtitle.setObjectName("subtitle")
        outer.addWidget(subtitle)
        outer.addSpacing(34)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(12)
        label = QLabel("ORIGINAL DISC IMAGE")
        label.setObjectName("section")
        card_layout.addWidget(label)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.disc_edit = QLineEdit()
        self.disc_edit.setPlaceholderText("Select a CHD, GDI, or CUE image…")
        self.disc_edit.textChanged.connect(self._on_disc_changed)
        row.addWidget(self.disc_edit, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        card_layout.addLayout(row)

        self.status = QLabel("Select your original disc image to begin.")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        card_layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        card_layout.addWidget(self.progress)
        outer.addWidget(card)
        outer.addSpacing(22)

        options = QHBoxLayout()
        options.addWidget(QLabel("Render scale"))
        self.scale_box = QComboBox()
        self.scale_box.addItems(["1", "2"])
        self.scale_box.setFixedWidth(70)
        options.addWidget(self.scale_box)
        options.addStretch(1)
        self.launch_button = QPushButton("Launch Game")
        self.launch_button.setObjectName("launch")
        self.launch_button.setEnabled(False)
        self.launch_button.clicked.connect(self._launch)
        options.addWidget(self.launch_button)
        outer.addLayout(options)
        outer.addStretch(1)
        note = QLabel("Only the selected original disc image is used.\nSettings are stored in your user profile.")
        note.setObjectName("note")
        outer.addWidget(note)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #08142e; color: #e9f0ff; }
            #title { color: #ffffff; letter-spacing: 1px; }
            #subtitle { color: #8ca8d8; font-size: 12px; font-weight: 600; }
            #card { background: #10244a; border: 1px solid #1d3c70; border-radius: 12px; }
            #section { color: #dbe8ff; font-size: 13px; font-weight: 700; }
            #status, #note { color: #9db4da; font-size: 12px; }
            QLineEdit, QComboBox { background: #07132a; border: 1px solid #315487; border-radius: 6px; padding: 9px; }
            QPushButton { background: #dce9ff; color: #0b1b3a; border: 0; border-radius: 6px; padding: 10px 16px; font-weight: 700; }
            QPushButton:hover { background: #ffffff; }
            QPushButton:disabled { background: #526783; color: #a8b7cf; }
            #launch { background: #55b7ff; padding: 11px 24px; }
            #launch:hover { background: #82cbff; }
            QProgressBar { border: 0; background: #07132a; height: 3px; }
            QProgressBar::chunk { background: #55b7ff; }
            """
        )

    @pyqtSlot()
    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select original Sonic Shuffle disc image",
            "",
            "Dreamcast images (*.chd *.gdi *.cue);;All files (*)",
        )
        if path:
            self.disc_edit.setText(path)
            self._check_image()

    @pyqtSlot(str)
    def _on_disc_changed(self, _value: str) -> None:
        self.image_ready = False
        self.launch_button.setEnabled(False)

    def _check_image(self) -> None:
        if self.check_thread is not None and self.check_thread.isRunning():
            return
        path = Path(self.disc_edit.text()).expanduser()
        self.progress.show()
        self.status.setText("Checking disc image…")
        self.check_thread = QThread(self)
        self.check_worker = ImageCheckWorker(path)
        self.check_worker.moveToThread(self.check_thread)
        self.check_thread.started.connect(self.check_worker.run)
        self.check_worker.finished.connect(self._image_checked)
        self.check_worker.finished.connect(self.check_thread.quit)
        self.check_thread.finished.connect(self._check_finished)
        self.check_thread.start()

    @pyqtSlot(bool, str)
    def _image_checked(self, ready: bool, message: str) -> None:
        self.image_ready = ready
        self.status.setText(message)
        self.launch_button.setEnabled(ready)

    @pyqtSlot()
    def _check_finished(self) -> None:
        self.progress.hide()
        if self.check_thread:
            self.check_thread.deleteLater()
        self.check_thread = None
        self.check_worker = None

    @pyqtSlot()
    def _launch(self) -> None:
        if not self.image_ready:
            return
        try:
            self.model.launch(Path(self.disc_edit.text()).expanduser(), int(self.scale_box.currentText()))
            self.close()
        except (FileNotFoundError, OSError) as exc:
            QMessageBox.critical(self, "Could not launch game", str(exc))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Sonic Shuffle Recompiled")
    app.setOrganizationName("ChippyOne")
    window = LauncherWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
