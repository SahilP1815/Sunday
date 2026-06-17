"""
Sunday System Controller
Handles all local OS operations: open files, apps, folders, URLs, volume, etc.
"""

import os
import subprocess
import webbrowser
import glob
import re
import ctypes
from pathlib import Path


# ── Known app direct paths (most reliable) ────────────────────────────────────
# These override the search. Add your own here.
_LOCAL  = str(Path.home() / "AppData" / "Local")
_ROAM   = str(Path.home() / "AppData" / "Roaming")
_PROG   = r"C:\Program Files"
_PROG86 = r"C:\Program Files (x86)"

APP_DIRECT_PATHS = {
    "chrome":              [rf"{_PROG}\Google\Chrome\Application\chrome.exe",
                            rf"{_PROG86}\Google\Chrome\Application\chrome.exe"],
    "google chrome":       [rf"{_PROG}\Google\Chrome\Application\chrome.exe"],
    "firefox":             [rf"{_PROG}\Mozilla Firefox\firefox.exe",
                            rf"{_PROG86}\Mozilla Firefox\firefox.exe"],
    "edge":                [rf"{_PROG}\Microsoft\Edge\Application\msedge.exe",
                            rf"{_PROG86}\Microsoft\Edge\Application\msedge.exe"],
    "microsoft edge":      [rf"{_PROG}\Microsoft\Edge\Application\msedge.exe"],
    "vs code":             [rf"{_LOCAL}\Programs\Microsoft VS Code\Code.exe"],
    "vscode":              [rf"{_LOCAL}\Programs\Microsoft VS Code\Code.exe"],
    "visual studio code":  [rf"{_LOCAL}\Programs\Microsoft VS Code\Code.exe"],
    "cursor":              [rf"{_LOCAL}\Programs\cursor\Cursor.exe",
                            rf"{_LOCAL}\cursor\Cursor.exe"],
    "spotify":             [rf"{_ROAM}\Spotify\Spotify.exe",
                            rf"{_LOCAL}\Spotify\Spotify.exe"],
    "discord":             [rf"{_LOCAL}\Discord\app-*\Discord.exe",   # glob pattern
                            rf"{_ROAM}\Discord\Discord.exe"],
    "telegram":            [rf"{_ROAM}\Telegram Desktop\Telegram.exe",
                            rf"{_LOCAL}\Telegram Desktop\Telegram.exe"],
    "whatsapp":            [rf"{_LOCAL}\WhatsApp\WhatsApp.exe",
                            rf"{_ROAM}\WhatsApp\WhatsApp.exe"],
    "steam":               [rf"{_PROG86}\Steam\Steam.exe",
                            rf"{_PROG}\Steam\Steam.exe"],
    "vlc":                 [rf"{_PROG}\VideoLAN\VLC\vlc.exe",
                            rf"{_PROG86}\VideoLAN\VLC\vlc.exe"],
    "obs":                 [rf"{_PROG}\obs-studio\bin\64bit\obs64.exe",
                            rf"{_PROG86}\obs-studio\bin\64bit\obs64.exe"],
    "zoom":                [rf"{_ROAM}\Zoom\bin\Zoom.exe",
                            rf"{_LOCAL}\Zoom\bin\Zoom.exe"],
    "teams":               [rf"{_LOCAL}\Microsoft\Teams\current\Teams.exe",
                            rf"{_ROAM}\Microsoft\Teams\current\Teams.exe"],
    "microsoft teams":     [rf"{_LOCAL}\Microsoft\Teams\current\Teams.exe"],
    "postman":             [rf"{_LOCAL}\Postman\Postman.exe"],
    "figma":               [rf"{_LOCAL}\Figma\Figma.exe",
                            rf"{_ROAM}\Figma\Figma.exe"],
    "blender":             [rf"{_PROG}\Blender Foundation\Blender*\blender.exe"],
    "pycharm":             [rf"{_LOCAL}\JetBrains\PyCharm*\bin\pycharm64.exe",
                            rf"{_PROG}\JetBrains\PyCharm*\bin\pycharm64.exe"],
    "android studio":      [rf"{_LOCAL}\Google\AndroidStudio*\bin\studio64.exe"],
    "notepad++":           [rf"{_PROG}\Notepad++\notepad++.exe",
                            rf"{_PROG86}\Notepad++\notepad++.exe"],
    "photoshop":           [rf"{_PROG}\Adobe\Adobe Photoshop*\Photoshop.exe"],
    "premiere":            [rf"{_PROG}\Adobe\Adobe Premiere Pro*\Adobe Premiere Pro.exe"],
    "illustrator":         [rf"{_PROG}\Adobe\Adobe Illustrator*\Support Files\Contents\Windows\Illustrator.exe"],
    "winrar":              [rf"{_PROG}\WinRAR\WinRAR.exe"],
    "7zip":                [rf"{_PROG}\7-Zip\7zFM.exe"],
}

# ── Shell commands (always available) ─────────────────────────────────────────
APP_SHELL_COMMANDS = {
    "notepad":             "notepad.exe",
    "calculator":          "calc.exe",
    "calc":                "calc.exe",
    "paint":               "mspaint.exe",
    "word":                "WINWORD.EXE",
    "excel":               "EXCEL.EXE",
    "powerpoint":          "POWERPNT.EXE",
    "outlook":             "OUTLOOK.EXE",
    "task manager":        "taskmgr.exe",
    "taskmgr":             "taskmgr.exe",
    "file explorer":       "explorer.exe",
    "explorer":            "explorer.exe",
    "cmd":                 "cmd.exe",
    "command prompt":      "cmd.exe",
    "terminal":            "wt.exe",       # Windows Terminal
    "powershell":          "powershell.exe",
    "snipping tool":       "SnippingTool.exe",
    "snip":                "SnippingTool.exe",
    "control panel":       "control.exe",
    "device manager":      "devmgmt.msc",
    "registry editor":     "regedit.exe",
    "regedit":             "regedit.exe",
    "settings":            "ms-settings:",
    "system info":         "msinfo32.exe",
    "disk manager":        "diskmgmt.msc",
    "event viewer":        "eventvwr.msc",
}

# ── Folder aliases ────────────────────────────────────────────────────────────
FOLDER_ALIASES = {
    "desktop":        str(Path.home() / "Desktop"),
    "documents":      str(Path.home() / "Documents"),
    "my documents":   str(Path.home() / "Documents"),
    "downloads":      str(Path.home() / "Downloads"),
    "my downloads":   str(Path.home() / "Downloads"),
    "download":       str(Path.home() / "Downloads"),
    "pictures":       str(Path.home() / "Pictures"),
    "my pictures":    str(Path.home() / "Pictures"),
    "photos":         str(Path.home() / "Pictures"),
    "images":         str(Path.home() / "Pictures"),
    "music":          str(Path.home() / "Music"),
    "my music":       str(Path.home() / "Music"),
    "songs":          str(Path.home() / "Music"),
    "videos":         str(Path.home() / "Videos"),
    "my videos":      str(Path.home() / "Videos"),
    "movies":         str(Path.home() / "Videos"),
    "home":           str(Path.home()),
    "user folder":    str(Path.home()),
    "c drive":        "C:\\",
    "c:":             "C:\\",
    "d drive":        "D:\\",
    "d:":             "D:\\",
    "e drive":        "E:\\",
    "e:":             "E:\\",
    "program files":  "C:\\Program Files",
    "appdata":        str(Path.home() / "AppData"),
    "app data":       str(Path.home() / "AppData"),
    "temp":           os.environ.get("TEMP", "C:\\Windows\\Temp"),
    "windows":        "C:\\Windows",
    "imagination":    "D:\\imagination",
    "projects":       str(Path.home() / "Documents"),
}

# Start Menu search paths
_START_MENU_PATHS = [
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
    str(Path.home() / r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs"),
]

_STRIP = re.compile(r"^(?:my|the|a|an|our)\s+|\s+(?:folder|directory|drive|location|path)$", re.I)

SEARCH_ROOTS = [
    str(Path.home() / "Desktop"),
    str(Path.home() / "Documents"),
    str(Path.home() / "Downloads"),
    str(Path.home() / "Pictures"),
    str(Path.home() / "Videos"),
    str(Path.home() / "Music"),
    "D:\\",
    "C:\\Users",
]


# ── Main dispatcher ───────────────────────────────────────────────────────────

def handle_command(text: str):
    lower = text.lower().strip()

    # 1. Explicit URL ──────────────────────────────────────────────
    m = re.search(r"open\s+(https?://\S+)", lower)
    if m:
        webbrowser.open(m.group(1))
        return f"Opening {m.group(1)}."

    # 2. Website / domain ──────────────────────────────────────────
    m = re.search(
        r"(?:open|go\s+to|visit|browse)\s+(?:the\s+)?(?:website\s+)?(\w[\w.-]+\.\w{2,6}(?:/\S*)?)",
        lower,
    )
    if m:
        site = m.group(1)
        url = f"https://{site}" if not site.startswith("http") else site
        webbrowser.open(url)
        return f"Opening {site}."

    # 3. System control ────────────────────────────────────────────
    if re.search(r"\bshut\s*down\b|\bpower\s*off\b", lower):
        subprocess.Popen("shutdown /s /t 10", shell=True)
        return "Shutting down in 10 seconds. Say cancel shutdown to abort."
    if "cancel shutdown" in lower:
        subprocess.Popen("shutdown /a", shell=True)
        return "Shutdown cancelled."
    if re.search(r"\brestart\b|\breboot\b", lower):
        subprocess.Popen("shutdown /r /t 10", shell=True)
        return "Restarting in 10 seconds."
    if re.search(r"\block\b.*(pc|screen|computer|system)|(pc|screen|computer|system).*\block\b", lower):
        ctypes.windll.user32.LockWorkStation()
        return "PC locked."

    # 4. Volume ────────────────────────────────────────────────────
    if re.search(r"\bvolume\s*up\b|\bincrease\s+volume\b", lower):
        _press_key(0xAF, count=5); return "Volume increased."
    if re.search(r"\bvolume\s*down\b|\bdecrease\s+volume\b", lower):
        _press_key(0xAE, count=5); return "Volume decreased."
    if re.search(r"\bmute\b|\bunmute\b", lower):
        _press_key(0xAD); return "Volume toggled."

    # 5. Screenshot ────────────────────────────────────────────────
    if re.search(r"\bscreenshot\b|\bscreen\s*capture\b|\bsnip\b", lower):
        _press_key_combo(); return "Taking a screenshot."

    # 6. Open / Launch ─────────────────────────────────────────────
    m = re.match(r"^(?:open|launch|start|run|show|go\s+to)\s+(.+)$", lower)
    if m:
        target = _clean(m.group(1))
        result = _resolve_open(target)
        if result:
            return result

    # 7. Find / locate file ────────────────────────────────────────
    m = re.search(
        r"(?:find|locate|where\s+is|search\s+for)\s+(?:the\s+)?(?:file\s+)?[\"']?(.+?)[\"']?\s*$",
        lower,
    )
    if m:
        return _find_and_open_file(_clean(m.group(1)))

    # 8. List files ────────────────────────────────────────────────
    m = re.search(
        r"(?:list|show|what(?:'s|\s+is|\s+are)(?:\s+in)?)\s+(?:files?\s+(?:in|on|inside)\s+)?(?:the\s+|my\s+)?(.+?)(?:\s+folder)?\s*$",
        lower,
    )
    if m:
        result = _list_files(_clean(m.group(1)))
        if result:
            return result

    return None


# ── Internal helpers ──────────────────────────────────────────────────────────

def _clean(s: str) -> str:
    return _STRIP.sub("", s).strip()


def _resolve_open(target: str):
    """
    Priority order:
    1. Folder alias
    2. Raw path (folder / file)
    3. Direct known path (APP_DIRECT_PATHS)
    4. Shell command (APP_SHELL_COMMANDS)
    5. Start Menu shortcut search (.lnk)
    6. `where` command (PATH)
    7. Recursive install dir search (limited)
    8. Subfolder search in SEARCH_ROOTS
    9. File search
    """
    key = target.lower()

    # 1. Folder alias
    folder_path = FOLDER_ALIASES.get(key)
    if folder_path and os.path.exists(folder_path):
        subprocess.Popen(f'explorer "{folder_path}"')
        return f"Opening {target} folder."

    # 2. Raw path
    if os.path.isdir(target):
        subprocess.Popen(f'explorer "{target}"')
        return f"Opening {target}."
    if os.path.isfile(target):
        os.startfile(target)
        return f"Opening {target}."

    # 3. Direct known paths (glob-aware)
    for alias_key, paths in APP_DIRECT_PATHS.items():
        if key == alias_key or key in alias_key or alias_key in key:
            for path_pattern in paths:
                # Expand glob patterns (e.g. Discord\app-*\Discord.exe)
                matches = glob.glob(path_pattern)
                if matches:
                    exe = sorted(matches)[-1]  # pick latest version
                    if os.path.isfile(exe):
                        subprocess.Popen(f'"{exe}"', shell=True)
                        return f"Opening {alias_key}."
                elif os.path.isfile(path_pattern):
                    subprocess.Popen(f'"{path_pattern}"', shell=True)
                    return f"Opening {alias_key}."

    # 4. Shell commands
    exe = APP_SHELL_COMMANDS.get(key)
    if exe:
        if exe.startswith("ms-"):
            os.startfile(exe)
        elif exe.endswith(".msc"):
            subprocess.Popen(f'mmc "{exe}"', shell=True)
        else:
            subprocess.Popen(exe, shell=True)
        return f"Opening {target}."

    # 5. Start Menu shortcut search
    result = _search_start_menu(key)
    if result:
        return result

    # 6. `where` command — finds anything in PATH
    result = _search_path(target)
    if result:
        return result

    # 7. Partial folder alias
    for alias_key, alias_path in FOLDER_ALIASES.items():
        if key in alias_key or alias_key in key:
            if os.path.exists(alias_path):
                subprocess.Popen(f'explorer "{alias_path}"')
                return f"Opening {alias_key} folder."

    # 8. Subfolder search
    for root in SEARCH_ROOTS:
        if not os.path.isdir(root):
            continue
        for d in glob.glob(os.path.join(root, "**", f"*{target}*"), recursive=True):
            if os.path.isdir(d):
                subprocess.Popen(f'explorer "{d}"')
                return f"Opening folder: {os.path.basename(d)}."

    # 9. File search
    return _find_and_open_file(target)


def _search_start_menu(app_name: str):
    """Search Start Menu .lnk shortcuts for the app name."""
    best_match = None
    best_score = 0

    for start_path in _START_MENU_PATHS:
        if not os.path.isdir(start_path):
            continue
        for lnk in glob.glob(os.path.join(start_path, "**", "*.lnk"), recursive=True):
            lnk_name = Path(lnk).stem.lower()
            # Score: exact match > startswith > contains
            if lnk_name == app_name:
                score = 3
            elif lnk_name.startswith(app_name) or app_name.startswith(lnk_name):
                score = 2
            elif app_name in lnk_name or lnk_name in app_name:
                score = 1
            else:
                continue
            if score > best_score:
                best_score = score
                best_match = lnk

    if best_match:
        try:
            os.startfile(best_match)
            return f"Opening {Path(best_match).stem}."
        except Exception as e:
            print(f"[StartMenu] Failed to open {best_match}: {e}")

    return None


def _search_path(app_name: str):
    """Use `where` to find an executable in PATH."""
    try:
        result = subprocess.run(
            ["where", f"{app_name}*"],
            capture_output=True, text=True, timeout=3, shell=True
        )
        if result.returncode == 0:
            exe = result.stdout.strip().splitlines()[0]
            if os.path.isfile(exe):
                subprocess.Popen(f'"{exe}"', shell=True)
                return f"Opening {app_name}."
    except Exception:
        pass
    return None


def _find_and_open_file(filename: str):
    if os.path.isfile(filename):
        os.startfile(filename)
        return f"Opening {filename}."

    patterns = [filename, f"{filename}.*", f"*{filename}*"]
    for root in SEARCH_ROOTS:
        if not os.path.isdir(root):
            continue
        for pat in patterns:
            for match in glob.glob(os.path.join(root, "**", pat), recursive=True):
                if os.path.isfile(match):
                    try:
                        os.startfile(match)
                        return f"Opening {os.path.basename(match)}."
                    except Exception as e:
                        return f"Found it but couldn't open: {e}"

    return f"I couldn't find '{filename}' in your common folders."


def _list_files(location: str):
    path = FOLDER_ALIASES.get(location.lower(), location)
    if not os.path.isdir(path):
        return None
    try:
        items   = os.listdir(path)
        files   = [f for f in items if os.path.isfile(os.path.join(path, f))]
        folders = [f for f in items if os.path.isdir(os.path.join(path, f))]
        parts = []
        if folders:
            parts.append(f"{len(folders)} folders: {', '.join(folders[:6])}{'...' if len(folders) > 6 else ''}")
        if files:
            parts.append(f"{len(files)} files: {', '.join(files[:6])}{'...' if len(files) > 6 else ''}")
        return ("In " + location + ": " + ". ".join(parts) + ".") if parts else f"{location} appears to be empty."
    except PermissionError:
        return f"Access denied to {location}."


def _press_key(vk_code: int, count: int = 1):
    for _ in range(count):
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)


def _press_key_combo():
    """Win+Shift+S — snipping tool."""
    VK_LWIN, VK_SHIFT, VK_S = 0x5B, 0x10, 0x53
    for k in [VK_LWIN, VK_SHIFT, VK_S]:
        ctypes.windll.user32.keybd_event(k, 0, 0, 0)
    for k in [VK_S, VK_SHIFT, VK_LWIN]:
        ctypes.windll.user32.keybd_event(k, 0, 2, 0)
