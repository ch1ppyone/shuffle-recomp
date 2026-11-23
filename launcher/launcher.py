#!/usr/bin/env python3
"""PyQt6 desktop launcher for Sonic Shuffle Recompiled.

The launcher selects the player's original disc image, configures the display and
controller bindings, starts the native game and keeps a complete log of the run.
It has no mod, patch, or translation loading path.
"""
from __future__ import annotations

import ctypes
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from copy import deepcopy
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, QTimer, Qt, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices, QFont, QKeyEvent, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "Sonic Shuffle Recompiled"
APP_VERSION = "1.1"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def app_dir() -> Path:
    """Directory that holds the launcher, game/ and tools/ folders."""
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        # macOS .app: SonicShuffle.app/Contents/MacOS/launcher
        if executable.parent.name == "MacOS" and executable.parent.parent.name == "Contents":
            return executable.parent.parent / "Resources"
        return executable.parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SonicShuffle"
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support/SonicShuffle"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sonicshuffle"
    base.mkdir(parents=True, exist_ok=True)
    return base


def settings_file() -> Path:
    return data_dir() / "launcher.json"


def bindings_file() -> Path:
    return data_dir() / "bindings.cfg"


def logs_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Controls and bindings
# ---------------------------------------------------------------------------

# (label shown in the launcher, key written to the bindings file)
CONTROLS: list[tuple[str, str]] = [
    ("A", "a"),
    ("B", "b"),
    ("X", "x"),
    ("Y", "y"),
    ("Start", "start"),
    ("D-Pad Up", "dpad_up"),
    ("D-Pad Down", "dpad_down"),
    ("D-Pad Left", "dpad_left"),
    ("D-Pad Right", "dpad_right"),
    ("Left Trigger (L)", "ltrigger"),
    ("Right Trigger (R)", "rtrigger"),
    ("Stick Up", "stick_up"),
    ("Stick Down", "stick_down"),
    ("Stick Left", "stick_left"),
    ("Stick Right", "stick_right"),
]

DEFAULT_BINDINGS: dict[str, dict[str, str]] = {
    "keyboard": {
        "a": "key:Z",
        "b": "key:X",
        "x": "key:A",
        "y": "key:S",
        "start": "key:Return",
        "dpad_up": "key:Up",
        "dpad_down": "key:Down",
        "dpad_left": "key:Left",
        "dpad_right": "key:Right",
        "ltrigger": "key:Q",
        "rtrigger": "key:W",
        "stick_up": "key:Up",
        "stick_down": "key:Down",
        "stick_left": "key:Left",
        "stick_right": "key:Right",
    },
    "gamepad": {
        "a": "button:a",
        "b": "button:b",
        "x": "button:x",
        "y": "button:y",
        "start": "button:start",
        "dpad_up": "button:dpup",
        "dpad_down": "button:dpdown",
        "dpad_left": "button:dpleft",
        "dpad_right": "button:dpright",
        "ltrigger": "axis:lefttrigger+",
        "rtrigger": "axis:righttrigger+",
        "stick_up": "axis:lefty-",
        "stick_down": "axis:lefty+",
        "stick_left": "axis:leftx-",
        "stick_right": "axis:leftx+",
    },
}

GAMEPAD_OPTIONS: list[tuple[str, str]] = [
    ("Button A", "button:a"),
    ("Button B", "button:b"),
    ("Button X", "button:x"),
    ("Button Y", "button:y"),
    ("Back", "button:back"),
    ("Guide", "button:guide"),
    ("Start", "button:start"),
    ("Left Stick Click", "button:leftstick"),
    ("Right Stick Click", "button:rightstick"),
    ("Left Shoulder", "button:leftshoulder"),
    ("Right Shoulder", "button:rightshoulder"),
    ("D-Pad Up", "button:dpup"),
    ("D-Pad Down", "button:dpdown"),
    ("D-Pad Left", "button:dpleft"),
    ("D-Pad Right", "button:dpright"),
    ("Left Stick Left", "axis:leftx-"),
    ("Left Stick Right", "axis:leftx+"),
    ("Left Stick Up", "axis:lefty-"),
    ("Left Stick Down", "axis:lefty+"),
    ("Right Stick Left", "axis:rightx-"),
    ("Right Stick Right", "axis:rightx+"),
    ("Right Stick Up", "axis:righty-"),
    ("Right Stick Down", "axis:righty+"),
    ("Left Trigger", "axis:lefttrigger+"),
    ("Right Trigger", "axis:righttrigger+"),
]

GAMEPAD_LABELS = dict((value, label) for label, value in GAMEPAD_OPTIONS)

KEY_SPECIAL: dict[int, str] = {
    int(Qt.Key.Key_Escape): "Escape",
    int(Qt.Key.Key_Tab): "Tab",
    int(Qt.Key.Key_Backtab): "Tab",
    int(Qt.Key.Key_Backspace): "Backspace",
    int(Qt.Key.Key_Return): "Return",
    int(Qt.Key.Key_Enter): "Keypad Enter",
    int(Qt.Key.Key_Insert): "Insert",
    int(Qt.Key.Key_Delete): "Delete",
    int(Qt.Key.Key_Pause): "Pause",
    int(Qt.Key.Key_Print): "PrintScreen",
    int(Qt.Key.Key_SysReq): "PrintScreen",
    int(Qt.Key.Key_Clear): "Clear",
    int(Qt.Key.Key_Home): "Home",
    int(Qt.Key.Key_End): "End",
    int(Qt.Key.Key_Left): "Left",
    int(Qt.Key.Key_Up): "Up",
    int(Qt.Key.Key_Right): "Right",
    int(Qt.Key.Key_Down): "Down",
    int(Qt.Key.Key_PageUp): "PageUp",
    int(Qt.Key.Key_PageDown): "PageDown",
    int(Qt.Key.Key_Shift): "Left Shift",
    int(Qt.Key.Key_Control): "Left Ctrl",
    int(Qt.Key.Key_Meta): "Left GUI",
    int(Qt.Key.Key_Alt): "Left Alt",
    int(Qt.Key.Key_AltGr): "Right Alt",
    int(Qt.Key.Key_CapsLock): "CapsLock",
    int(Qt.Key.Key_NumLock): "NumLock",
    int(Qt.Key.Key_ScrollLock): "ScrollLock",
    int(Qt.Key.Key_Menu): "Menu",
}

KEY_PUNCTUATION: dict[int, str] = {
    int(Qt.Key.Key_Minus): "-",
    int(Qt.Key.Key_Equal): "=",
    int(Qt.Key.Key_BracketLeft): "[",
    int(Qt.Key.Key_BracketRight): "]",
    int(Qt.Key.Key_Backslash): "\\",
    int(Qt.Key.Key_Semicolon): ";",
    int(Qt.Key.Key_Apostrophe): "'",
    int(Qt.Key.Key_QuoteLeft): "`",
    int(Qt.Key.Key_Comma): ",",
    int(Qt.Key.Key_Period): ".",
    int(Qt.Key.Key_Slash): "/",
    int(Qt.Key.Key_Space): "Space",
}


def sdl_key_name(event: QKeyEvent) -> str | None:
    """Translate a Qt key press to the SDL scancode name the game expects."""
    key = int(event.key())
    keypad = bool(event.modifiers() & Qt.KeyboardModifier.KeypadModifier)
    if key in KEY_SPECIAL:
        return KEY_SPECIAL[key]
    first_letter = int(Qt.Key.Key_A)
    last_letter = int(Qt.Key.Key_Z)
    if first_letter <= key <= last_letter:
        return chr(ord("A") + key - first_letter)
    first_digit = int(Qt.Key.Key_0)
    last_digit = int(Qt.Key.Key_9)
    if first_digit <= key <= last_digit:
        digit = key - first_digit
        return f"Keypad {digit}" if keypad else str(digit)
    first_f = int(Qt.Key.Key_F1)
    last_f = int(Qt.Key.Key_F24)
    if first_f <= key <= last_f:
        return f"F{key - first_f + 1}"
    if key in KEY_PUNCTUATION:
        name = KEY_PUNCTUATION[key]
        if keypad:
            return {
                "-": "Keypad -",
                "=": "Keypad =",
                ".": "Keypad .",
                "/": "Keypad /",
                "*": "Keypad *",
                "+": "Keypad +",
            }.get(name, name)
        return name
    # Keypad operators arrive as Qt.Key_Plus / Key_Asterisk etc.
    keypad_names = {
        int(Qt.Key.Key_Plus): "Keypad +",
        int(Qt.Key.Key_Asterisk): "Keypad *",
        int(Qt.Key.Key_Percent): "Keypad /",
    }
    if key in keypad_names and keypad:
        return keypad_names[key]
    return None


def binding_label(value: str) -> str:
    if not value:
        return "Not bound"
    if value.startswith("key:"):
        name = value[4:]
        return "Enter" if name == "Return" else name
    if value.startswith("button:"):
        return GAMEPAD_LABELS.get(value, value[7:].replace("_", " ").title())
    if value.startswith("axis:"):
        return GAMEPAD_LABELS.get(value, value[5:].replace("_", " ").title())
    return value


# ---------------------------------------------------------------------------
# Session log
# ---------------------------------------------------------------------------


class SessionLog:
    """One log per launcher run. The game writes its stdout/stderr here too."""

    def __init__(self) -> None:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = logs_dir() / f"session-{stamp}.log"
        self._lock = threading.Lock()
        self.path.touch()

    def write(self, message: str) -> None:
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        with self._lock:
            with self.path.open("a", encoding="utf-8", errors="replace") as stream:
                stream.write(f"[launcher {stamp}] {message}\n")

    def write_block(self, title: str, lines: list[str]) -> None:
        self.write(title)
        for line in lines:
            self.write("  " + line)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class LauncherModel:
    def __init__(self) -> None:
        self.data = self._load()
        self.bindings_path = Path(self.data.get("bindings") or bindings_file())
        self.binding_values, self.deadzone, self.trigger_ramp = self.load_bindings()

    @staticmethod
    def _load() -> dict:
        try:
            return json.loads(settings_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save_settings(self, disc: str, settings: dict) -> None:
        payload = {"disc": disc, **settings}
        settings_file().write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_bindings(self) -> tuple[dict[str, dict[str, str]], int, bool]:
        values = deepcopy(DEFAULT_BINDINGS)
        deadzone = 20
        trigger_ramp = True
        path = Path(self.data.get("bindings") or bindings_file())
        if path.is_file():
            current: str | None = None
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                lines = []
            for raw in lines:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    current = line[1:-1].strip()
                    continue
                if "=" not in line:
                    continue
                key, value = (part.strip() for part in line.split("=", 1))
                if current in values:
                    if key in values[current]:
                        values[current][key] = value
                elif current is None:
                    if key == "deadzone":
                        try:
                            deadzone = max(0, min(90, int(value)))
                        except ValueError:
                            pass
                    elif key == "trigger_ramp":
                        trigger_ramp = value != "0"
        self.data["bindings"] = str(path)
        self.data["deadzone"] = deadzone
        self.data["trigger_ramp"] = trigger_ramp
        return values, deadzone, trigger_ramp

    def save_bindings(
        self,
        values: dict[str, dict[str, str]],
        deadzone: int,
        trigger_ramp: bool,
    ) -> Path:
        lines = [
            "# Sonic Shuffle Recompiled controller bindings.",
            "# Physical inputs use SDL's own names, so the file survives an SDL upgrade.",
            "version = 1",
            f"deadzone = {deadzone}",
            f"trigger_ramp = {1 if trigger_ramp else 0}",
        ]
        path = bindings_file()
        # Keep the game's optional second slots (a.2, start.2, ...) when the player
        # edited them with F1 in-game. The launcher only edits the first slot.
        extras: dict[str, list[str]] = {"keyboard": [], "gamepad": []}
        known = {key for _, key in CONTROLS}
        if path.is_file():
            current: str | None = None
            for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    current = line[1:-1].strip()
                elif current in extras and "=" in line:
                    key = line.split("=", 1)[0].strip()
                    # Only the game's second slots are kept. Anything else is an
                    # old or unknown key and would make the game warn.
                    if key.endswith(".2") and key[:-2] in known:
                        extras[current].append(line)
        for device in ("keyboard", "gamepad"):
            lines += ["", f"[{device}]"]
            for _, key in CONTROLS:
                lines.append(f"{key} = {values[device].get(key, '')}".rstrip())
            lines.extend(extras[device])
        temporary = path.with_suffix(".tmp")
        temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        temporary.replace(path)
        self.bindings_path = path
        self.data["bindings"] = str(path)
        self.data["deadzone"] = deadzone
        self.data["trigger_ramp"] = trigger_ramp
        return path

    @staticmethod
    def _track_files(path: Path, text: str) -> list[Path]:
        tracks: list[Path] = []
        if path.suffix.lower() == ".cue":
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped.upper().startswith("FILE "):
                    continue
                quoted = stripped.split('"')
                name = quoted[1] if len(quoted) >= 2 else stripped[5:].rsplit(" ", 1)[0].strip()
                if name:
                    tracks.append(path.parent / name)
        else:
            for line in text.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0].isdigit():
                    tracks.append(path.parent / parts[4])
        return tracks

    @staticmethod
    def validate_image(path: Path) -> tuple[bool, str]:
        """Format-aware checks that do not copy or extract any game data."""
        if not path.is_file():
            return False, "Invalid: file not found."
        suffix = path.suffix.lower()
        if suffix not in {".chd", ".gdi", ".cdi", ".cue"}:
            return False, "Invalid: choose a CHD, GDI, CDI, or CUE image."
        try:
            size = path.stat().st_size
            if size == 0:
                return False, "Invalid: the selected image is empty."
            size_text = _size_text(size)
            if suffix == ".chd":
                with path.open("rb") as stream:
                    header = stream.read(16)
                if len(header) < 16 or header[:8] != b"MComprHD":
                    return False, "Invalid: CHD header was not recognised."
                version = int.from_bytes(header[12:16], "big")
                if version != 5:
                    return False, f"Invalid: CHD version {version} is not supported (need v5)."
                return True, f"Valid CHD image: {path.name}  •  {size_text}"
            if suffix == ".cdi":
                with path.open("rb") as stream:
                    header = stream.read(4)
                if header[:3] != b"CDI":
                    return False, "Invalid: CDI header was not recognised."
                return True, f"Valid CDI image: {path.name}  •  {size_text}"
            text = path.read_text(encoding="utf-8", errors="replace")
            if not text.strip():
                return False, f"Invalid: the {suffix[1:].upper()} sheet is empty."
            missing = [track.name for track in LauncherModel._track_files(path, text) if not track.is_file()]
            if missing:
                return False, "Invalid: missing track file(s): " + ", ".join(missing[:3])
            kind = "CUE" if suffix == ".cue" else "GDI"
            return True, f"Valid {kind} image: {path.name}  •  {size_text}"
        except OSError as exc:
            return False, f"Invalid: cannot inspect image ({exc})."

    @staticmethod
    def _source_key(path: Path) -> str:
        return os.path.normcase(str(path.resolve()))

    @classmethod
    def image_fingerprint(cls, path: Path) -> str:
        """Cheap content fingerprint: metadata plus a header for compressed images."""
        info = path.stat()
        digest = hashlib.sha1()
        digest.update(path.name.encode("utf-8", "replace"))
        digest.update(str(info.st_size).encode("ascii"))
        digest.update(str(info.st_mtime_ns).encode("ascii"))
        suffix = path.suffix.lower()
        if suffix in {".chd", ".cdi"}:
            with path.open("rb") as stream:
                digest.update(stream.read(65536))
        elif suffix in {".cue", ".gdi"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            digest.update(text.encode("utf-8", "replace"))
            for track in cls._track_files(path, text):
                track_info = track.stat()
                digest.update(track.name.encode("utf-8", "replace"))
                digest.update(str(track_info.st_size).encode("ascii"))
                digest.update(str(track_info.st_mtime_ns).encode("ascii"))
        return digest.hexdigest()[:16]

    @staticmethod
    def manifest_path() -> Path:
        return data_dir() / "prepared.json"

    @classmethod
    def load_manifest(cls) -> dict:
        try:
            return json.loads(cls.manifest_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    @classmethod
    def save_manifest(cls, manifest: dict) -> None:
        path = cls.manifest_path()
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def clear_manifest(cls) -> None:
        try:
            cls.manifest_path().unlink()
        except OSError:
            pass

    @classmethod
    def prepared_for(cls, image: Path) -> dict | None:
        """Return the prepared manifest when it still matches this image."""
        manifest = cls.load_manifest()
        if not manifest:
            return None
        if manifest.get("source_key") != cls._source_key(image):
            return None
        try:
            if cls.image_fingerprint(image) != manifest.get("fingerprint"):
                return None
        except OSError:
            return None
        prepared = Path(manifest.get("prepared_path", ""))
        if not prepared.is_file():
            return None
        return manifest

    @classmethod
    def clear_prepared(cls, image: Path) -> None:
        manifest = cls.load_manifest()
        if manifest.get("source_key") == cls._source_key(image):
            cache = manifest.get("cache_dir")
            if cache:
                shutil.rmtree(cache, ignore_errors=True)
            cls.clear_manifest()

    @classmethod
    def prepare_image(cls, image: Path, progress=None) -> dict:
        """Validate, fingerprint and (for CDI) convert the image once."""
        emit = progress or (lambda _message: None)
        valid, message = cls.validate_image(image)
        if not valid:
            raise RuntimeError(message)
        emit(message)
        fingerprint = cls.image_fingerprint(image)
        emit(f"fingerprint {fingerprint}")
        resolved = image.resolve()
        manifest = {
            "source": str(resolved),
            "source_key": cls._source_key(image),
            "fingerprint": fingerprint,
            "kind": image.suffix.lower().lstrip("."),
            "prepared_path": str(resolved),
            "cache_dir": "",
            "prepared_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        old = cls.load_manifest()
        if image.suffix.lower() == ".cdi":
            converter = cls.cdirip()
            if converter is None:
                raise FileNotFoundError(
                    "CDI support is missing: tools/cdirip.exe was not bundled."
                )
            cache = data_dir() / "images" / fingerprint
            cue = next(iter(sorted(cache.glob("*.cue"))), None) if cache.is_dir() else None
            if cue is None:
                cache.mkdir(parents=True, exist_ok=True)
                emit(f"converting CDI to {cache} …")
                result = subprocess.run(
                    [str(converter), str(image), str(cache), "-bin", "-full"],
                    check=False,
                    cwd=str(cache),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                cues = sorted(cache.glob("*.cue"))
                if not cues:
                    detail = (result.stdout or "").strip().splitlines()[-1:] or ["no output"]
                    raise RuntimeError("CDI conversion failed: " + detail[0])
                cue = cues[0]
            manifest["prepared_path"] = str(cue)
            manifest["cache_dir"] = str(cache)
            emit(f"CDI tracks ready: {cue.name}")
        if old.get("source_key") == manifest["source_key"] and old.get("cache_dir"):
            if old.get("cache_dir") != manifest["cache_dir"]:
                shutil.rmtree(old["cache_dir"], ignore_errors=True)
        cls.save_manifest(manifest)
        emit("image prepared; launch is enabled")
        return manifest

    @staticmethod
    def executable() -> Path | None:
        name = "sonic-shuffle-recomp.exe" if os.name == "nt" else "sonic-shuffle-recomp"
        candidates = (
            app_dir() / "game" / name,
            app_dir() / "build" / "game" / name,
            app_dir() / "build-macos" / "game" / name,
            app_dir() / "build-linux" / "game" / name,
            app_dir() / "build-win" / "game" / name,
        )
        return next((candidate for candidate in candidates if candidate.is_file()), None)

    @staticmethod
    def cdirip() -> Path | None:
        name = "cdirip.exe" if os.name == "nt" else "cdirip"
        candidates = (app_dir() / "tools" / name, app_dir() / name)
        return next((candidate for candidate in candidates if candidate.is_file()), None)

    @staticmethod
    def config() -> Path:
        return app_dir() / "game" / "sonicshuffle.toml"

    @classmethod
    def preflight(cls, image: Path) -> list[str]:
        problems: list[str] = []
        executable = cls.executable()
        if executable is None:
            problems.append("Game executable is missing: game/sonic-shuffle-recomp")
        elif os.name == "nt":
            if not (executable.parent / "SDL3.dll").is_file():
                problems.append("SDL3.dll is missing next to the game executable.")
        if not cls.config().is_file():
            problems.append("Game configuration is missing: game/sonicshuffle.toml")
        if sys.platform == "darwin" and getattr(sys, "frozen", False):
            game_dir = app_dir() / "game"
            for name in (
                "libSDL3.0.dylib",
                "libvulkan.1.dylib",
                "libMoltenVK.dylib",
                "MoltenVK_icd.json",
            ):
                if not (game_dir / name).is_file():
                    problems.append(f"macOS runtime is missing {name} in the app bundle.")
        if not image.is_file():
            problems.append("Disc image is missing.")
        elif cls.prepared_for(image) is None:
            problems.append("The disc image has not been prepared yet. Press Prepare image.")
        if os.name == "nt":
            ok, message = vulkan_probe()
            if not ok:
                problems.append(
                    message
                    + " Enable 3D acceleration and install the VM guest tools, or run "
                    "the game on a Windows PC with a Vulkan-capable GPU."
                )
        return problems

    def launch(
        self,
        image: Path,
        settings: dict,
        log: SessionLog,
    ) -> tuple[subprocess.Popen, Path | None]:
        executable = self.executable()
        if executable is None:
            raise FileNotFoundError("Build the port before launching the game.")
        config = self.config()
        if not config.is_file():
            raise FileNotFoundError(f"Game configuration is missing: {config}")
        manifest = self.prepared_for(image)
        if manifest is None:
            raise RuntimeError("Prepare the disc image before launching the game.")
        runtime_image = Path(manifest["prepared_path"])
        bindings = self.save_bindings(
            self.binding_values, self.deadzone, self.trigger_ramp
        )
        self.save_settings(str(image), settings)
        command = [
            str(executable),
            "--config",
            str(config),
            "--disc",
            str(runtime_image),
            "--window",
            "--scale",
            str(settings["scale"]),
            "--volume",
            str(settings["volume"]),
            "--bindings",
            str(bindings),
        ]
        if settings["fullscreen"]:
            command.append("--fullscreen")
        if settings["aspect"] == "16:9":
            command += ["--render-aspect", "1.7778"]
        interpolation = settings.get("interpolation", "off")
        env = os.environ.copy()
        if interpolation == "auto":
            command.append("--interpolate-auto")
            env.pop("DREAM_NO_INTERPOLATE", None)
        else:
            env["DREAM_NO_INTERPOLATE"] = "1"
        if sys.platform == "darwin":
            icd = app_dir() / "game" / "MoltenVK_icd.json"
            if icd.is_file():
                env["VK_ICD_FILENAMES"] = str(icd)
                env["VK_DRIVER_FILES"] = str(icd)
                log.write(f"vulkan ICD: {icd}")
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        log.write("command: " + " ".join(command))
        log.write(f"working directory: {app_dir()}")
        log.write(f"disc image: {image} ({_size_text(image.stat().st_size)})")
        log.write(f"bindings: {bindings}")
        log.write(f"interpolation: {interpolation}")
        log.write("--- game output ---")
        with log.path.open("ab", buffering=0) as stream:
            process = subprocess.Popen(
                command,
                cwd=str(app_dir()),
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                env=env,
                creationflags=creationflags,
            )
        return process, None


def _size_text(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def running_under_wine() -> bool:
    if os.name != "nt":
        return False
    try:
        return hasattr(ctypes.WinDLL("ntdll.dll"), "wine_get_version")
    except OSError:
        return False


def vulkan_probe() -> tuple[bool, str]:
    """Check that the Windows Vulkan loader exposes a surface-capable device."""
    if os.name != "nt":
        return True, "Vulkan probe skipped (not Windows)."
    try:
        library = ctypes.WinDLL("vulkan-1.dll")
    except OSError as exc:
        return False, f"Vulkan loader is missing: {exc}"

    class VkExtensionProperties(ctypes.Structure):
        _fields_ = [
            ("extensionName", ctypes.c_char * 256),
            ("specVersion", ctypes.c_uint32),
        ]

    count = ctypes.c_uint32(0)
    if library.vkEnumerateInstanceExtensionProperties(
        None, ctypes.byref(count), None
    ) != 0:
        return False, "Vulkan loader could not list instance extensions."
    extensions = (VkExtensionProperties * count.value)()
    if count.value:
        if library.vkEnumerateInstanceExtensionProperties(
            None, ctypes.byref(count), extensions
        ) != 0:
            return False, "Vulkan loader could not read instance extensions."
    names = {
        extensions[i].extensionName.decode("ascii", "replace")
        for i in range(count.value)
    }
    if "VK_KHR_surface" not in names:
        return False, (
            "Vulkan does not expose VK_KHR_surface. This machine or VM cannot "
            "create a Vulkan window surface."
        )

    class VkApplicationInfo(ctypes.Structure):
        _fields_ = [
            ("sType", ctypes.c_uint32),
            ("pNext", ctypes.c_void_p),
            ("pApplicationName", ctypes.c_char_p),
            ("applicationVersion", ctypes.c_uint32),
            ("pEngineName", ctypes.c_char_p),
            ("engineVersion", ctypes.c_uint32),
            ("apiVersion", ctypes.c_uint32),
        ]

    class VkInstanceCreateInfo(ctypes.Structure):
        _fields_ = [
            ("sType", ctypes.c_uint32),
            ("pNext", ctypes.c_void_p),
            ("flags", ctypes.c_uint32),
            ("pApplicationInfo", ctypes.POINTER(VkApplicationInfo)),
            ("enabledLayerCount", ctypes.c_uint32),
            ("ppEnabledLayerNames", ctypes.c_void_p),
            ("enabledExtensionCount", ctypes.c_uint32),
            ("ppEnabledExtensionNames", ctypes.c_void_p),
        ]

    app_info = VkApplicationInfo()
    app_info.sType = 0  # VK_STRUCTURE_TYPE_APPLICATION_INFO
    app_info.pApplicationName = b"Sonic Shuffle Launcher"
    app_info.applicationVersion = 1
    app_info.pEngineName = b"dreamcomp"
    app_info.engineVersion = 1
    app_info.apiVersion = 1 << 22  # Vulkan 1.0
    create_info = VkInstanceCreateInfo()
    create_info.sType = 1  # VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO
    create_info.pApplicationInfo = ctypes.pointer(app_info)
    instance = ctypes.c_void_p()
    if library.vkCreateInstance(
        ctypes.byref(create_info), None, ctypes.byref(instance)
    ) != 0:
        return False, "Vulkan loader is present, but no usable Vulkan driver answered."
    try:
        devices = ctypes.c_uint32(0)
        if library.vkEnumeratePhysicalDevices(
            instance, ctypes.byref(devices), None
        ) != 0:
            return False, "Vulkan could not enumerate physical devices."
        if devices.value == 0:
            return False, (
                "Vulkan loader is installed, but no Vulkan device was found. "
                "The GPU driver does not provide Vulkan."
            )
        return True, f"Vulkan OK: {devices.value} device(s), VK_KHR_surface present."
    finally:
        library.vkDestroyInstance(instance, None)


class PrepareWorker(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, dict)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    @pyqtSlot()
    def run(self) -> None:
        try:
            manifest = LauncherModel.prepare_image(self.path, self.progress.emit)
            self.finished.emit(True, "Image prepared.", manifest)
        except Exception as exc:  # noqa: BLE001 - shown to the player
            self.finished.emit(False, str(exc), {})


# ---------------------------------------------------------------------------
# Binding capture dialog
# ---------------------------------------------------------------------------


class BindingDialog(QDialog):
    def __init__(
        self,
        device: str,
        control_label: str,
        current: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.device = device
        self.control_label = control_label
        self.value: str | None = None
        self.setWindowTitle(f"Bind {control_label}")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title = QLabel(f"Bind “{control_label}”")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        if device == "keyboard":
            hint = QLabel("Press the key you want to use. Escape cancels.")
            hint.setObjectName("note")
            hint.setWordWrap(True)
            layout.addWidget(hint)
            self.capture = QLabel("Waiting for a key…")
            self.capture.setObjectName("capture")
            self.capture.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.capture.setMinimumHeight(64)
            layout.addWidget(self.capture)
            self.current = QLabel(f"Current binding: {binding_label(current)}")
            self.current.setObjectName("note")
            layout.addWidget(self.current)
        else:
            hint = QLabel(
                "Choose the gamepad input. The game reads SDL's controller names, "
                "so any controller SDL recognises uses the same profile."
            )
            hint.setObjectName("note")
            hint.setWordWrap(True)
            layout.addWidget(hint)
            self.combo = QComboBox()
            for label, value in GAMEPAD_OPTIONS:
                self.combo.addItem(label, value)
            if current in GAMEPAD_LABELS:
                index = self.combo.findData(current)
                if index >= 0:
                    self.combo.setCurrentIndex(index)
            self.combo.setMinimumHeight(36)
            layout.addWidget(self.combo)

        buttons = QHBoxLayout()
        clear = QPushButton("Clear binding")
        clear.setObjectName("secondary")
        clear.clicked.connect(self._clear)
        buttons.addWidget(clear)
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.ok = QPushButton("Bind")
        self.ok.setObjectName("launch")
        self.ok.clicked.connect(self._accept)
        self.ok.setEnabled(device == "gamepad")
        buttons.addWidget(self.ok)
        layout.addLayout(buttons)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        if self.device == "keyboard":
            self.setFocus(Qt.FocusReason.OtherFocusReason)
            self.grabKeyboard()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self.device == "keyboard":
            self.releaseKeyboard()
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if self.device != "keyboard":
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        name = sdl_key_name(event)
        if name is None:
            self.capture.setText("This key cannot be bound — try another.")
            return
        self.value = f"key:{name}"
        self.capture.setText(binding_label(self.value))
        self.ok.setEnabled(True)
        self.current.setText(f"New binding: {binding_label(self.value)}")

    def _accept(self) -> None:
        if self.device == "gamepad":
            self.value = self.combo.currentData()
        if self.value is not None:
            self.accept()

    def _clear(self) -> None:
        self.value = ""
        self.accept()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class LauncherWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.model = LauncherModel()
        self.log = SessionLog()
        self.process: subprocess.Popen | None = None
        self.temporary: Path | None = None
        self.started_at = 0.0
        self.stopping = False
        self.log_position = 0
        self.image_ready = False
        self.prepared_manifest: dict | None = None
        self.prepare_notify = True
        self.prepare_thread: QThread | None = None
        self.prepare_worker: PrepareWorker | None = None
        self.binding_buttons: dict[str, dict[str, QPushButton]] = {
            "keyboard": {},
            "gamepad": {},
        }

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(920, 660)
        self.resize(1080, 840)
        self._build_ui()
        self._apply_style()
        self._load_state()

        self.process_timer = QTimer(self)
        self.process_timer.setInterval(300)
        self.process_timer.timeout.connect(self._poll_process)
        self.process_timer.start()

        self.log_timer = QTimer(self)
        self.log_timer.setInterval(500)
        self.log_timer.timeout.connect(self._poll_log)
        self.log_timer.start()
        self._poll_log()

    # -- UI ----------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(28, 22, 28, 18)
        outer.setSpacing(14)

        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        title = QLabel("SONIC SHUFFLE")
        title.setObjectName("headerTitle")
        header_text.addWidget(title)
        subtitle = QLabel("RECOMPILED NATIVE PORT")
        subtitle.setObjectName("headerSubtitle")
        header_text.addWidget(subtitle)
        header.addLayout(header_text)
        header.addStretch(1)
        badge = QLabel(f"LAUNCHER {APP_VERSION}")
        badge.setObjectName("badge")
        header.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(header)

        accent = QFrame()
        accent.setObjectName("accent")
        accent.setFixedHeight(4)
        outer.addWidget(accent)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.game_tab = self._build_game_tab()
        self.controls_tab = self._build_controls_tab()
        self.logs_tab = self._build_logs_tab()
        self.tabs.addTab(self.game_tab, "Game")
        self.tabs.addTab(self.controls_tab, "Controls")
        self.tabs.addTab(self.logs_tab, "Logs")
        outer.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        self.footer_status = QLabel("Ready.")
        self.footer_status.setObjectName("footer")
        footer.addWidget(self.footer_status, 1)
        log_hint = QLabel(f"Logs: {logs_dir()}")
        log_hint.setObjectName("footer")
        log_hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        footer.addWidget(log_hint, 0, Qt.AlignmentFlag.AlignRight)
        outer.addLayout(footer)

    @staticmethod
    def _scroll_page() -> tuple[QScrollArea, QWidget, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("page")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)
        scroll.setWidget(content)
        return scroll, content, layout

    @staticmethod
    def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 18, 22, 20)
        layout.setSpacing(12)
        label = QLabel(title)
        label.setObjectName("section")
        layout.addWidget(label)
        return card, layout

    def _build_game_tab(self) -> QWidget:
        scroll, _content, layout = self._scroll_page()

        disc_card, disc_layout = self._card("ORIGINAL DISC IMAGE")
        disc_row = QHBoxLayout()
        disc_row.setSpacing(10)
        self.disc_edit = QLineEdit()
        self.disc_edit.setPlaceholderText("Select a CHD, GDI, CUE, or CDI image…")
        self.disc_edit.setMinimumHeight(36)
        self.disc_edit.textChanged.connect(self._on_disc_changed)
        disc_row.addWidget(self.disc_edit, 1)
        self.browse_button = QPushButton("Browse…")
        self.browse_button.setObjectName("secondary")
        self.browse_button.setMinimumHeight(36)
        self.browse_button.clicked.connect(self._browse)
        disc_row.addWidget(self.browse_button)
        disc_layout.addLayout(disc_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.prepare_button = QPushButton("Prepare image")
        self.prepare_button.setObjectName("launch")
        self.prepare_button.setMinimumHeight(40)
        self.prepare_button.clicked.connect(lambda: self._prepare_image(notify=True))
        action_row.addWidget(self.prepare_button)
        self.rebuild_button = QPushButton("Rebuild")
        self.rebuild_button.setObjectName("secondary")
        self.rebuild_button.setMinimumHeight(40)
        self.rebuild_button.clicked.connect(self._rebuild_image)
        action_row.addWidget(self.rebuild_button)
        action_row.addStretch(1)
        disc_layout.addLayout(action_row)

        self.status = QLabel(
            "Select your original disc image, then prepare it once. "
            "The native game is already built; preparing validates the image and "
            "converts a CDI into a cached CUE/GDI. Your disc is never modified."
        )
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        disc_layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.hide()
        disc_layout.addWidget(self.progress)
        layout.addWidget(disc_card)

        settings_card, settings_layout = self._card("DISPLAY & AUDIO")
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)
        grid.setColumnMinimumWidth(0, 180)

        self.scale_box = QComboBox()
        for value in range(1, 9):
            width, height = 640 * value, 480 * value
            self.scale_box.addItem(f"{value}x  —  {width}×{height}", value)
        self.scale_box.setMinimumHeight(36)
        grid.addWidget(QLabel("Resolution scale"), 0, 0)
        grid.addWidget(self.scale_box, 0, 1)

        self.aspect_box = QComboBox()
        self.aspect_box.addItem("4:3  —  native", "4:3")
        self.aspect_box.addItem("16:9  —  widescreen", "16:9")
        self.aspect_box.setMinimumHeight(36)
        grid.addWidget(QLabel("Display aspect"), 1, 0)
        grid.addWidget(self.aspect_box, 1, 1)

        volume_row = QHBoxLayout()
        volume_row.setSpacing(12)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setMinimumHeight(30)
        self.volume_value = QLabel("100 %")
        self.volume_value.setObjectName("value")
        self.volume_value.setFixedWidth(56)
        self.volume_slider.valueChanged.connect(
            lambda value: self.volume_value.setText(f"{value} %")
        )
        volume_row.addWidget(self.volume_slider, 1)
        volume_row.addWidget(self.volume_value)
        grid.addWidget(QLabel("Volume"), 2, 0)
        grid.addLayout(volume_row, 2, 1)

        self.fullscreen_box = QCheckBox("Start in fullscreen")
        self.fullscreen_box.setMinimumHeight(30)
        grid.addWidget(QLabel("Window"), 3, 0)
        grid.addWidget(self.fullscreen_box, 3, 1)

        self.interpolation_box = QComboBox()
        self.interpolation_box.addItem("Off  —  fastest", "off")
        self.interpolation_box.addItem("Auto  —  above 60 Hz", "auto")
        self.interpolation_box.setMinimumHeight(36)
        grid.addWidget(QLabel("Frame interpolation"), 4, 0)
        grid.addWidget(self.interpolation_box, 4, 1)
        settings_layout.addLayout(grid)

        preset_row = QHBoxLayout()
        preset = QPushButton("Fast preset: 1x, no interpolation")
        preset.setObjectName("secondary")
        preset.setMinimumHeight(34)
        preset.clicked.connect(self._apply_fast_preset)
        preset_row.addWidget(preset)
        preset_row.addStretch(1)
        settings_layout.addLayout(preset_row)

        hint = QLabel(
            "Controller bindings live on the Controls tab. Both keyboard and gamepad "
            "remain active in-game. Higher scales render more pixels; use 1x–2x on "
            "laptops, Wine, or virtual machines."
        )
        hint.setObjectName("note")
        hint.setWordWrap(True)
        settings_layout.addWidget(hint)
        layout.addWidget(settings_card)

        launch_card, launch_layout = self._card("LAUNCH")
        self.game_status = QLabel("Waiting for a valid disc image.")
        self.game_status.setObjectName("status")
        self.game_status.setWordWrap(True)
        launch_layout.addWidget(self.game_status)
        launch_row = QHBoxLayout()
        launch_row.addStretch(1)
        self.stop_button = QPushButton("Stop Game")
        self.stop_button.setObjectName("danger")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_game)
        launch_row.addWidget(self.stop_button)
        self.launch_button = QPushButton("Launch Game")
        self.launch_button.setObjectName("launch")
        self.launch_button.setMinimumHeight(46)
        self.launch_button.setMinimumWidth(200)
        self.launch_button.setEnabled(False)
        self.launch_button.clicked.connect(self._launch)
        launch_row.addWidget(self.launch_button)
        launch_layout.addLayout(launch_row)
        layout.addWidget(launch_card)
        layout.addStretch(1)
        self.game_scroll = scroll
        return scroll

    def _build_controls_tab(self) -> QWidget:
        scroll, _content, layout = self._scroll_page()

        card, card_layout = self._card("CONTROLLER BINDINGS")
        intro = QLabel(
            "Choose a device, then press a binding button to assign a new input. "
            "Bindings are written to your user profile and passed to the game on launch."
        )
        intro.setObjectName("note")
        intro.setWordWrap(True)
        card_layout.addWidget(intro)

        device_row = QHBoxLayout()
        device_row.setSpacing(10)
        device_row.addWidget(QLabel("Editing device"))
        self.device_box = QComboBox()
        self.device_box.addItem("Keyboard", "keyboard")
        self.device_box.addItem("Gamepad", "gamepad")
        self.device_box.setMinimumHeight(36)
        self.device_box.setMinimumWidth(180)
        self.device_box.currentIndexChanged.connect(self._switch_device)
        device_row.addWidget(self.device_box)
        device_row.addStretch(1)
        reset = QPushButton("Reset defaults")
        reset.setObjectName("secondary")
        reset.setMinimumHeight(36)
        reset.clicked.connect(self._reset_bindings)
        device_row.addWidget(reset)
        card_layout.addLayout(device_row)

        self.binding_stack = QStackedWidget()
        self.binding_stack.setObjectName("bindingStack")
        self.binding_stack.setStyleSheet("background: transparent;")
        self.binding_stack.addWidget(self._build_binding_page("keyboard"))
        self.binding_stack.addWidget(self._build_binding_page("gamepad"))
        card_layout.addWidget(self.binding_stack)
        layout.addWidget(card)

        options_card, options_layout = self._card("STICK & TRIGGERS")
        options_grid = QGridLayout()
        options_grid.setHorizontalSpacing(18)
        options_grid.setVerticalSpacing(12)
        options_grid.setColumnStretch(1, 1)
        options_grid.setColumnMinimumWidth(0, 180)

        deadzone_row = QHBoxLayout()
        deadzone_row.setSpacing(12)
        self.deadzone_slider = QSlider(Qt.Orientation.Horizontal)
        self.deadzone_slider.setRange(0, 50)
        self.deadzone_slider.setMinimumHeight(30)
        self.deadzone_value = QLabel("20 %")
        self.deadzone_value.setObjectName("value")
        self.deadzone_value.setFixedWidth(56)
        self.deadzone_slider.valueChanged.connect(
            lambda value: self.deadzone_value.setText(f"{value} %")
        )
        deadzone_row.addWidget(self.deadzone_slider, 1)
        deadzone_row.addWidget(self.deadzone_value)
        options_grid.addWidget(QLabel("Stick deadzone"), 0, 0)
        options_grid.addLayout(deadzone_row, 0, 1)

        self.trigger_ramp_box = QCheckBox("Ramp digital triggers over about 150 ms")
        self.trigger_ramp_box.setMinimumHeight(30)
        options_grid.addWidget(QLabel("Triggers"), 1, 0)
        options_grid.addWidget(self.trigger_ramp_box, 1, 1)
        options_layout.addLayout(options_grid)
        hint = QLabel(
            "A deadzone keeps a worn stick from steering on its own. Trigger ramping "
            "softens the jump from a keyboard's fully-down key to a full trigger."
        )
        hint.setObjectName("note")
        hint.setWordWrap(True)
        options_layout.addWidget(hint)
        layout.addWidget(options_card)
        layout.addStretch(1)
        return scroll

    def _build_binding_page(self, device: str) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 8, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)
        grid.setColumnMinimumWidth(0, 190)

        header = QLabel("CONTROL")
        header.setObjectName("columnHeader")
        grid.addWidget(header, 0, 0)
        header = QLabel("BINDING")
        header.setObjectName("columnHeader")
        grid.addWidget(header, 0, 1)

        for row, (label, key) in enumerate(CONTROLS, start=1):
            grid.addWidget(QLabel(label), row, 0)
            button = QPushButton()
            button.setObjectName("bind")
            button.setMinimumHeight(36)
            button.setMinimumWidth(260)
            button.clicked.connect(
                lambda _checked=False, d=device, k=key: self._edit_binding(d, k)
            )
            self.binding_buttons[device][key] = button
            grid.addWidget(button, row, 1)
            clear = QPushButton("Clear")
            clear.setObjectName("secondary")
            clear.setMinimumHeight(36)
            clear.clicked.connect(
                lambda _checked=False, d=device, k=key: self._clear_binding(d, k)
            )
            grid.addWidget(clear, row, 2)
        return page

    def _build_logs_tab(self) -> QWidget:
        scroll, _content, layout = self._scroll_page()
        card, card_layout = self._card("SESSION LOG")
        note = QLabel(
            "Every launch writes the game's stdout and stderr here. If the game exits "
            "immediately, this tab shows the reason."
        )
        note.setObjectName("note")
        note.setWordWrap(True)
        card_layout.addWidget(note)

        path_row = QHBoxLayout()
        self.log_path = QLabel(str(self.log.path))
        self.log_path.setObjectName("mono")
        self.log_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.log_path.setWordWrap(True)
        path_row.addWidget(self.log_path, 1)
        open_folder = QPushButton("Open log folder")
        open_folder.setObjectName("secondary")
        open_folder.clicked.connect(self._open_log_folder)
        path_row.addWidget(open_folder)
        card_layout.addLayout(path_row)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log_view.setMinimumHeight(420)
        card_layout.addWidget(self.log_view, 1)

        buttons = QHBoxLayout()
        diagnostics = QPushButton("Run diagnostics")
        diagnostics.setObjectName("secondary")
        diagnostics.clicked.connect(self._run_diagnostics)
        buttons.addWidget(diagnostics)
        refresh = QPushButton("Refresh")
        refresh.setObjectName("secondary")
        refresh.clicked.connect(self._poll_log)
        buttons.addWidget(refresh)
        copy = QPushButton("Copy log")
        copy.setObjectName("secondary")
        copy.clicked.connect(self._copy_log)
        buttons.addWidget(copy)
        buttons.addStretch(1)
        card_layout.addLayout(buttons)
        layout.addWidget(card, 1)
        return scroll

    # -- Style -------------------------------------------------------------

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #061b48; color: #f8fbff; font-size: 14px; }
            QWidget#page { background: transparent; }
            QLabel, QCheckBox { background: transparent; }
            QTabWidget, QTabBar { background: transparent; }
            QStackedWidget, QStackedWidget > QWidget { background: transparent; }
            #headerTitle { color: #ffffff; font-size: 30px; font-weight: 800; letter-spacing: 2px; }
            #headerSubtitle { color: #8fb8f5; font-size: 12px; font-weight: 700; letter-spacing: 1px; }
            #badge { background: #0c2c67; color: #ffd52e; border: 1px solid #3272cb;
                     border-radius: 10px; padding: 5px 12px; font-size: 11px; font-weight: 800; }
            #accent { background: #ffd52e; border-radius: 2px; }
            #card { background: #0c2c67; border: 2px solid #164a96; border-radius: 14px; }
            #section { color: #ffd52e; font-size: 13px; font-weight: 800; letter-spacing: 1px; }
            #status, #note { color: #b8d5ff; font-size: 12px; }
            #value { color: #ffffff; font-weight: 700; }
            #columnHeader { color: #8fb8f5; font-size: 11px; font-weight: 800; letter-spacing: 1px; }
            #footer { color: #7f9cc9; font-size: 11px; }
            #mono { color: #9fc4f5; font-family: "Consolas", "Menlo", monospace; font-size: 11px; }
            #dialogTitle { color: #ffffff; font-size: 20px; font-weight: 800; }
            #capture { background: #041535; border: 2px solid #3272cb; border-radius: 10px;
                       color: #ffd52e; font-size: 22px; font-weight: 800; padding: 12px; }
            QLineEdit, QComboBox { background: #041535; border: 1px solid #3272cb;
                                   border-radius: 8px; padding: 8px 10px; min-height: 20px;
                                   color: #ffffff; selection-background-color: #ffd52e;
                                   selection-color: #082052; }
            QLineEdit:focus, QComboBox:focus { border: 2px solid #ffd52e; }
            QComboBox QAbstractItemView { background: #041535; color: #ffffff;
                                          selection-background-color: #ffd52e;
                                          selection-color: #082052; border: 1px solid #3272cb; }
            QPushButton { background: #ffd52e; color: #082052; border: none; border-radius: 8px;
                          padding: 8px 18px; min-height: 20px; font-weight: 800; }
            QPushButton:hover { background: #ffe878; }
            QPushButton:pressed { background: #e6bd18; }
            QPushButton:disabled { background: #4a628f; color: #b8c7df; }
            QPushButton#secondary { background: #123a78; color: #dbe8ff; border: 1px solid #3272cb; }
            QPushButton#secondary:hover { background: #1a4a94; }
            QPushButton#secondary:disabled { background: #2a3f63; color: #7f95b8; border-color: #3c5680; }
            QPushButton#danger { background: #d64545; color: #ffffff; }
            QPushButton#danger:hover { background: #e65c5c; }
            QPushButton#danger:disabled { background: #4a628f; color: #b8c7df; }
            QPushButton#launch { background: #ffcf1b; font-size: 15px; padding: 10px 30px; }
            QPushButton#launch:disabled { background: #4a628f; color: #b8c7df; }
            QPushButton#bind:disabled { background: #1a3157; color: #7f95b8; border-color: #3c5680; }
            QPushButton#bind { background: #041535; color: #ffffff; border: 1px solid #3272cb;
                               text-align: left; padding: 8px 12px; font-weight: 600; }
            QPushButton#bind:hover { border: 2px solid #ffd52e; }
            QCheckBox { color: #f8fbff; spacing: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px;
                                   border: 1px solid #3272cb; background: #041535; }
            QCheckBox::indicator:checked { background: #ffd52e; border: 1px solid #ffd52e; }
            QSlider::groove:horizontal { height: 6px; background: #041535; border-radius: 3px; }
            QSlider::sub-page:horizontal { background: #ffd52e; border-radius: 3px; }
            QSlider::handle:horizontal { background: #ffffff; width: 16px; margin: -5px 0;
                                         border-radius: 8px; }
            QTabWidget::pane { border: 2px solid #164a96; border-radius: 14px; background: #082457; }
            QTabBar::tab { background: #08265a; color: #b8d5ff; padding: 10px 28px;
                           margin-right: 4px; border-top-left-radius: 8px;
                           border-top-right-radius: 8px; font-weight: 700; }
            QTabBar::tab:selected { background: #ffd52e; color: #082052; }
            QTabBar::tab:hover:!selected { background: #123a78; }
            QTabWidget#innerTabs::pane { border: none; background: transparent; }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: #041535; width: 12px; border-radius: 6px; }
            QScrollBar::handle:vertical { background: #3272cb; border-radius: 6px; min-height: 30px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QProgressBar { border: 0; background: #041535; height: 4px; border-radius: 2px; }
            QProgressBar::chunk { background: #ffd52e; border-radius: 2px; }
            QPlainTextEdit { background: #041535; color: #cfe2ff; border: 1px solid #3272cb;
                             border-radius: 8px; font-family: "Consolas", "Menlo", monospace;
                             font-size: 12px; padding: 8px; }
            QMessageBox { background: #0c2c67; }
            """
        )

    # -- State -------------------------------------------------------------

    def _load_state(self) -> None:
        data = self.model.data
        saved_disc = str(data.get("disc", ""))
        self.disc_edit.setText(saved_disc)
        index = self.scale_box.findData(int(data.get("scale", 2)))
        self.scale_box.setCurrentIndex(index if index >= 0 else 1)
        index = self.aspect_box.findData(data.get("aspect", "4:3"))
        self.aspect_box.setCurrentIndex(index if index >= 0 else 0)
        self.volume_slider.setValue(int(data.get("volume", 100)))
        self.fullscreen_box.setChecked(bool(data.get("fullscreen", False)))
        index = self.interpolation_box.findData(data.get("interpolation", "off"))
        self.interpolation_box.setCurrentIndex(index if index >= 0 else 0)
        self.deadzone_slider.setValue(int(self.model.deadzone))
        self.trigger_ramp_box.setChecked(bool(self.model.trigger_ramp))
        self._refresh_binding_buttons()
        self._write_startup_log()
        self.game_scroll.verticalScrollBar().setValue(0)
        if saved_disc:
            self.status.setText("Remembered image — preparing…")
            self._prepare_image(notify=False)

    def _settings(self) -> dict:
        return {
            "scale": int(self.scale_box.currentData() or 2),
            "aspect": str(self.aspect_box.currentData() or "4:3"),
            "volume": int(self.volume_slider.value()),
            "fullscreen": bool(self.fullscreen_box.isChecked()),
            "interpolation": str(self.interpolation_box.currentData() or "off"),
        }

    def _apply_fast_preset(self) -> None:
        self.scale_box.setCurrentIndex(0)
        self.interpolation_box.setCurrentIndex(0)
        self.fullscreen_box.setChecked(False)
        self.status.setText("Fast preset applied: 1x scale, interpolation off.")
        self.log.write("fast preset applied: 1x scale, interpolation off")

    def _save_settings(self) -> None:
        self.model.deadzone = int(self.deadzone_slider.value())
        self.model.trigger_ramp = bool(self.trigger_ramp_box.isChecked())
        self.model.save_bindings(
            self.model.binding_values,
            self.model.deadzone,
            self.model.trigger_ramp,
        )
        self.model.save_settings(self.disc_edit.text().strip(), self._settings())

    # -- Disc image --------------------------------------------------------

    @pyqtSlot()
    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select original Sonic Shuffle disc image",
            str(Path(self.disc_edit.text()).parent) if self.disc_edit.text() else "",
            "Dreamcast images (*.chd *.gdi *.cdi *.cue);;All files (*)",
        )
        if path:
            self.disc_edit.setText(path)
            self._prepare_image(notify=True)

    @pyqtSlot(str)
    def _on_disc_changed(self, value: str) -> None:
        self.image_ready = False
        self.prepared_manifest = None
        self.launch_button.setEnabled(False)
        self.prepare_button.setEnabled(bool(value.strip()))
        self.rebuild_button.setEnabled(bool(value.strip()))
        self.game_status.setText("Waiting for the image to be prepared.")

    def _rebuild_image(self) -> None:
        self._prepare_image(rebuild=True, notify=True)

    def _prepare_image(self, rebuild: bool = False, notify: bool = True) -> None:
        if self.prepare_thread is not None:
            if self.prepare_thread.isRunning():
                return
            # The worker signalled completion but its QThread cleanup has not been
            # delivered yet. Finish that bookkeeping before starting another one.
            self.prepare_thread.wait(2000)
            self.prepare_thread.deleteLater()
            self.prepare_thread = None
            self.prepare_worker = None
        text = self.disc_edit.text().strip()
        if not text:
            return
        image = Path(text).expanduser()
        if rebuild:
            LauncherModel.clear_prepared(image)
        self.prepare_notify = notify
        self.prepared_manifest = None
        self.image_ready = False
        self.launch_button.setEnabled(False)
        self.prepare_button.setEnabled(False)
        self.rebuild_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.progress.show()
        self.status.setText("Preparing image…")
        self.game_status.setText("Preparing the disc image…")
        self.log.write(("rebuilding " if rebuild else "preparing ") + f"image: {image}")
        self.prepare_thread = QThread(self)
        self.prepare_worker = PrepareWorker(image)
        self.prepare_worker.moveToThread(self.prepare_thread)
        self.prepare_thread.started.connect(self.prepare_worker.run)
        self.prepare_worker.progress.connect(self._prepare_progress)
        self.prepare_worker.finished.connect(self._prepare_finished)
        self.prepare_worker.finished.connect(self.prepare_thread.quit)
        self.prepare_thread.finished.connect(self._prepare_finished_thread)
        self.prepare_thread.start()

    @pyqtSlot(str)
    def _prepare_progress(self, message: str) -> None:
        self.status.setText(message)
        self.log.write("prepare: " + message)

    @pyqtSlot(bool, str, dict)
    def _prepare_finished(self, ready: bool, message: str, manifest: dict) -> None:
        self.progress.hide()
        self.prepare_button.setEnabled(True)
        self.rebuild_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        if ready:
            self.prepared_manifest = manifest
            self.image_ready = True
            self.status.setText("Prepared — ready to launch.")
            self.game_status.setText("Ready to launch.")
            self.launch_button.setEnabled(self.process is None)
            self.game_scroll.verticalScrollBar().setValue(0)
            self.disc_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            self.model.save_settings(self.disc_edit.text().strip(), self._settings())
            self.log.write("prepare finished: " + manifest.get("prepared_path", ""))
        else:
            self.prepared_manifest = None
            self.image_ready = False
            self.launch_button.setEnabled(False)
            self.status.setText("Preparation failed: " + message)
            self.game_status.setText("Fix the image, then press Prepare image.")
            self.log.write("prepare failed: " + message)
            if self.prepare_notify:
                QMessageBox.critical(
                    self,
                    "Could not prepare the image",
                    message + f"\n\nFull log:\n{self.log.path}",
                )

    @pyqtSlot()
    def _prepare_finished_thread(self) -> None:
        if self.prepare_thread:
            self.prepare_thread.deleteLater()
        self.prepare_thread = None
        self.prepare_worker = None

    # -- Bindings ----------------------------------------------------------

    def _refresh_binding_buttons(self) -> None:
        for device, buttons in self.binding_buttons.items():
            for key, button in buttons.items():
                button.setText(binding_label(self.model.binding_values[device].get(key, "")))

    def _switch_device(self, index: int) -> None:
        self.binding_stack.setCurrentIndex(0 if index == 0 else 1)

    def _edit_binding(self, device: str, key: str) -> None:
        label = next(text for text, name in CONTROLS if name == key)
        dialog = BindingDialog(
            device,
            label,
            self.model.binding_values[device].get(key, ""),
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.model.binding_values[device][key] = dialog.value or ""
        self.model.save_bindings(
            self.model.binding_values,
            self.deadzone_slider.value(),
            self.trigger_ramp_box.isChecked(),
        )
        self._refresh_binding_buttons()
        self.log.write(
            f"binding {device}/{key} = {dialog.value or '(unbound)'}"
        )

    def _clear_binding(self, device: str, key: str) -> None:
        self.model.binding_values[device][key] = ""
        self.model.save_bindings(
            self.model.binding_values,
            self.deadzone_slider.value(),
            self.trigger_ramp_box.isChecked(),
        )
        self._refresh_binding_buttons()
        self.log.write(f"binding {device}/{key} cleared")

    def _reset_bindings(self) -> None:
        self.model.binding_values = deepcopy(DEFAULT_BINDINGS)
        self.deadzone_slider.setValue(20)
        self.trigger_ramp_box.setChecked(True)
        self.model.save_bindings(self.model.binding_values, 20, True)
        self._refresh_binding_buttons()
        self.log.write("controller bindings reset to defaults")

    # -- Launch ------------------------------------------------------------

    def _launch(self) -> None:
        if not self.image_ready or self.process is not None:
            return
        image = Path(self.disc_edit.text()).expanduser()
        problems = LauncherModel.preflight(image)
        if problems:
            self.log.write_block("preflight failed", problems)
            self.tabs.setCurrentWidget(self.logs_tab)
            QMessageBox.critical(
                self,
                "Cannot launch the game",
                "\n\n".join(problems) + f"\n\nFull log:\n{self.log.path}",
            )
            return
        self._save_settings()
        self.log.write("launch requested")
        self.launch_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.game_status.setText("Starting the game…")
        self.footer_status.setText("Starting the game…")
        try:
            self.process, self.temporary = self.model.launch(
                image, self._settings(), self.log
            )
        except Exception as exc:  # noqa: BLE001 - shown to the player
            self.log.write(f"launch failed: {exc}")
            self.launch_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.game_status.setText("The game could not be started.")
            self.footer_status.setText("Launch failed.")
            self.tabs.setCurrentWidget(self.logs_tab)
            QMessageBox.critical(
                self,
                "Could not launch game",
                f"{exc}\n\nFull log:\n{self.log.path}",
            )
            return
        self.started_at = time.monotonic()
        self.game_status.setText("Game running…")
        self.footer_status.setText("Game running…")
        self.log.write(f"game process started (pid {self.process.pid})")
        self._poll_log()

    def _poll_process(self) -> None:
        if self.process is None:
            return
        code = self.process.poll()
        if code is None:
            return
        elapsed = time.monotonic() - self.started_at
        self.log.write(f"game exited with code {code} after {elapsed:.1f} s")
        self.process = None
        self.stop_button.setEnabled(False)
        self.launch_button.setEnabled(self.image_ready)
        if self.temporary is not None:
            shutil.rmtree(self.temporary, ignore_errors=True)
            self.temporary = None
        self._poll_log()
        if self.stopping:
            self.stopping = False
            self.game_status.setText("Game stopped.")
            self.footer_status.setText("Game stopped.")
            return
        if code == 0:
            self.game_status.setText("Game exited normally.")
            self.footer_status.setText("Game exited normally.")
            return
        self.game_status.setText(f"Game exited with code {code}. See the Logs tab.")
        self.footer_status.setText(f"Game exited with code {code}.")
        self.tabs.setCurrentWidget(self.logs_tab)
        self._show_failure_dialog(code, elapsed)

    def _show_failure_dialog(self, code: int, elapsed: float) -> None:
        tail = self._log_tail(24000)
        interesting = [
            line
            for line in tail.splitlines()
            if any(
                word in line.lower()
                for word in (
                    "error",
                    "cannot",
                    "failed",
                    "missing",
                    "disc:",
                    "window:",
                    "fatal",
                    "exception",
                    "not found",
                    "vulkan",
                )
            )
        ]
        details = "\n".join(interesting[-12:]) or "\n".join(tail.splitlines()[-12:])
        hint = ""
        if "VK_KHR_surface" in tail or "surface extension" in tail:
            hint = (
                "\n\nThe VM's Vulkan driver does not support window surfaces "
                "(VK_KHR_surface). Enable 3D acceleration and install the VM guest "
                "tools, or run the game on a Windows PC with a Vulkan-capable GPU."
            )
        QMessageBox.warning(
            self,
            "The game stopped",
            f"The game exited with code {code} after {elapsed:.1f} seconds.\n\n"
            f"{details}{hint}\n\nFull log:\n{self.log.path}",
        )

    def _stop_game(self) -> None:
        if self.process is None:
            return
        self.log.write("stopping the game")
        self.stopping = True
        self.process.terminate()
        try:
            self.process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.footer_status.setText("Stopping the game…")

    # -- Logs --------------------------------------------------------------

    def _write_startup_log(self) -> None:
        executable = LauncherModel.executable()
        cdirip = LauncherModel.cdirip()
        if executable is None:
            sdl = "NOT FOUND"
        elif os.name == "nt":
            sdl = executable.parent / "SDL3.dll"
        elif sys.platform == "darwin":
            bundled = executable.parent / "libSDL3.0.dylib"
            sdl = bundled if bundled.is_file() else Path("/opt/homebrew/opt/sdl3/lib/libSDL3.0.dylib")
        else:
            sdl = executable.parent / "libSDL3.so.0"
        lines = [
            f"{APP_NAME} {APP_VERSION}",
            f"platform: {sys.platform} {os.name}",
            f"launcher: {sys.executable}",
            f"app directory: {app_dir()}",
            f"settings: {settings_file()}",
            f"bindings: {self.model.bindings_path}",
            f"game: {executable or 'NOT FOUND'}",
            f"SDL3: {sdl}",
            f"config: {LauncherModel.config()}",
            f"cdirip: {cdirip or 'not bundled'}",
            f"disc: {self.disc_edit.text() or 'not selected'}",
            f"prepared: {LauncherModel.load_manifest().get('prepared_path', 'not prepared')}",
        ]
        if sys.platform == "darwin":
            icd = app_dir() / "game" / "MoltenVK_icd.json"
            lines.append(f"vulkan ICD: {icd if icd.is_file() else 'system default'}")
        if os.name == "nt":
            ok, message = vulkan_probe()
            lines.append(("vulkan: OK — " if ok else "vulkan: FAILED — ") + message)
            if running_under_wine():
                lines.append(
                    "wine: yes — use 1x scale and interpolation off for best speed"
                )
        self.log.write_block("startup", lines)

    def _poll_log(self) -> None:
        try:
            size = self.log.path.stat().st_size
        except OSError:
            return
        if size < self.log_position:
            self.log_position = 0
            self.log_view.clear()
        if size <= self.log_position:
            return
        try:
            with self.log.path.open("rb") as stream:
                stream.seek(self.log_position)
                data = stream.read()
                self.log_position = stream.tell()
        except OSError:
            return
        text = data.decode("utf-8", errors="replace")
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

    def _log_tail(self, limit: int) -> str:
        try:
            size = self.log.path.stat().st_size
            with self.log.path.open("rb") as stream:
                if size > limit:
                    stream.seek(size - limit)
                return stream.read().decode("utf-8", errors="replace")
        except OSError:
            return ""

    def _open_log_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_dir())))

    def _copy_log(self) -> None:
        QApplication.clipboard().setText(self.log_view.toPlainText())

    def _run_diagnostics(self) -> None:
        image = Path(self.disc_edit.text()).expanduser()
        lines = [
            f"launcher version: {APP_VERSION}",
            f"platform: {sys.platform}",
            f"game executable: {LauncherModel.executable()}",
            f"config: {LauncherModel.config()}",
            f"cdirip: {LauncherModel.cdirip()}",
            f"disc: {image}",
        ]
        if image.is_file():
            valid, message = LauncherModel.validate_image(image)
            lines.append(f"disc check: {'OK' if valid else 'FAILED'} — {message}")
            prepared = LauncherModel.prepared_for(image)
            lines.append(
                "prepared: "
                + (str(prepared.get("prepared_path")) if prepared else "NO — press Prepare image")
            )
        else:
            lines.append("disc check: file not found")
        if sys.platform == "darwin":
            icd = app_dir() / "game" / "MoltenVK_icd.json"
            lines.append(f"vulkan ICD: {icd if icd.is_file() else 'system default'}")
        if os.name == "nt":
            ok, message = vulkan_probe()
            lines.append(("vulkan: OK — " if ok else "vulkan: FAILED — ") + message)
            if running_under_wine():
                lines.append("wine: yes — use 1x scale and interpolation off for best speed")
        problems = LauncherModel.preflight(image) if image.is_file() else []
        lines.append("preflight: " + ("OK" if not problems else "; ".join(problems)))
        self.log.write_block("diagnostics", lines)
        self._poll_log()
        self.tabs.setCurrentWidget(self.logs_tab)

    # -- Window ------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self.prepare_thread is not None and self.prepare_thread.isRunning():
            QMessageBox.information(
                self,
                "Preparing the image",
                "Please wait for the image preparation to finish before closing.",
            )
            event.ignore()
            return
        if self.prepare_thread is not None:
            self.prepare_thread.wait(2000)
        if self.process is not None and self.process.poll() is None:
            answer = QMessageBox.question(
                self,
                "Game is running",
                "Stop the game and close the launcher?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._stop_game()
        self._save_settings()
        if self.temporary is not None:
            shutil.rmtree(self.temporary, ignore_errors=True)
            self.temporary = None
        self.log.write("launcher closed")
        event.accept()


def main() -> int:
    QApplication.setApplicationName(APP_NAME)
    QApplication.setOrganizationName("ChippyOne")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    window = LauncherWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
