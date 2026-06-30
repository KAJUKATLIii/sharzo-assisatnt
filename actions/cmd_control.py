# cmd_control.py — SHARZO Command & Shell Control Action
"""
Executes natural-language system/shell commands.

Parameters:
    task    : str  — natural language description of what to do
    visible : bool — (Windows only) open a visible console window (default False)
"""

import os
import re
import sys
import json
import platform
import subprocess
from pathlib import Path

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"


def _get_api_key() -> str:
    config_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _get_desktop() -> Path:
    if _OS == "Linux":
        xdg = os.environ.get("XDG_DESKTOP_DIR", "")
        if xdg and Path(xdg).exists():
            return Path(xdg)
    return Path.home() / "Desktop"


def _resolve_path(raw: str) -> str:
    """Expand common path shorthands."""
    raw = raw.strip().strip('"').strip("'")
    desktop = str(_get_desktop())
    home    = str(Path.home())
    raw = raw.replace("%DESKTOP%", desktop)
    raw = raw.replace("~/Desktop", desktop)
    raw = raw.replace("desktop", desktop) if raw.lower() == "desktop" else raw
    raw = raw.replace("~", home)
    return raw


def _open_file(path: str, visible: bool = False) -> str:
    """Open a file with its default application."""
    p = Path(_resolve_path(path))
    if not p.exists():
        # Try desktop as fallback
        desktop_p = _get_desktop() / p.name
        if desktop_p.exists():
            p = desktop_p
        else:
            return f"File not found: {path}"

    if _OS == "Windows":
        os.startfile(str(p))
    elif _OS == "Darwin":
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])

    return f"Opened: {p.name}"


def _open_app(app_name: str) -> str:
    """Launch an application by name."""
    app_map_win = {
        "notepad": "notepad.exe",
        "notepad++": "notepad++.exe",
        "calculator": "calc.exe",
        "paint": "mspaint.exe",
        "explorer": "explorer.exe",
        "cmd": "cmd.exe",
        "powershell": "powershell.exe",
        "task manager": "taskmgr.exe",
        "control panel": "control.exe",
        "settings": "ms-settings:",
        "chrome": "chrome.exe",
        "firefox": "firefox.exe",
        "edge": "msedge.exe",
        "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE",
        "powerpoint": "POWERPNT.EXE",
    }

    name_lower = app_name.lower().strip()

    if _OS == "Windows":
        exe = app_map_win.get(name_lower, app_name)
        if exe.startswith("ms-"):
            subprocess.Popen(["start", exe], shell=True)
        else:
            try:
                subprocess.Popen([exe], shell=True)
            except Exception as e:
                return f"Could not open {app_name}: {e}"
    elif _OS == "Darwin":
        subprocess.Popen(["open", "-a", app_name])
    else:
        subprocess.Popen([app_name])

    return f"Launched: {app_name}"


def _run_shell(command: str, visible: bool = False, timeout: int = 30) -> str:
    """Run a shell command and return its output."""
    try:
        if _OS == "Windows" and visible:
            subprocess.Popen(
                ["cmd.exe", "/k", command],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            return f"Opened console with: {command}"

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        if result.returncode == 0:
            return out or "Command completed successfully."
        return err or f"Command failed (exit {result.returncode})."
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s."
    except Exception as e:
        return f"Shell error: {e}"


def _interpret_task(task: str, visible: bool) -> str:
    """
    Parse a natural-language task into an action.
    Handles: open file, open app, run command, etc.
    """
    t = task.lower().strip()

    # --- open file patterns ---
    open_file_match = re.search(
        r'open\s+(.+?)\s+(?:with|in|using)\s+(.+)', t
    )
    if open_file_match:
        file_part = open_file_match.group(1).strip()
        app_part  = open_file_match.group(2).strip()
        # e.g. "open mechanical_engineering.txt on desktop with notepad"
        # resolve desktop paths
        desktop = str(_get_desktop())
        if "desktop" in file_part:
            file_part = re.sub(r'\s*on\s+desktop', '', file_part).strip()
            full_path = str(_get_desktop() / file_part)
        else:
            full_path = file_part

        if _OS == "Windows":
            app_exe = {
                "notepad": "notepad.exe",
                "notepad++": "notepad++.exe",
                "wordpad": "wordpad.exe",
                "word": "WINWORD.EXE",
            }.get(app_part, app_part)
            subprocess.Popen([app_exe, full_path], shell=True)
            return f"Opened {file_part} in {app_part}."
        elif _OS == "Darwin":
            subprocess.Popen(["open", "-a", app_part, full_path])
            return f"Opened {file_part} in {app_part}."
        else:
            subprocess.Popen([app_part, full_path])
            return f"Opened {file_part} in {app_part}."

    # --- open <file> (on desktop) ---
    open_desktop_match = re.search(
        r'open\s+(.+?)\s+(?:on|from)\s+(?:the\s+)?desktop', t
    )
    if open_desktop_match:
        filename = open_desktop_match.group(1).strip()
        return _open_file(str(_get_desktop() / filename), visible)

    # --- open <app> ---
    open_app_match = re.match(r'open\s+(.+)', t)
    if open_app_match:
        target = open_app_match.group(1).strip()
        # Check if it looks like a file path
        if "." in target.split("/")[-1].split("\\")[-1]:
            return _open_file(target, visible)
        return _open_app(target)

    # --- run / execute shell command ---
    run_match = re.match(r'(?:run|execute|launch|start)\s+(.+)', t)
    if run_match:
        cmd = run_match.group(1).strip()
        return _run_shell(cmd, visible)

    # --- fallback: treat the whole task as a shell command ---
    return _run_shell(task, visible)


def cmd_control(parameters: dict, player=None, speak=None) -> str:
    """
    Entry point for executor.

    parameters:
        task    : str  — what to do (required)
        visible : bool — show console window (optional, Windows only)
    """
    task    = parameters.get("task", "").strip()
    visible = bool(parameters.get("visible", False))

    if not task:
        return "No task provided to cmd_control."

    if speak:
        speak("On it, sir.")

    try:
        result = _interpret_task(task, visible)
        if player:
            try:
                player.write_log(f"CMD: {result}")
            except Exception:
                pass
        return result
    except Exception as e:
        return f"cmd_control error: {e}"
