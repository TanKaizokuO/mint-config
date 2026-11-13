#!/usr/bin/env python3
"""Keybinding cheatsheet: every bindsym in the live sway config, described in
plain English, searchable in fuzzel (Super+/). Read-only — picking a line just
closes the menu.

New bindings show up automatically. If one isn't in DESCRIBE below, it falls
back to "Run <program>"; add a pattern here to give it a proper description.
"""
import os
import re
import subprocess

CONFIG = os.path.expanduser("~/.config/sway/config")

# (regex on the command, description). First match wins; \1 etc. allowed.
DESCRIBE = [
    # apps
    (r"exec kitty --class yazi", "Open yazi file manager (terminal)"),
    (r"exec kitty$", "Open terminal (Kitty)"),
    (r"exec code$", "Open VS Code"),
    (r"exec antigravity$", "Open Antigravity"),
    (r"exec android-studio$", "Open Android Studio"),
    (r"exec brave-browser", "Open Brave browser"),
    (r"exec nautilus", "Open Files (Nautilus)"),
    (r"exec chatgpt", "Open ChatGPT"),
    (r"exec nm-connection-editor", "Wi-Fi / network settings"),
    (r"exec rofi -show drun", "App launcher"),
    # system
    (r"lock\.sh", "Lock screen"),
    (r"glass-theme\.sh toggle", "Switch dark / light theme"),
    (r"keys\.(sh|py)", "Show this shortcut list"),
    (r"swaynag .*", "Log out of Sway (asks first)"),
    (r"^reload$", "Reload Sway config"),
    # screenshots
    (r"screenshot\.sh region", "Screenshot a selected area"),
    (r"screenshot\.sh full", "Screenshot the whole screen"),
    # clipboard
    (r"cliphist decode", "Clipboard history: copy an old item"),
    (r"cliphist delete", "Clipboard history: delete an item"),
    (r"cliphist wipe", "Clipboard history: clear everything"),
    # media / hardware
    (r"brightnessctl set \S+\+", "Brightness up"),
    (r"brightnessctl set \S+-", "Brightness down"),
    (r"wpctl set-volume .*\+$", "Volume up"),
    (r"wpctl set-volume .*-$", "Volume down"),
    (r"wpctl set-mute", "Mute / unmute"),
    (r"playerctl play-pause", "Play / pause media"),
    (r"playerctl next", "Next track"),
    (r"playerctl previous", "Previous track"),
    # windows
    (r"^focus (\w+)$", r"Focus the window \1"),
    (r"^move (left|right|up|down)$", r"Move window \1"),
    (r"^kill$", "Close window"),
    (r"^fullscreen toggle$", "Fullscreen on / off"),
    (r"^floating toggle$", "Float / tile window"),
    (r"^split h$", "Next window opens to the right"),
    (r"^split v$", "Next window opens below"),
    (r"^layout stacking$", "Stacked layout (titles on top of each other)"),
    (r"^layout tabbed$", "Tabbed layout"),
    (r"^layout toggle split$", "Side-by-side layout (toggle direction)"),
    # scratchpad
    (r'dropterm.*scratchpad show', "Drop-down terminal (show / hide)"),
    (r"^move scratchpad$", "Hide window (send to scratchpad)"),
    (r"^scratchpad show$", "Bring back hidden windows (cycle)"),
]

KEYNAMES = {
    "$mod": "Super", "Mod4": "Super", "Mod1": "Alt", "Control": "Ctrl",
    "Return": "Enter", "grave": "`", "minus": "-", "slash": "/",
    "space": "Space", "Print": "PrtSc", "Delete": "Del",
    "XF86MonBrightnessUp": "Brightness↑", "XF86MonBrightnessDown": "Brightness↓",
    "XF86AudioRaiseVolume": "Volume↑", "XF86AudioLowerVolume": "Volume↓",
    "XF86AudioMute": "Mute", "XF86AudioPlay": "Play", "XF86AudioNext": "Next",
    "XF86AudioPrev": "Prev", "XF86SelectiveScreenshot": "Screenshot key",
    "Left": "←", "Right": "→", "Up": "↑", "Down": "↓",
}


def pretty_key(combo):
    parts = [KEYNAMES.get(p, p.upper() if len(p) == 1 else p) for p in combo.split("+")]
    return " + ".join(parts)


def describe(cmd):
    for pat, text in DESCRIBE:
        m = re.search(pat, cmd)
        if m:
            return m.expand(text)
    if cmd.startswith("exec "):
        prog = os.path.basename(cmd.split()[1])
        return f"Run {prog}"
    return cmd


def bindings():
    out, ws_go, ws_move = [], [], []
    with open(CONFIG) as f:
        lines = f.read().replace("\\\n", " ").splitlines()  # join continued lines
    for line in lines:
        m = re.match(r"\s*bindsym\s+((?:--\S+\s+)*)(\S+)\s+(.*)", line)
        if not m:
            continue
        key, cmd = m.group(2), m.group(3).strip()
        # Collapse the 20 workspace lines into two.
        if re.match(r"workspace number", cmd):
            ws_go.append(key); continue
        if re.match(r"move container to workspace number", cmd):
            ws_move.append(key); continue
        out.append((pretty_key(key), describe(cmd)))
    if ws_go:
        out.append(("Super + 1 … 0", "Go to workspace 1–10"))
    if ws_move:
        out.append(("Super + Shift + 1 … 0", "Move window to workspace 1–10"))
    return out


def main():
    rows = bindings()
    # Two keys with the same action (e.g. Super+T and Super+Enter) share one line.
    merged = {}
    for key, desc in rows:
        merged.setdefault(desc, []).append(key)
    width = max(len(" / ".join(k)) for k in merged.values()) + 3
    text = "\n".join(f"{' / '.join(keys):<{width}}{desc}" for desc, keys in merged.items())
    subprocess.run(
        ["fuzzel", "--dmenu", "--prompt=keys> ", "--width=90", "--lines=18"],
        input=text, text=True, stdout=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    if os.environ.get("KEYS_PRINT"):
        rows = bindings()
        for k, d in rows:
            print(f"{k:<28}{d}")
    else:
        main()
