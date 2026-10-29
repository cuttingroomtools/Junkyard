#!/usr/bin/env python3
"""
Junkyard for DaVinci Resolve Studio
===================================
© 2026 Joel McDowell. Free to use. All rights reserved.

Flag your junk footage, then send the source files to the yard.

Workflow
--------
1. While reviewing (all-footage timeline or Media Pool), flag junk clips
   with your junk flag colour (default: Cocoa).
2. Workspace > Scripts > Junkyard.
3. The Yard tab lists every junk clip, its size, and every OTHER timeline
   that also uses it. Untick anything you want to keep.
4. Tick what you want done, click Run, then Confirm.

Every option starts OFF. You choose what happens:
  Source files
    - Move to the junkyard folder (_JUNKYARD next to the media, or a
      folder you choose). Folder structure is kept; a log is written.
    - Or move to the Trash (macOS; Finder's Put Back works).
    - Or Burn Pile: delete permanently. Skips the Trash, can't be restored,
      and asks you to type BURN in a pop-up first. Clips used in other
      timelines are never burned.
    - Include sidecars and proxies (camera XML/LRV/THM/SRT etc. and
      linked proxy media).
    - Relink moved clips so they stay playable in Resolve.
  In Resolve
    - Gather the clips in a JUNK bin.
    - Remove them from the Media Pool.
    - Cut and delete gaps: cut them from your chosen timeline and ripple
      everything up.

Safety
------
- Nothing is permanently deleted unless you choose Burn Pile, tick it,
  click Run, Confirm, then type BURN in the pop-up.
- Clips used in other timelines start unticked and are marked in orange.
  If you tick one anyway it is never removed from the Media Pool.
- Restore tab: puts the last run's files back and relinks or re-imports
  the clips. It can't put clips back into the all-footage timeline.

Install
-------
Mac: drag this file into
  ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit/
(in Finder press Cmd+Shift+G and paste that path). Windows: run the installer.
It appears under Workspace > Scripts > Junkyard.

Updates
-------
Junkyard checks for a new version when it opens (at most twice a day) and
installs it with one click. Turn this off on the Report tab.
"""

import os
import re
import csv
import sys
import json
import base64
import shutil
import datetime
import subprocess

APP_TITLE = "Junkyard"
APP_VERSION = "1.2.0"
YARD_FOLDER_NAME = "_JUNKYARD"
JUNK_BIN_NAME = "JUNK"
RESTORE_BIN_NAME = "Junkyard Restored"
LOG_NAME = "junkyard_log.csv"
TRACK_TYPES = ("video", "audio")
IS_MAC = sys.platform == "darwin"

if IS_MAC:
    APP_DIR = os.path.expanduser("~/Library/Application Support/Junkyard")
else:
    APP_DIR = os.path.join(os.path.expanduser("~"), ".junkyard")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
LEDGER_FILE = os.path.join(APP_DIR, "ledger.csv")
ICON_DIR = os.path.join(APP_DIR, "icons")

FLAG_COLOURS = ["Cocoa", "Blue", "Cyan", "Green", "Yellow", "Red", "Pink",
                "Purple", "Fuchsia", "Rose", "Lavender", "Sky", "Mint",
                "Lemon", "Sand", "Cream"]
CLIP_COLOURS = ["Orange", "Apricot", "Yellow", "Lime", "Olive", "Green",
                "Teal", "Navy", "Blue", "Purple", "Violet", "Pink", "Tan",
                "Beige", "Brown", "Chocolate"]
LOCATIONS = ["Media Pool", "Timeline"]

SIDECAR_EXTS = {".xml", ".lrv", ".lrf", ".thm", ".srt", ".xmp", ".bim", ".cpi"}

OPTION_IDS = ("MoveFiles", "Trash", "Burn", "Extras", "Relink", "ToBin", "Remove", "CloseGaps")
FILE_ACTIONS = ("MoveFiles", "Trash", "Burn")

DEFAULTS = {
    "mark_type": "Flag",
    "mark_colour": "Cocoa",
    "location": "Media Pool",
    "timeline_colour": "Brown",
    "dest": "",
    "last_run": None,
    "auto_update": True,
    "seen_version": None,
    "last_check": 0,
    "latest": None,
}

ACCENT = "#E8833A"
MUTED = "#9C9C9C"

# Tab icons (48px PNG, base64)
ICONS = {
    "yard_off": "iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAABmJLR0QA/wD/AP+gvaeTAAADJklEQVRoge1Zz2vUQBT+ZkbaLmFLwVYQxNWTiKXHnvwDCt4LXoSFNHsriGcFFcFLqfRS2k1b8CLs3b/Ak3qSKtJja3tx/dmy3bZu5nloUmfHTTaTZNda8p3e5M37Zl5mvvmRADly5MiRIwVYFiQLCwuDlmXdA1CKGbLZaDTmZmdnD9O2fS4tAQAUCoW7RPTEMEYCeJq2bZ6W4F8jkxFoNpvzlmVxGEyh/f39+Sza/u8RKWJdnER0GcAlxtgGgK8Z9+U8EV0DsM0Y2/KfdRV75BQKEycRjafrayTGiUjtQ6TYz7aINXEOEdGdwMcYewFgL6N+FInotsL9HMABYog99kZWq9XE7u7uIQABAFLKScdx3ibscBtc150E8NovesPDw4PT09NenNjYU8gn/B6UGWNjRr2Mhsr1LW7nAXMN1AMjywQ0rnpoxQ4w3cjqAK77dlsCypKLTktfF/8JFxH1PIG/GgXal9xOS1+UX0o5xtixHDnnRgkYTSH17ehTiHN+tZMdx69ymY6AUQLa2+mViHuXgEpORG0JkLJ9qnZMf38S0IZXH4E3IXYcf3+mECJEbNv2qpRySko5Zdv2qh7YxZ94BIyulNVqdYIx9i4oCyEK5XL5wIRDx9ra2pDneU2Fc6JcLq/HjTdaRqWUdSHESbnVao0C2AaA5eXlG5zzl369W47jfFBjw/y6ltBjEX8BoIpxNLCFEA6OD30l325DmF9KOapUo6OjI6N7hlEClUrlF4CfQVnbC4ZC7Ei/xvHDbyM2ktwHsj4PJRYwkCABxljYSnQQYnfz9zeBsL2AiKoANgFs+rYe19EvpUyVQJLPKh2nkG3b7wFcCQsK86c5SgMpNaC9vaRIvAsDp0zEpkdpIEMNpMDpEHEK9DcBzvlnpTiyuLh4wZQjwNLS0kUAI0E5iQaMVyHP8zaEEA0AFgA+MDCw7rruJ1MeHyX8OVDuCSE+mhIk+sGxsrLyiIjuJ4kNAxE9mJmZeWwal+jTYrFYfEhEzwDE/n4TAY8xNrezs2P0gyRAql9MruuWGGM3pZRWknjOeaPVar2qVCpb3WvnyJHjTOI3k9F2MT74VMIAAAAASUVORK5CYII=",
    "yard_on": "iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAABmJLR0QA/wD/AP+gvaeTAAADmklEQVRoge1ZTWgTURD+5m2btpTUgkmbVDH2IEWUHiu2Ch4rnhW8eNSbIB6lIfYHvJSKV6EHL4KexaugNqh4kCpSPEhrtdb4UxNqf/eNBzfZt2my2be7qRTynd5m8r6Z2fl5s7tAAw000EADAUBhkHy4c7Ylms9fBzjlUe18oaNj8sjVxxtBdTcFJQCAaH7lGpgmvO9gRPMrEsCtoLpFUIL/jVAiUOjonIrm80IvhfZNhaF7z8O1iMuLk5kOEfFBljRHgn+EaQhL2k+C+5hpkYgXLPNqFrtrCpUXJ4EBBoj4ODgs0y1usrihctcu9gBFHKYH/rlcI6AWJzG1MviSLaX7IBR8a3aAomBcLF4x6B4Rr3spds8HGT84byzPfd4AYAAAMwaS6ZlXvm1WsDR+coCYXliXZnffgRa68ND0stdzClmEv+wfKK5lpSu5g+unV+MB/RrI2UoRngOmwsWcc/nnDmgdZATkGDgKAALS4YDdcoFKrc9VThQvFTJR/RyQjBwVq0Y6U0htuZVan5tcQMbZKkdSo+wBeikk7PDyjhSi3sprD3KlBmRdHWChkodWAyz914CWAwSVnJ0OMHHFtRe5I5qinhFQu1BZG2X5suLak9y+GSTqmkJKBNiZQol0dpokD5Pk4UQ6O12+1V1OvlNI65FyeeJEP0vjTfF6zYy09WaerOtwlONj5kxrm7G5VvqBuT+Rzs563a/VRgUiORP2IdmMtRiARQBYGh06RsSP/tlA55Lp5+/UvdXkkSYZV2c5Ibfrl0Kx2J/vUEbHSLMRK64JfBlACkDKWjtQTd4st2LK3zielFrPGXpd6MrrLQC/S9q2ldwVaK24riFnpRkQsGLp8Aw/zwPKYSaDnwXqIcZ6HQgI6ICjf0usV1zXkLMyU5HmHAT4ccBxl5QUMnAXwDyAeWvtRDW5Y6bSa6GAn9cqArlSGSsRSNyYeQvgcLVtVeXOmWo3IqDcJRnKQ41yiO1KDQiliDkEB9ROpp9C2g6QEgERwkTKrMxBmoOcZYO2RjsCITggyP8oDfiJAOGbctn5NTPYpctRRG7idJKBzhK3Dwe0u9C23JwTRmQVoHYAAgZml8cGP+nyAIApzRTsgbKwKlve63L4+sCxNDY0SuARP3urG8Lp7pHsmO4+X68WE309N8F0G4Dn9zcuMBmY7DKzGh9IbAT6xPRlfDBlgE5BcrsvAkGr5jY97ck8WwhiRwMNNLCH8Rf+Zo91b9wWQwAAAABJRU5ErkJggg==",
    "restore_off": "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",
    "restore_on": "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",
    "report_off": "iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAABmJLR0QA/wD/AP+gvaeTAAAA6UlEQVRoge3YQQrCMBAF0G8QpOQQxQsGxDMIbqSQC4qHaIub1I2LIrVNiJMx8N8qizLpp5kkFCAiIiKiau2kCnvvD9baMwD0fX9zzj0l5tlLFAWApmlO0zRd3uMA4Coxj5EoCgDGmOPS+OfzSBUupfoAYj0QK7fZ1QPkNrv6EsptdvUAuaoPkNwDpU7YWMkBSp2wsZKXUKkTNlb1PcAA2hhAGwNoSw4QQrgvjaWf+yb5JB7HsbPWGgAYhqEr9Rz9q9X/QrObZ1vofT49tm68qz0wv3lq2brxVr+Nrn6B2Q6htoS4MxERiXoBLdptHyEuAQkAAAAASUVORK5CYII=",
    "report_on": "iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAABmJLR0QA/wD/AP+gvaeTAAAA70lEQVRoge3YMQrCMBQG4D9FcGr1BuLgYbyMIJ5BcJGCl/EwDuINJJ1cTIcKVShp2viSBv5vekNJ+tO8JBQgIiIiomQpqYFvl+081/oAAFVRnDe760tinpnEoACQ6+ceRh0/9RvASWKeTGLQhlp31/8lGCCM5AOI9YAr32aPHsC32SewhPyafQIB/CQfYHAPhDphXQ0OEOqEdTViCYU5YV0l3wMMEBsDxMYAsY0IYO7dtfRz3QafxFWxLHOts6ZelKGeo6my/hdqb55mFeqFfqlH343X2gPfN884TO+NN/lt1PoF2h0i5hLizkREJKgGu6JjcsBGVCgAAAAASUVORK5CYII=",
}




# ==========================================================================
# Connection
# ==========================================================================

def connect():
    g = globals()
    bmd_mod = g.get("bmd")
    if bmd_mod is None:
        try:
            import DaVinciResolveScript as bmd_mod
        except ImportError:
            bmd_mod = None
    r = g.get("resolve")
    if r is None and bmd_mod is not None:
        try:
            r = bmd_mod.scriptapp("Resolve")
        except Exception:
            r = None
    return r, bmd_mod


# ==========================================================================
# General helpers
# ==========================================================================

def ensure_app_dir():
    try:
        os.makedirs(APP_DIR, exist_ok=True)
    except Exception:
        pass


def human(n):
    n = float(n)
    sign = "-" if n < 0 else ""
    n = abs(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return "%s%.1f %s" % (sign, n, unit)
        n /= 1024.0
    return "%s%.1f PB" % (sign, n)


def plural(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def now_stamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE) as f:
            s.update(json.load(f))
    except Exception:
        pass
    return s


def save_settings(s):
    ensure_app_dir()
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass


def write_icons():
    """Write the embedded tab icons to disk once; return {name: path}."""
    paths = {}
    try:
        os.makedirs(ICON_DIR, exist_ok=True)
        for name, data in ICONS.items():
            p = os.path.join(ICON_DIR, "%s_v%s.png" % (name, APP_VERSION))
            if not os.path.exists(p):
                with open(p, "wb") as f:
                    f.write(base64.b64decode(data))
            paths[name] = p
    except Exception:
        pass
    return paths


def safe_name(text):
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in (text or "Project")).strip()


def unique_dest(dest):
    if not os.path.exists(dest):
        return dest
    base, ext = os.path.splitext(dest)
    i = 1
    while os.path.exists("%s_%d%s" % (base, i, ext)):
        i += 1
    return "%s_%d%s" % (base, i, ext)


def volume_key(path):
    drive, _ = os.path.splitdrive(path)
    if drive:
        return drive
    parts = path.split(os.sep)
    if len(parts) > 2 and parts[1] == "Volumes":
        return os.sep.join(parts[:3])
    return os.sep


def usable_root(root):
    if not root:
        return False
    rest = os.path.splitdrive(root)[1]
    return rest not in ("", os.sep) and root != os.path.join(os.sep, "Volumes")


def rel_for(path, root):
    if usable_root(root):
        return os.path.relpath(path, root)
    return os.path.join(os.path.basename(os.path.dirname(path)), os.path.basename(path))


def common_dir(paths):
    try:
        return os.path.commonpath([os.path.dirname(p) for p in paths])
    except ValueError:
        return ""


def plan_destinations(paths, chosen, tag):
    """Return [(src, dst, dest_root)], keeping folder structure."""
    out = []
    if not paths:
        return out
    if chosen:
        dest_root = os.path.join(chosen, tag)
        root = common_dir(paths)
        for p in paths:
            out.append((p, os.path.join(dest_root, rel_for(p, root)), dest_root))
        return out
    groups = {}
    for p in paths:
        groups.setdefault(volume_key(p), []).append(p)
    for vol, ps in groups.items():
        root = common_dir(ps) or vol
        base = root if usable_root(root) else (os.path.expanduser("~") if vol == os.sep else vol)
        dest_root = os.path.join(base, YARD_FOLDER_NAME, tag)
        for p in ps:
            out.append((p, os.path.join(dest_root, rel_for(p, root)), dest_root))
    return out


def size_of(path):
    try:
        return os.path.getsize(path)
    except Exception:
        return 0


def reveal(path):
    try:
        if IS_MAC:
            subprocess.Popen(["open", path])
        elif os.name == "nt":
            subprocess.Popen(["explorer", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def applescript_str(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def mac_trash(path):
    """Move to the Trash through Finder (so Put Back works). Returns the new path."""
    out = subprocess.check_output([
        "osascript",
        "-e", "set f to (POSIX file %s) as alias" % applescript_str(path),
        "-e", 'tell application "Finder" to set t to delete f',
        "-e", "return POSIX path of (t as alias)",
    ], stderr=subprocess.STDOUT, timeout=120)
    return out.decode("utf-8", "replace").strip()


# ==========================================================================
# Sidecars and proxies
# ==========================================================================

class SidecarFinder(object):
    """Finds camera sidecar files next to a clip (cached per folder)."""

    def __init__(self):
        self.cache = {}

    def listing(self, folder):
        if folder not in self.cache:
            try:
                self.cache[folder] = os.listdir(folder)
            except Exception:
                self.cache[folder] = []
        return self.cache[folder]

    def find(self, path):
        folder, name = os.path.split(path)
        stem = os.path.splitext(name)[0].lower()
        alt = "gl" + stem[2:] if stem[:2] in ("gx", "gh") else None   # GoPro low-res
        sony = re.compile(re.escape(stem) + r"m\d\d$")                  # Sony C0001M01.XML
        out = []
        for entry in self.listing(folder):
            s, x = os.path.splitext(entry)
            if x.lower() not in SIDECAR_EXTS:
                continue
            sl = s.lower()
            if sl == stem or (alt and sl == alt) or sony.match(sl):
                full = os.path.join(folder, entry)
                if full != path and os.path.isfile(full):
                    out.append(full)
        return out


# ==========================================================================
# Resolve helpers
# ==========================================================================

def safe_call(obj, method, *args, **kw):
    default = kw.get("default")
    try:
        result = getattr(obj, method)(*args)
        return default if result is None else result
    except Exception:
        return default


def clip_path(mpi):
    if not mpi:
        return None
    p = safe_call(mpi, "GetClipProperty", "File Path", default="")
    return p or None


def proxy_path(mpi, src):
    p = safe_call(mpi, "GetClipProperty", "Proxy Media Path", default="") or ""
    if p and p != src and os.path.isfile(p):
        return p
    return None


def item_mpi(item):
    return safe_call(item, "GetMediaPoolItem")


def is_marked(obj, mark_type, colour):
    if mark_type == "Flag":
        flags = safe_call(obj, "GetFlagList", default=[])
        if isinstance(flags, dict):
            flags = list(flags.values())
        return colour in (flags or [])
    return (safe_call(obj, "GetClipColor", default="") or "") == colour


def walk_pool(folder):
    for mpi in safe_call(folder, "GetClipList", default=[]) or []:
        yield mpi
    for sub in safe_call(folder, "GetSubFolderList", default=[]) or []:
        for mpi in walk_pool(sub):
            yield mpi


def pool_by_path(mp):
    pool = {}
    for mpi in walk_pool(mp.GetRootFolder()):
        p = clip_path(mpi)
        if p:
            pool.setdefault(p, []).append(mpi)
    return pool


def find_bin(mp, name):
    root = mp.GetRootFolder()
    for sub in safe_call(root, "GetSubFolderList", default=[]) or []:
        if safe_call(sub, "GetName", default="") == name:
            return sub
    return mp.AddSubFolder(root, name)


def timeline_id(t):
    return safe_call(t, "GetUniqueId", default=None) or safe_call(t, "GetName", default="")


def track_items(t, ttype, i):
    return safe_call(t, "GetItemListInTrack", ttype, i, default=[]) or []


# ==========================================================================
# Ledger (Report tab)
# ==========================================================================

LEDGER_FIELDS = ["when", "project", "action", "clips", "bytes", "destination"]


def ledger_add(row):
    ensure_app_dir()
    new = not os.path.exists(LEDGER_FILE)
    try:
        with open(LEDGER_FILE, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
            if new:
                w.writeheader()
            w.writerow(row)
    except Exception:
        pass


def ledger_rows():
    try:
        with open(LEDGER_FILE, newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


# ==========================================================================
# Updates and What's new
# ==========================================================================

GITHUB_USER = "cuttingroomtools"
UPDATE_URL = "https://raw.githubusercontent.com/%s/junkyard/main/version.json" % GITHUB_USER
CHECK_EVERY_HOURS = 12

# Newest first. Shown once in the What's new window after each update.
RELEASE_NOTES = [
    ("1.2.0", [
        "One-click updates. Junkyard tells you when a new version is out and installs it for you.",
        "This What's new window, shown once after each update.",
        "Restored clips now go into a 'Junkyard Restored' bin so they're easy to review.",
        "Find junk in the Media Pool (flags or clip colours) or a Timeline (clip colours).",
        "Junkyard remembers your junk colour for each mode.",
        "Fixes: Burn Pile can be run on its own, results stay on screen, tidier layout.",
    ]),
]


def version_tuple(v):
    out = []
    for part in str(v or "0").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out + [0] * (3 - len(out)))


def http_get(url, timeout=4):
    """Fetch a URL. Falls back to curl when Python's certificates aren't set up."""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Junkyard/%s" % APP_VERSION,
                                                   "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        pass
    try:
        return subprocess.check_output(["curl", "-fsSL", "--max-time", str(timeout), url],
                                       stderr=subprocess.DEVNULL, timeout=timeout + 2)
    except Exception:
        return None


def fetch_latest():
    """Return the published version info, or None if it can't be reached."""
    if "PLACEHOLDER" in GITHUB_USER:
        return None
    data = http_get(UPDATE_URL + "?t=%d" % int(datetime.datetime.now().timestamp()))
    if not data:
        return None
    try:
        info = json.loads(data.decode("utf-8"))
        return info if info.get("version") and info.get("url") and info.get("sha256") else None
    except Exception:
        return None


def script_candidates():
    paths = []
    f = globals().get("__file__")
    if f:
        paths.append(os.path.abspath(f))
    if IS_MAC:
        bases = [os.path.expanduser("~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts"),
                 "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts"]
    elif os.name == "nt":
        bases = [os.path.join(os.environ.get("APPDATA", ""), "Blackmagic Design", "DaVinci Resolve",
                              "Support", "Fusion", "Scripts"),
                 os.path.join(os.environ.get("PROGRAMDATA", ""), "Blackmagic Design", "DaVinci Resolve",
                              "Fusion", "Scripts")]
    else:
        bases = [os.path.expanduser("~/.local/share/DaVinciResolve/Fusion/Scripts"),
                 "/opt/resolve/Fusion/Scripts"]
    for base in bases:
        for sub in ("Edit", "Utility", "Comp", "Color", "Deliver"):
            paths.append(os.path.join(base, sub, "Junkyard.py"))
    return paths


def installed_script():
    """The Junkyard.py Resolve is running, or None if it can't be found."""
    for p in script_candidates():
        if os.path.lexists(p):
            return p
    return None


def is_dev_install(path):
    return bool(path) and os.path.islink(path)


def install_update(info, path):
    """Download, verify and install the new version. Returns (ok, message)."""
    import hashlib
    data = http_get(info["url"], timeout=20)
    if not data:
        return False, "Couldn't download the update. Check your internet connection and try again."
    if hashlib.sha256(data).hexdigest().lower() != str(info["sha256"]).lower():
        return False, "The download didn't match the published fingerprint, so it wasn't installed."
    try:
        source = data.decode("utf-8")
        compile(source, "Junkyard.py", "exec")
    except Exception:
        return False, "The download looks damaged, so it wasn't installed."
    if "APP_TITLE = \"Junkyard\"" not in source:
        return False, "The download isn't a Junkyard script, so it wasn't installed."
    try:
        backups = os.path.join(APP_DIR, "backups")
        os.makedirs(backups, exist_ok=True)
        shutil.copy2(path, os.path.join(backups, "Junkyard_%s.py" % APP_VERSION))
        tmp = path + ".download"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception as e:
        return False, "Couldn't install the update: %s" % e
    return True, ("Updated to %s. Close Junkyard and open it again from Workspace › Scripts."
                  % info["version"])


def notes_since(seen):
    """Release notes newer than the version last seen, newest first."""
    return [(v, n) for v, n in RELEASE_NOTES
            if version_tuple(v) > version_tuple(seen) and version_tuple(v) <= version_tuple(APP_VERSION)]


# ==========================================================================
# The window
# ==========================================================================

class Junkyard(object):

    def __init__(self, resolve_app, bmd_mod):
        self.resolve = resolve_app
        self.settings = load_settings()
        self.rows = []
        self.timelines = []
        self.armed = None
        self.loading = True
        self.page = 0

        self.fusion = resolve_app.Fusion()
        self.ui = ui = self.fusion.UIManager
        self.disp = bmd_mod.UIDispatcher(ui)
        self.icons = write_icons()

        heading = lambda t: ui.Label({"Text": "<b>%s</b>" % t, "Weight": 0})

        yard_page = ui.VGroup({"Spacing": 8}, [
            ui.HGroup({"Weight": 0, "Spacing": 10}, [
                ui.Label({"Text": "Find junk in", "Weight": 0, "MinimumSize": [120, 0], "MaximumSize": [120, 40]}),
                ui.ComboBox({"ID": "Location", "Weight": 1, "ToolTip": "Media Pool: junk is marked on the clips in your bins (flags or clip colours). Timeline: junk is marked with clip colours on the clips in your chosen timeline. Resolve only allows flags in the Media Pool."}),
                ui.HGap(0, 2.15),
            ]),
            ui.HGroup({"Weight": 0, "Spacing": 10}, [
                ui.Label({"Text": "Marked with", "Weight": 0, "MinimumSize": [120, 0], "MaximumSize": [120, 40]}),
                ui.ComboBox({"ID": "MarkType", "Weight": 1, "ToolTip": "Mark junk with a flag or a clip colour. Flags work well if you already use clip colours for cameras. In a timeline, Resolve only allows clip colours."}),
                ui.Label({"Text": "", "Weight": 0, "MinimumSize": [16, 0], "MaximumSize": [16, 40]}),
                ui.ComboBox({"ID": "MarkColour", "Weight": 1, "ToolTip": "The colour that means junk. Junkyard remembers your pick."}),
                ui.HGap(0, 1),
            ]),
            ui.HGroup({"Weight": 0, "Spacing": 10}, [
                ui.Label({"Text": "Timeline", "Weight": 0, "MinimumSize": [120, 0], "MaximumSize": [120, 40]}),
                ui.ComboBox({"ID": "Stringout", "Weight": 1, "ToolTip": "Your all-footage timeline. It's ignored when checking where clips are used, and it's where Cut and delete gaps happens. When finding junk in a timeline, this is the one that's scanned."}),
                ui.Button({"ID": "Refresh", "Text": "Refresh", "Weight": 0, "MinimumSize": [110, 0], "ToolTip": "Re-scan after marking more clips."}),
            ]),
            ui.Tree({"ID": "Tree", "Weight": 1, "SortingEnabled": True,
                     "Events": {"ItemChanged": True, "ItemClicked": True}}),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"ID": "Totals", "Text": ""}),
                ui.Button({"ID": "TickAll", "Text": "Tick all", "Weight": 0, "ToolTip": "Tick every junk clip. Clips used in other timelines stay unticked."}),
                ui.Button({"ID": "TickNone", "Text": "Untick all", "Weight": 0, "ToolTip": "Untick every clip."}),
            ]),
            ui.VGap(2),
            heading("Source files"),
            ui.HGroup({"Weight": 0}, [
                ui.CheckBox({"ID": "MoveFiles", "Text": "Move to junkyard folder", "Weight": 0, "ToolTip": "Moves the source files to _JUNKYARD next to the media, or a folder you choose. Folder structure is kept and a log is saved. Nothing is deleted."}),
                ui.LineEdit({"ID": "Dest", "PlaceholderText":
                             "%s next to the media (default)" % YARD_FOLDER_NAME}),
                ui.Button({"ID": "Browse", "Text": "Choose…", "Weight": 0, "ToolTip": "Pick a different junkyard folder."}),
                ui.Button({"ID": "DefaultDest", "Text": "Default", "Weight": 0, "ToolTip": "Go back to _JUNKYARD next to the media."}),
            ]),
            ui.CheckBox({"ID": "Trash", "Weight": 0, "ToolTip": "Moves the files to the Mac Trash instead. Finder's Put Back still works until you empty the Trash.",
                         "Text": "Move to the Trash instead" + ("" if IS_MAC else " (macOS only)")}),
            ui.HGroup({"Weight": 0}, [
                ui.CheckBox({"ID": "Burn", "Weight": 0, "ToolTip": "Deletes the files permanently. They skip the Trash and can't be restored. You'll be asked to type BURN to confirm. Clips used in other timelines are never burned.",
                             "Text": "Burn Pile: delete permanently"}),
                ui.Label({"ID": "BurnWarn", "Weight": 1,
                          "Text": "<span style='color:#E5533D'><b>⚠ Can't be undone. No Restore.</b></span>"}),
            ]),
            ui.CheckBox({"ID": "Extras", "Weight": 0, "ToolTip": "Also moves camera sidecar files (Sony XML, GoPro LRV/THM, DJI SRT) and any linked proxy media with each clip.",
                         "Text": "Include sidecars and proxies (XML, LRV, THM, SRT, proxy media)"}),
            ui.CheckBox({"ID": "Relink", "Weight": 0, "ToolTip": "Points Resolve at the moved files so the clips stay online and playable. Handy for a last look before you bin them. Not needed if you remove them from the Media Pool.",
                         "Text": "Relink moved clips so they stay playable in Resolve"}),
            ui.VGap(2),
            heading("In Resolve"),
            ui.CheckBox({"ID": "ToBin", "Weight": 0, "ToolTip": "Moves the clips into a JUNK bin in the Media Pool so they're all in one place.",
                         "Text": "Gather them in a %s bin" % JUNK_BIN_NAME}),
            ui.CheckBox({"ID": "Remove", "Weight": 0, "ToolTip": "Removes the clips from the Media Pool. Clips used in other timelines are always kept so those edits don't break.",
                         "Text": "Remove them from the Media Pool"}),
            ui.CheckBox({"ID": "CloseGaps", "Weight": 0, "ToolTip": "Cuts the junk clips out of the chosen timeline and ripples everything up. Restore can't undo this part.",
                         "Text": "Cut and delete gaps in the chosen timeline"}),
            ui.VGap(4),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"ID": "Status", "WordWrap": True, "Text": "", "Weight": 1, "MinimumSize": [200, 64], "Alignment": {"AlignTop": True}}),
                ui.Button({"ID": "Run", "Text": "Run", "Weight": 0, "MinimumSize": [150, 32], "MaximumSize": [150, 32], "ToolTip": "First click shows exactly what will happen. Nothing moves until you click Confirm."}),
            ]),
        ])

        restore_page = ui.VGroup({"Spacing": 8}, [
            ui.Label({"ID": "RestoreInfo", "Weight": 0, "WordWrap": True, "Text": ""}),
            ui.Tree({"ID": "RestoreTree", "Weight": 1}),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"ID": "RestoreStatus", "WordWrap": True, "Text": ""}),
                ui.Button({"ID": "Reveal", "Text": "Show in Finder" if IS_MAC else "Show folder", "Weight": 0, "ToolTip": "Open the junkyard folder from the last run."}),
                ui.Button({"ID": "RestoreRun", "Text": "Restore these files", "Weight": 0, "ToolTip": "Moves the last run's files back where they came from and relinks or re-imports them.",
                           "MinimumSize": [170, 32]}),
            ]),
        ])

        report_page = ui.VGroup({"Spacing": 8}, [
            ui.Label({"ID": "ReportTotal", "Weight": 0, "Text": ""}),
            ui.Tree({"ID": "ReportTree", "Weight": 1, "SortingEnabled": True}),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Weight": 1, "WordWrap": True,
                          "Text": "Trash moves count once the Trash is emptied. Restores are subtracted."}),
                ui.Button({"ID": "OpenLedger", "Text": "Open ledger", "Weight": 0, "ToolTip": "Open the folder holding the full history of every run."}),
            ]),
            ui.VGap(6),
            heading("Updates"),
            ui.HGroup({"Weight": 0, "Spacing": 8}, [
                ui.Label({"ID": "VersionInfo", "Weight": 1, "WordWrap": True, "Text": ""}),
                ui.Button({"ID": "WhatsNew", "Text": "What's new", "Weight": 0, "ToolTip": "See what changed in this version."}),
                ui.Button({"ID": "CheckNow", "Text": "Check for updates", "Weight": 0, "ToolTip": "Look for a newer version of Junkyard now."}),
            ]),
            ui.CheckBox({"ID": "AutoCheck", "Weight": 0, "Text": "Check for updates when Junkyard opens",
                         "ToolTip": "Junkyard looks for a new version at most twice a day. It only reads the version number; nothing about you or your projects is sent."}),
            ui.Label({"Weight": 0, "Text": "<span style='color:#7d7d7d'>© 2026 Joel McDowell. Free to use. All rights reserved.</span>"}),
        ])

        def tab(tid, label):
            return ui.VGroup({"Weight": 0, "Spacing": 0}, [
                ui.Button({"ID": tid, "Flat": True, "Weight": 0, "MinimumSize": [64, 34],
                           "IconSize": [24, 24]}),
                ui.Label({"ID": tid + "Label", "Text": label, "Alignment": {"AlignHCenter": True},
                          "Weight": 0}),
            ])

        self.win = self.disp.AddWindow(
            {"ID": "JunkyardWin", "WindowTitle": "%s %s" % (APP_TITLE, APP_VERSION),
             "Geometry": [200, 120, 860, 720]},
            ui.VGroup({"Spacing": 6}, [
                ui.HGroup({"Weight": 0, "Spacing": 8}, [
                    ui.Label({"ID": "UpdateMsg", "Weight": 1, "WordWrap": True, "Text": ""}),
                    ui.Button({"ID": "UpdateNotes", "Text": "What's new", "Weight": 0,
                               "ToolTip": "See what's in the new version."}),
                    ui.Button({"ID": "UpdateGo", "Text": "Update", "Weight": 0, "MinimumSize": [130, 28],
                               "ToolTip": "Download, check and install the new version. Your current version is backed up first."}),
                ]),
                ui.Stack({"ID": "Pages", "Weight": 1}, [yard_page, restore_page, report_page]),
                ui.HGroup({"Weight": 0, "Spacing": 18}, [
                    ui.HGap(0, 1),
                    tab("TabYard", "Yard"),
                    tab("TabRestore", "Restore"),
                    tab("TabReport", "Report"),
                    ui.HGap(0, 1),
                ]),
            ]))

        self.it = self.win.GetItems()
        self.setup_trees()
        self.setup_controls()
        self.bind()
        self.loading = False
        self.show_page(0)

    # ------------------------------------------------------------------ setup

    def make_tree(self, tid, labels, widths):
        tree = self.it[tid]
        tree.ColumnCount = len(labels)
        hdr = tree.NewItem()
        for i, label in enumerate(labels):
            hdr.Text[i] = label
        tree.SetHeaderItem(hdr)
        for i, w in enumerate(widths):
            tree.ColumnWidth[i] = w

    def setup_trees(self):
        self.make_tree("Tree", ["Clip", "Size", "Also used in", "Folder"], [230, 90, 270, 240])
        self.make_tree("RestoreTree", ["File", "Type", "Now at"], [240, 80, 500])
        self.make_tree("ReportTree", ["Project", "Runs", "Clips", "Space freed", "Last run"],
                       [280, 60, 60, 120, 150])

    def setup_controls(self):
        s = self.settings
        loc = self.it["Location"]
        for label in LOCATIONS:
            loc.AddItem(label)
        loc.CurrentIndex = LOCATIONS.index(s.get("location")) if s.get("location") in LOCATIONS else 0
        self.fill_mark_types()
        self._shown_location = loc.CurrentText
        self._shown_type = self.it["MarkType"].CurrentText
        self.fill_timelines()
        self.it["Dest"].Text = s.get("dest", "") or ""
        for cid in OPTION_IDS:
            self.it[cid].Checked = False          # every option starts off
        self.set_update_bar("", False)
        self.apply_rules()

    def in_timeline(self):
        return self.it["Location"].CurrentText == "Timeline"

    def fill_mark_types(self):
        """Timeline clips can only take clip colours, so lock the mark type there."""
        s = self.settings
        mt = self.it["MarkType"]
        mt.Clear()
        if self.in_timeline():
            mt.AddItem("Clip colour")
            mt.Enabled = False
            self.fill_colours(s.get("timeline_colour", "Brown"))
        else:
            for label in ("Flag", "Clip colour"):
                mt.AddItem(label)
            mt.Enabled = True
            mt.CurrentIndex = 1 if s.get("mark_type") == "Clip colour" else 0
            self.fill_colours(s.get("mark_colour"))

    def fill_colours(self, wanted=None):
        mc = self.it["MarkColour"]
        mc.Clear()
        colours = FLAG_COLOURS if self.it["MarkType"].CurrentText == "Flag" else CLIP_COLOURS
        for c in colours:
            mc.AddItem(c)
        if wanted in colours:
            mc.CurrentIndex = colours.index(wanted)

    def fill_timelines(self):
        project = self.project()
        combo = self.it["Stringout"]
        combo.Clear()
        combo.AddItem("(none)")
        self.timelines = [None]
        if not project:
            return
        current = project.GetCurrentTimeline()
        current_id = timeline_id(current) if current else None
        pick = 0
        for i in range(1, (project.GetTimelineCount() or 0) + 1):
            t = project.GetTimelineByIndex(i)
            if not t:
                continue
            self.timelines.append(t)
            combo.AddItem(t.GetName())
            if current_id and timeline_id(t) == current_id:
                pick = len(self.timelines) - 1
        combo.CurrentIndex = pick

    def bind(self):
        on = self.win.On
        on.JunkyardWin.Close = self.on_close
        on.TabYard.Clicked = lambda ev: self.show_page(0)
        on.TabRestore.Clicked = lambda ev: self.show_page(1)
        on.TabReport.Clicked = lambda ev: self.show_page(2)
        on.Refresh.Clicked = lambda ev: self.refresh(reload_timelines=True)
        on.Run.Clicked = self.on_run
        on.Browse.Clicked = self.on_browse
        on.DefaultDest.Clicked = lambda ev: setattr(self.it["Dest"], "Text", "")
        on.TickAll.Clicked = lambda ev: self.tick_all(True)
        on.TickNone.Clicked = lambda ev: self.tick_all(False)
        on.MarkType.CurrentIndexChanged = self.on_mark_type
        on.Location.CurrentIndexChanged = self.on_location
        on.MarkColour.CurrentIndexChanged = self.on_colour
        on.Stringout.CurrentIndexChanged = lambda ev: self.refresh()
        on.Tree.ItemChanged = lambda ev: self.update_totals(disarm=True)
        on.Tree.ItemClicked = lambda ev: self.update_totals(disarm=True)
        on.Dest.TextChanged = lambda ev: self.disarm()
        on.MoveFiles.Clicked = lambda ev: self.on_option("MoveFiles")
        on.Trash.Clicked = lambda ev: self.on_option("Trash")
        for cid in ("Burn", "Extras", "Relink", "ToBin", "Remove", "CloseGaps"):
            setattr(getattr(on, cid), "Clicked", lambda ev, c=cid: self.on_option(c))
        on.RestoreRun.Clicked = self.on_restore
        on.Reveal.Clicked = self.on_reveal
        on.OpenLedger.Clicked = lambda ev: reveal(APP_DIR)
        on.UpdateGo.Clicked = self.on_update
        on.UpdateNotes.Clicked = lambda ev: self.show_notes(remote=True)
        on.WhatsNew.Clicked = lambda ev: self.show_notes(everything=True)
        on.CheckNow.Clicked = lambda ev: self.check_updates(force=True)
        on.AutoCheck.Clicked = self.on_autocheck

    # ------------------------------------------------------------------ tabs

    def show_page(self, index):
        self.page = index
        self.disarm()
        self.it["Pages"].CurrentIndex = index
        for i, (tid, icon) in enumerate((("TabYard", "yard"), ("TabRestore", "restore"),
                                         ("TabReport", "report"))):
            active = (i == index)
            path = self.icons.get("%s_%s" % (icon, "on" if active else "off"))
            try:
                if path:
                    self.it[tid].Icon = self.ui.Icon({"File": path})
                else:
                    self.it[tid].Text = ("● " if active else "") + icon.title()
            except Exception:
                self.it[tid].Text = icon.title()
            try:
                self.it[tid + "Label"].StyleSheet = "color: %s;" % (ACCENT if active else MUTED)
            except Exception:
                pass
        if index == 0:
            self.refresh()

        elif index == 1:
            self.load_restore()
        else:
            self.load_report()

    # ------------------------------------------------------------------ state

    def project(self):
        try:
            return self.resolve.GetProjectManager().GetCurrentProject()
        except Exception:
            return None

    def stringout(self):
        idx = self.it["Stringout"].CurrentIndex
        if idx is None or idx < 0 or idx >= len(self.timelines):
            return None
        return self.timelines[idx]

    def opts(self):
        on = lambda cid: bool(self.it[cid].Checked) and bool(self.it[cid].Enabled)
        o = {k: on(k) for k in OPTION_IDS}
        o["dest"] = (self.it["Dest"].Text or "").strip()
        o["files"] = o["MoveFiles"] or o["Trash"] or o["Burn"]
        return o

    def apply_rules(self):
        move = bool(self.it["MoveFiles"].Checked)
        trash = bool(self.it["Trash"].Checked) and IS_MAC
        burn = bool(self.it["Burn"].Checked)
        remove = bool(self.it["Remove"].Checked)
        self.it["Trash"].Enabled = IS_MAC
        for cid in ("Dest", "Browse", "DefaultDest"):
            self.it[cid].Enabled = move
        self.it["Extras"].Enabled = move or trash or burn
        self.it["Relink"].Enabled = move and not remove
        self.it["ToBin"].Enabled = not remove
        self.it["CloseGaps"].Enabled = self.stringout() is not None
        o = self.opts()
        self.it["Run"].Enabled = any(o[k] for k in ("MoveFiles", "Trash", "Burn", "ToBin", "Remove", "CloseGaps"))

    def remember(self):
        s = self.settings
        s["location"] = self.it["Location"].CurrentText
        if self.in_timeline():
            s["timeline_colour"] = self.it["MarkColour"].CurrentText
            save_settings(s)
            s["dest"] = (self.it["Dest"].Text or "").strip()
            save_settings(s)
            return
        s["mark_type"] = self.it["MarkType"].CurrentText
        s["mark_colour"] = self.it["MarkColour"].CurrentText
        s["dest"] = (self.it["Dest"].Text or "").strip()
        save_settings(s)

    def status(self, text):
        self.it["Status"].Text = text

    def disarm(self):
        self.armed = None
        self.it["Run"].Text = "Run"
        self.it["RestoreRun"].Text = "Restore these files"

    # ------------------------------------------------------------------ yard

    def refresh(self, reload_timelines=False):
        if self.loading:
            return
        self.disarm()
        if reload_timelines:
            self.loading = True
            self.fill_timelines()
            self.loading = False
        self.apply_rules()

        project = self.project()
        tree = self.it["Tree"]
        tree.Clear()
        self.rows = []
        if not project:
            self.status("No project open.")
            self.update_totals()
            return

        mp = project.GetMediaPool()
        mark_type = self.it["MarkType"].CurrentText
        colour = self.it["MarkColour"].CurrentText
        stringout = self.stringout()
        string_id = timeline_id(stringout) if stringout else None

        in_tl = self.in_timeline()
        if in_tl and not stringout:
            self.status("Pick the timeline to scan, or switch Find junk in to Media Pool.")
            self.update_totals()
            return

        pool = {}
        junk = set()
        for mpi in walk_pool(mp.GetRootFolder()):
            p = clip_path(mpi)
            if not p:
                continue
            pool.setdefault(p, []).append(mpi)
            if not in_tl and is_marked(mpi, mark_type, colour):
                junk.add(p)

        string_items = {}
        if stringout:
            for ttype in TRACK_TYPES:
                for i in range(1, (stringout.GetTrackCount(ttype) or 0) + 1):
                    for item in track_items(stringout, ttype, i):
                        p = clip_path(item_mpi(item))
                        if not p:
                            continue
                        string_items.setdefault(p, []).append(item)
                        if in_tl and is_marked(item, "Clip colour", colour):
                            junk.add(p)

        used = {}
        for t in self.timelines[1:]:
            if string_id and timeline_id(t) == string_id:
                continue
            name = t.GetName()
            for ttype in TRACK_TYPES:
                for i in range(1, (t.GetTrackCount(ttype) or 0) + 1):
                    for item in track_items(t, ttype, i):
                        p = clip_path(item_mpi(item))
                        if p in junk:
                            used.setdefault(p, {}).setdefault(name, set()).add("%s%d" % (ttype[0].upper(), i))

        sidecars = SidecarFinder()
        for p in sorted(junk, key=lambda x: os.path.basename(x).lower()):
            exists = os.path.isfile(p)
            mpis = pool.get(p, [])
            extras = []
            if exists:
                extras = [("sidecar", s) for s in sidecars.find(p)]
                for mpi in mpis[:1]:
                    px = proxy_path(mpi, p)
                    if px:
                        extras.append(("proxy", px))
            uses = used.get(p, {})
            use_text = ", ".join("%s (%s)" % (n, ", ".join(sorted(tr))) for n, tr in sorted(uses.items()))

            item = tree.NewItem()
            item.Text[0] = os.path.basename(p)
            item.Text[1] = human(size_of(p)) if exists else "offline"
            item.Text[2] = ("⚠ " + use_text) if use_text else "—"
            item.Text[3] = os.path.dirname(p)
            item.CheckState[0] = "Unchecked" if (use_text or not exists) else "Checked"
            if use_text:
                try:
                    item.TextColor[2] = {"R": 0.91, "G": 0.51, "B": 0.23, "A": 1.0}
                except Exception:
                    pass
            tree.AddTopLevelItem(item)
            self.rows.append({
                "path": p, "item": item, "exists": exists, "size": size_of(p) if exists else 0,
                "extras": extras, "extras_size": sum(size_of(e) for _, e in extras),
                "used": use_text, "mpis": mpis, "string_items": string_items.get(p, []),
            })

        if not self.rows:
            if in_tl:
                where = "in '%s'" % stringout.GetName()
                kind = "clip colour"
            else:
                where = "in the Media Pool"
                kind = "flag" if mark_type == "Flag" else "clip colour"
            self.status("No clips %s marked with a %s %s yet. Mark your junk, then hit Refresh."
                        % (where, colour, kind))
        else:
            self.status("Untick anything you want to keep, pick what to do, then Run.")
        self.update_totals()

    def checked_rows(self):
        out = []
        for r in self.rows:
            try:
                if r["item"].CheckState[0] == "Checked":
                    out.append(r)
            except Exception:
                pass
        return out

    def tick_all(self, on):
        for r in self.rows:
            if on and (r["used"] or not r["exists"]):
                continue                         # never bulk-tick protected clips
            r["item"].CheckState[0] = "Checked" if on else "Unchecked"
        self.update_totals(disarm=True)

    def update_totals(self, disarm=False):
        if disarm:
            self.disarm()
        sel = self.checked_rows()
        size = sum(r["size"] for r in sel)
        extras = sum(r["extras_size"] for r in sel)
        text = "%d of %d clips ticked  ·  %s" % (len(sel), len(self.rows), human(size))
        if extras:
            text += "  (+ %s sidecars and proxies)" % human(extras)
        self.it["Totals"].Text = text

    # ------------------------------------------------------------------ events

    def on_close(self, ev):
        self.remember()
        self.disp.ExitLoop()

    def on_location(self, ev):
        # Ignore events that fire while the window is built or that don't change anything
        loc = self.it["Location"].CurrentText
        if self.loading or loc == getattr(self, "_shown_location", None):
            return
        self._shown_location = loc
        self.loading = True
        self.fill_mark_types()
        self._shown_type = self.it["MarkType"].CurrentText
        self.loading = False
        self.refresh()

    def on_colour(self, ev):
        if self.loading:
            return
        # Remember the colour for the mode it was picked in
        key = "timeline_colour" if self.in_timeline() else "mark_colour"
        self.settings[key] = self.it["MarkColour"].CurrentText
        if not self.in_timeline():
            self.settings["mark_type"] = self.it["MarkType"].CurrentText
        self.refresh()

    def on_mark_type(self, ev):
        mt = self.it["MarkType"].CurrentText
        if self.loading or self.in_timeline() or mt == getattr(self, "_shown_type", None):
            return
        self._shown_type = mt
        self.loading = True
        s = self.settings
        self.fill_colours(s.get("mark_colour") if mt == s.get("mark_type") else None)
        self.loading = False
        self.refresh()

    def on_option(self, cid):
        # Move, Trash and Burn Pile are either/or
        if cid in FILE_ACTIONS and self.it[cid].Checked:
            for other in FILE_ACTIONS:
                if other != cid:
                    self.it[other].Checked = False
        self.apply_rules()
        self.disarm()

    def on_browse(self, ev):
        start = self.it["Dest"].Text or os.path.expanduser("~")
        path = None
        try:
            path = self.fusion.RequestDir(start)
        except Exception:
            path = None
        if path:
            self.it["Dest"].Text = str(path).rstrip("/\\")
        else:
            self.status("No folder picked. You can also paste a folder path into the box.")

    # ------------------------------------------------------------------ run

    def on_run(self, ev):
        sel = self.checked_rows()
        o = self.opts()
        if not sel:
            self.status("Nothing ticked.")
            return
        if o["MoveFiles"] and o["dest"] and not os.path.isdir(o["dest"]):
            self.status("That junkyard folder doesn't exist.")
            return
        if self.armed != "run":
            self.armed = "run"
            self.it["Run"].Text = "Confirm"
            self.status(self.describe(sel, o))
            return
        self.disarm()
        self.remember()
        if o["Burn"]:
            self.open_burn_dialog(sel, o)
            return
        msg = self.execute(sel, o)
        self.refresh()
        self.status(msg)            # keep the result visible after the list refreshes

    def open_burn_dialog(self, sel, o):
        burnable = [r for r in sel if r["exists"] and not r["used"]]
        if not burnable:
            self.status("Nothing to burn. Clips used in other timelines are never burned.")
            return
        size = sum(r["size"] + (r["extras_size"] if o["Extras"] else 0) for r in burnable)
        names = [os.path.basename(r["path"]) for r in burnable]
        shown = ", ".join(names[:8]) + (" and %d more" % (len(names) - 8) if len(names) > 8 else "")
        ui = self.ui
        self.it["Run"].Enabled = False
        dlg = self.disp.AddWindow(
            {"ID": "BurnDlg", "WindowTitle": "Burn Pile", "Geometry": [320, 220, 560, 380]},
            ui.VGroup({"Spacing": 10}, [
                ui.Label({"Weight": 0, "WordWrap": True, "MinimumSize": [0, 30], "Text":
                          "<span style='color:#E5533D; font-size:15px'><b>Permanently delete %s (%s)?</b></span>"
                          % (plural(len(burnable), "file"), human(size))}),
                ui.Label({"Weight": 0, "WordWrap": True, "MinimumSize": [0, 48], "Text":
                          "These files skip the Trash and can't be restored by Junkyard. "
                          "Make sure you have a backup if there's any doubt."}),
                ui.Label({"Weight": 1, "WordWrap": True, "MinimumSize": [0, 40],
                          "Alignment": {"AlignTop": True}, "Text": "<i>%s</i>" % shown}),
                ui.Label({"Weight": 0, "MinimumSize": [0, 24], "Text": "Type <b>BURN</b> to confirm:"}),
                ui.LineEdit({"ID": "BurnText", "Weight": 0, "PlaceholderText": "BURN"}),
                ui.HGroup({"Weight": 0}, [
                    ui.HGap(0, 1),
                    ui.Button({"ID": "BurnCancel", "Text": "Cancel", "Weight": 0}),
                    ui.Button({"ID": "BurnGo", "Text": "Burn forever", "Weight": 0,
                               "Enabled": False, "MinimumSize": [130, 30]}),
                ]),
            ]))
        di = dlg.GetItems()

        def typed(ev):
            di["BurnGo"].Enabled = (di["BurnText"].Text or "").strip() == "BURN"

        def close(ev=None):
            dlg.Hide()
            self.apply_rules()
            self.status("Burn cancelled. Nothing was deleted.")

        def go(ev):
            if (di["BurnText"].Text or "").strip() != "BURN":
                return
            dlg.Hide()
            msg = self.execute(sel, o)
            self.refresh()
            self.status(msg)

        dlg.On.BurnText.TextChanged = typed
        dlg.On.BurnCancel.Clicked = close
        dlg.On.BurnDlg.Close = close
        dlg.On.BurnGo.Clicked = go
        dlg.Show()
        self.status("Waiting for you to confirm the burn in the pop-up.")

    def describe(self, sel, o):
        size = sum(r["size"] for r in sel) + (sum(r["extras_size"] for r in sel) if o["Extras"] else 0)
        steps = []
        if o["MoveFiles"]:
            steps.append("move %s to %s" % (human(size), o["dest"] or YARD_FOLDER_NAME + " next to the media"))
        if o["Trash"]:
            steps.append("move %s to the Trash" % human(size))
        if o["Burn"]:
            burn_size = sum(r["size"] + (r["extras_size"] if o["Extras"] else 0)
                            for r in sel if not r["used"])
            steps.append("PERMANENTLY DELETE %s (no Restore)" % human(burn_size))
        if o["Relink"]:
            steps.append("relink them")
        if o["ToBin"]:
            steps.append("gather them in the %s bin" % JUNK_BIN_NAME)
        if o["Remove"]:
            steps.append("remove them from the Media Pool")
        if o["CloseGaps"]:
            steps.append("cut and delete gaps in '%s'" % self.stringout().GetName())
        text = "%s: %s." % (plural(len(sel), "clip"), "; ".join(steps))
        risky = [r for r in sel if r["used"]]
        if risky and o["Burn"]:
            text += "\n⚠ %d ticked clip(s) are used in other timelines, so they won't be burned." % len(risky)
        elif risky:
            text += "\n⚠ %d ticked clip(s) are used in other timelines and will stay in the Media Pool" % len(risky)
            text += (", but those edits will go offline." if o["files"] and not o["Relink"] else ".")
        if o["CloseGaps"]:
            text += "\nRestore can't undo the timeline cut."
        if o["Burn"]:
            return text + "\nClick Confirm, then type BURN in the pop-up."
        return text + "\nClick Confirm to go."

    def execute(self, sel, o):
        project = self.project()
        mp = project.GetMediaPool()
        notes = []

        # 1. Cut and delete gaps in the chosen timeline
        stringout = self.stringout()
        if o["CloseGaps"] and stringout:
            items = [it for r in sel for it in r["string_items"]]
            if items:
                try:
                    ok = stringout.DeleteClips(items, True)
                    notes.append("cut %d clips and deleted the gaps" % len(items) if ok else "cut and delete gaps failed")
                except Exception:
                    notes.append("couldn't cut the timeline clips")

        # 2. Source files
        moved = {}          # original clip path -> new clip path
        moved_proxy = {}    # original clip path -> new proxy path
        failed = []
        protected = []
        log_rows = {}
        freed = 0
        if o["files"]:
            jobs = []       # (kind, clip, src)
            for r in sel:
                if not r["exists"]:
                    continue
                if o["Burn"] and r["used"]:
                    protected.append(os.path.basename(r["path"]))
                    continue
                jobs.append(("clip", r["path"], r["path"]))
                if o["Extras"]:
                    for kind, extra in r["extras"]:
                        jobs.append((kind, r["path"], extra))

            if o["MoveFiles"]:
                stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
                tag = "%s_%s" % (safe_name(project.GetName()), stamp)
                plan = {src: (dst, root) for src, dst, root in
                        plan_destinations([j[2] for j in jobs], o["dest"], tag)}

            for kind, clip, src in jobs:
                if kind != "clip" and clip not in moved:
                    continue                    # only take extras with a clip that moved
                bytes_ = size_of(src)
                try:
                    if o["MoveFiles"]:
                        dst, root = plan[src]
                        dst = unique_dest(dst)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.move(src, dst)
                    elif o["Burn"]:
                        os.remove(src)
                        dst, root = "", "Burn"
                    else:
                        dst = mac_trash(src)
                        root = "Trash"
                    status = "deleted" if o["Burn"] else "moved"
                    freed += bytes_
                    if kind == "clip":
                        moved[clip] = dst
                    elif kind == "proxy":
                        moved_proxy[clip] = dst
                except Exception as e:
                    dst, root = "", plan[src][1] if o["MoveFiles"] else ("Burn" if o["Burn"] else "Trash")
                    status = "error: %s" % e
                    if kind == "clip":
                        failed.append(os.path.basename(src))
                log_rows.setdefault(root, []).append([kind, clip, src, dst, status])
            if o["Burn"]:
                notes.append("burned %d clips (%s), deleted permanently" % (len(moved), human(freed)))
            else:
                where = "the Trash" if o["Trash"] else "the junkyard"
                notes.append("moved %d clips (%s) to %s" % (len(moved), human(freed), where))

        targets = [r for r in sel if r["path"] in moved or not r["exists"]] if o["files"] else list(sel)

        # 3. Relink
        if o["Relink"]:
            n, offline = 0, []
            for r in targets:
                if r["path"] in moved:
                    new_path = moved[r["path"]]
                    for mpi in r["mpis"]:
                        safe_call(mp, "RelinkClips", [mpi], os.path.dirname(new_path), default=False)
                        if clip_path(mpi) == new_path:          # check Resolve really points at the new file
                            n += 1
                        else:
                            offline.append(os.path.basename(r["path"]))
                        if r["path"] in moved_proxy:
                            safe_call(mpi, "LinkProxyMedia", moved_proxy[r["path"]])
            notes.append("relinked %d clips" % n)
            if offline:
                notes.append("⚠ couldn't relink %s (they'll show offline)" % ", ".join(offline))

        # 4. JUNK bin
        if o["ToBin"]:
            mpis = [m for r in targets for m in r["mpis"]]
            if mpis:
                safe_call(mp, "MoveClips", mpis, find_bin(mp, JUNK_BIN_NAME))
                notes.append("gathered in the %s bin" % JUNK_BIN_NAME)

        # 5. Remove from the Media Pool (never clips used elsewhere)
        if o["Remove"]:
            mpis = [m for r in targets if not r["used"] for m in r["mpis"]]
            removed = len(mpis) if (mpis and safe_call(mp, "DeleteClips", mpis, default=False)) else 0
            kept = len([r for r in targets if r["used"]])
            notes.append("removed %d from the Media Pool" % removed +
                         (" (kept %d used elsewhere)" % kept if kept else ""))

        # 6. Logs, restore point and ledger
        log_paths = []
        for root, rows in log_rows.items():
            special = root in ("Trash", "Burn")
            log_dir = os.path.join(APP_DIR, "%s_logs" % root.lower()) if special else root
            try:
                os.makedirs(log_dir, exist_ok=True)
                name = ("%s_%s.csv" % (root.lower(), datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S"))
                        if special else LOG_NAME)
                log_path = os.path.join(log_dir, name)
                with open(log_path, "w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["kind", "clip", "original_path", "moved_to", "status"])
                    w.writerows(rows)
                log_paths.append(log_path)
            except Exception as e:
                notes.append("couldn't write a log: %s" % e)
        if log_paths:
            action = "burn" if o["Burn"] else ("trash" if o["Trash"] else "yard")
            dest = {"burn": "Burned", "trash": "Trash"}.get(action, os.path.dirname(log_paths[0]))
            if action != "burn":            # burned files can't be restored, keep the old restore point
                self.settings["last_run"] = {"logs": log_paths, "project": project.GetName(),
                                             "when": now_stamp(), "dest": dest, "action": action}
                save_settings(self.settings)
            ledger_add({"when": now_stamp(), "project": project.GetName(), "action": action,
                        "clips": len(moved), "bytes": freed, "destination": dest})

        text = "Done: " + "; ".join(notes) + "."
        if protected:
            text += "\n⚠ Not burned (used in other timelines): " + ", ".join(protected)
        if failed:
            text += "\n⚠ Couldn't move: " + ", ".join(failed)
        return text

    # ------------------------------------------------------------------ restore

    def last_rows(self):
        last = self.settings.get("last_run")
        rows = []
        if last:
            for log_path in last.get("logs", []):
                try:
                    with open(log_path, newline="") as f:
                        rows += [r for r in csv.DictReader(f) if r.get("status") == "moved"]
                except Exception:
                    pass
        return last, rows

    def load_restore(self):
        tree = self.it["RestoreTree"]
        tree.Clear()
        last, rows = self.last_rows()
        self.it["RestoreStatus"].Text = ""
        if not last or not rows:
            self.it["RestoreInfo"].Text = "Nothing to restore. Your last run will show up here."
            self.it["RestoreRun"].Enabled = False
            self.it["Reveal"].Enabled = False
            return
        clips = len([r for r in rows if r["kind"] == "clip"])
        where = "the Trash" if last.get("action") == "trash" else last.get("dest", "")
        self.it["RestoreInfo"].Text = ("<b>Last run:</b> %s · project '%s' · %d clips moved to %s"
                                       % (last.get("when"), last.get("project"), clips, where))
        for r in rows:
            item = tree.NewItem()
            item.Text[0] = os.path.basename(r["original_path"])
            item.Text[1] = r["kind"]
            item.Text[2] = r["moved_to"] if os.path.exists(r["moved_to"]) else "missing (Trash emptied?)"
            tree.AddTopLevelItem(item)
        self.it["RestoreRun"].Enabled = True
        self.it["Reveal"].Enabled = last.get("action") != "trash"

    def on_reveal(self, ev):
        last = self.settings.get("last_run") or {}
        if last.get("dest") and os.path.isdir(last["dest"]):
            reveal(last["dest"])

    def on_restore(self, ev):
        last, rows = self.last_rows()
        if not rows:
            return
        if self.armed != "restore":
            self.armed = "restore"
            self.it["RestoreRun"].Text = "Confirm restore"
            self.it["RestoreStatus"].Text = "Put these files back where they came from?"
            return
        self.disarm()
        msg = self.restore(last, rows)
        self.load_restore()
        self.it["RestoreStatus"].Text = msg

    def restore(self, last, rows):
        project = self.project()
        mp = project.GetMediaPool()
        restored, skipped = {}, []
        freed_back = 0
        for r in rows:
            orig, now = r["original_path"], r["moved_to"]
            if not now or not os.path.exists(now) or os.path.exists(orig):
                skipped.append(os.path.basename(orig))
                continue
            try:
                os.makedirs(os.path.dirname(orig), exist_ok=True)
                freed_back += size_of(now)
                shutil.move(now, orig)
                restored.setdefault(r["clip"], {})[r["kind"]] = (orig, now)
            except Exception:
                skipped.append(os.path.basename(orig))

        pool = pool_by_path(mp)
        relinked, to_import = 0, []
        for clip, kinds in restored.items():
            if "clip" not in kinds:
                continue
            orig, now = kinds["clip"]
            mpis = pool.get(now) or pool.get(orig)
            if mpis:
                for mpi in mpis:
                    if safe_call(mp, "RelinkClips", [mpi], os.path.dirname(orig), default=False):
                        relinked += 1
                    if "proxy" in kinds:
                        safe_call(mpi, "LinkProxyMedia", kinds["proxy"][0])
            else:
                to_import.append(orig)

        if to_import:
            safe_call(mp, "SetCurrentFolder", find_bin(mp, RESTORE_BIN_NAME))
            imported = safe_call(mp, "ImportMedia", to_import, default=[]) or []
            for mpi in imported:
                p = clip_path(mpi)
                for clip, kinds in restored.items():
                    if "clip" in kinds and kinds["clip"][0] == p and "proxy" in kinds:
                        safe_call(mpi, "LinkProxyMedia", kinds["proxy"][0])

        for log_path in last.get("logs", []):
            try:
                os.rename(log_path, log_path.replace(".csv", "_RESTORED.csv"))
            except Exception:
                pass
        ledger_add({"when": now_stamp(), "project": last.get("project"), "action": "restore",
                    "clips": -len([c for c in restored.values() if "clip" in c]),
                    "bytes": -freed_back, "destination": ""})
        self.settings["last_run"] = None
        save_settings(self.settings)

        text = "Restored %d clips; relinked %d" % (len([c for c in restored.values() if "clip" in c]), relinked)
        if to_import:
            text += "; re-imported %d into the '%s' bin" % (len(to_import), RESTORE_BIN_NAME)
        text += "."
        if skipped:
            text += "\n⚠ Skipped: " + ", ".join(skipped)
        return text

    # ------------------------------------------------------------------ report

    def load_report(self):
        tree = self.it["ReportTree"]
        tree.Clear()
        per = {}
        total_bytes, total_runs = 0, 0
        for r in ledger_rows():
            try:
                b, c = int(r.get("bytes") or 0), int(r.get("clips") or 0)
            except ValueError:
                continue
            p = per.setdefault(r.get("project") or "?", {"runs": 0, "clips": 0, "bytes": 0, "last": ""})
            if r.get("action") != "restore":
                p["runs"] += 1
                total_runs += 1
            p["clips"] += c
            p["bytes"] += b
            p["last"] = max(p["last"], r.get("when") or "")
            total_bytes += b
        for name, p in sorted(per.items(), key=lambda kv: -kv[1]["bytes"]):
            item = tree.NewItem()
            item.Text[0] = name
            item.Text[1] = str(p["runs"])
            item.Text[2] = str(p["clips"])
            item.Text[3] = human(p["bytes"])
            item.Text[4] = p["last"]
            tree.AddTopLevelItem(item)
        if per:
            self.it["ReportTotal"].Text = ("<b>All time: %s freed</b> across %d run%s in %d project%s"
                                           % (human(total_bytes), total_runs, "" if total_runs == 1 else "s",
                                              len(per), "" if len(per) == 1 else "s"))
        else:
            self.it["ReportTotal"].Text = "No runs yet. Space you free will add up here."
        self.refresh_version_info()

    # ------------------------------------------------------------------ go

    # ------------------------------------------------------------------ updates

    def set_update_bar(self, text, show_buttons):
        self.it["UpdateMsg"].Text = text
        self.it["UpdateMsg"].Hidden = not text
        self.it["UpdateNotes"].Hidden = not show_buttons
        self.it["UpdateGo"].Hidden = not show_buttons

    def newer(self):
        info = self.settings.get("latest")
        if info and version_tuple(info.get("version")) > version_tuple(APP_VERSION):
            return info
        return None

    def refresh_version_info(self):
        path = installed_script()
        text = "You're on Junkyard %s." % APP_VERSION
        info = self.newer()
        if is_dev_install(path):
            text += " Developer install: updates are installed by hand."
        elif info:
            text += " Version %s is available." % info["version"]
        elif self.settings.get("last_check"):
            when = datetime.datetime.fromtimestamp(self.settings["last_check"]).strftime("%d %b %H:%M")
            text += " Last checked %s." % when
        self.it["VersionInfo"].Text = text
        self.it["AutoCheck"].Checked = bool(self.settings.get("auto_update", True))

    def on_autocheck(self, ev):
        self.settings["auto_update"] = bool(self.it["AutoCheck"].Checked)
        save_settings(self.settings)

    def check_updates(self, force=False):
        s = self.settings
        due = (datetime.datetime.now().timestamp() - (s.get("last_check") or 0)) > CHECK_EVERY_HOURS * 3600
        if force or (s.get("auto_update", True) and due):
            info = fetch_latest()
            if info:
                s["latest"] = info
                s["last_check"] = datetime.datetime.now().timestamp()
                save_settings(s)
            elif force:
                self.set_update_bar("Couldn't reach the update server. Check your internet connection.", False)
                self.refresh_version_info()
                return
        self.update_armed = False
        info = self.newer()
        if info and not is_dev_install(installed_script()):
            self.it["UpdateGo"].Text = "Update"
            self.set_update_bar("<b>Junkyard %s is available.</b> You're on %s." % (info["version"], APP_VERSION), True)
        elif force:
            self.set_update_bar("You're on the latest version (%s)." % APP_VERSION, False)
        else:
            self.set_update_bar("", False)
        self.refresh_version_info()

    def on_update(self, ev):
        info = self.newer()
        if not info:
            return
        path = installed_script()
        if not path:
            self.set_update_bar("Couldn't find Junkyard's file. Download the new version from "
                                "github.com/%s/junkyard instead." % GITHUB_USER, False)
            return
        if not getattr(self, "update_armed", False):
            self.update_armed = True
            self.it["UpdateGo"].Text = "Confirm update"
            self.set_update_bar("Install Junkyard %s? Your current version is backed up first."
                                % info["version"], True)
            return
        self.update_armed = False
        ok, msg = install_update(info, path)
        self.set_update_bar(("<b>%s</b>" % msg) if ok else msg, False)

    def show_notes(self, remote=False, everything=False, first_run=False):
        if remote and self.newer():
            info = self.newer()
            items = [(info["version"], info.get("notes") or ["No notes for this version."])]
            title = "Coming in Junkyard %s" % info["version"]
        else:
            items = RELEASE_NOTES if everything else notes_since(self.settings.get("seen_version"))
            title = ("Welcome to Junkyard %s" % APP_VERSION if first_run
                     else "What's new in Junkyard %s" % APP_VERSION)
        if not items:
            return
        html = ""
        for v, notes in items:
            html += "<h3>Junkyard %s</h3><ul>%s</ul>" % (v, "".join("<li>%s</li>" % n for n in notes))
        ui = self.ui
        if getattr(self, "notes_win", None) is None:
            self.notes_win = self.disp.AddWindow(
                {"ID": "NotesWin", "WindowTitle": title, "Geometry": [360, 220, 480, 400]},
                ui.VGroup({"Spacing": 10}, [
                    ui.TextEdit({"ID": "NotesText", "ReadOnly": True, "Weight": 1}),
                    ui.HGroup({"Weight": 0}, [
                        ui.HGap(0, 1),
                        ui.Button({"ID": "NotesOK", "Text": "Got it", "Weight": 0, "MinimumSize": [110, 30]}),
                    ]),
                ]))
            ni = self.notes_win.GetItems()
            self.notes_items = ni
            self.notes_win.On.NotesOK.Clicked = lambda ev: self.notes_win.Hide()
            self.notes_win.On.NotesWin.Close = lambda ev: self.notes_win.Hide()
        self.notes_win.WindowTitle = title
        self.notes_items["NotesText"].HTML = html
        self.notes_win.Show()

    def after_open(self):
        s = self.settings
        if s.get("seen_version") != APP_VERSION:
            self.show_notes(first_run=not s.get("seen_version"))
            s["seen_version"] = APP_VERSION
            save_settings(s)
        self.check_updates()

    # ------------------------------------------------------------------ go

    def show(self):
        self.win.Show()
        try:
            self.after_open()
        except Exception as e:
            print("Junkyard update check skipped: %s" % e)
        self.disp.RunLoop()
        self.win.Hide()
        if getattr(self, "notes_win", None) is not None:
            self.notes_win.Hide()


def main():
    resolve_app, bmd_mod = connect()
    if not resolve_app or not bmd_mod:
        print("%s: couldn't connect to DaVinci Resolve. Run it from Workspace > Scripts." % APP_TITLE)
        return
    Junkyard(resolve_app, bmd_mod).show()


if os.environ.get("JUNKYARD_TEST") != "1":
    main()
