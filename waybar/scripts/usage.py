#!/usr/bin/env python3
# Waybar custom module: percent of the 5h window used on the bar, 5h + 7d on hover.
# Claude Code: ~/.cache/usage/claude.json, written by ~/.claude/statusline-command.sh.
# Codex and agy: ~/.cache/usage/omp.json, refreshed by fetch_omp_usage.py (omp usage --json).
# Codex falls back to the newest ~/.codex/sessions rollout that carries rate_limits.
#
# Expired or unavailable usage displays as 00%; snapshots still expire normally.
# Exception: a live 7d window at 100% used shows 100% (critical) instead of the 5h value.
# Tooltips keep reset countdowns but omit snapshot-age annotations.
import glob
import json
import os
import sys
import time
from datetime import datetime

NOW = time.time()
HOME = os.path.expanduser("~")
WINDOW_MIN = {"five": 300, "seven": 10080}


def window_left(used, resets_at, minutes, snap):
    if used is None or resets_at is None:
        return None
    start = resets_at - minutes * 60
    if NOW >= resets_at or not (start <= snap < resets_at):
        return None
    return max(0.0, 100.0 - float(used))


def reset_in(ts):
    d = int(ts - NOW)
    if d <= 0:
        return ""
    if d >= 86400:
        return f"resets {d // 86400}d{(d % 86400) // 3600}h"
    if d >= 3600:
        return f"resets {d // 3600}h{(d % 3600) // 60}m"
    return f"resets {d // 60}m"


def parse_iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def claude():
    try:
        with open(f"{HOME}/.cache/usage/claude.json") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    snap = data.get("updated", NOW)
    out = {"snap": snap}
    for key, src in (("five", "five_hour"), ("seven", "seven_day")):
        w = data.get(src) or {}
        out[key] = (
            window_left(w.get("used_percentage"), w.get("resets_at"), WINDOW_MIN[key], snap),
            w.get("resets_at"),
        )
    return out


def omp(name):
    try:
        with open(f"{HOME}/.cache/usage/omp.json") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if name not in data:
        return None
    snap = data.get(f"{name}_at", data.get("updated", NOW))
    out = {"snap": snap}
    for key in ("five", "seven"):
        w = data[name].get(key) or {}
        resets = w.get("resets_at")
        # The provider reports remaining percent directly; a passed reset means stale.
        left = w.get("left") if resets and NOW < resets else None
        out[key] = (left, resets)
    return out


def codex():
    cached = omp("codex")
    if cached and NOW - cached["snap"] < 1800:
        return cached
    # Rollout names start with a timestamp, so reverse lexical order is newest first.
    paths = sorted(glob.glob(f"{HOME}/.codex/sessions/*/*/*/rollout-*.jsonl"), reverse=True)
    for path in paths[:60]:
        last = None
        try:
            with open(path) as f:
                for line in f:
                    if '"rate_limits"' not in line:
                        continue
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    rl = (ev.get("payload") or {}).get("rate_limits")
                    if rl:
                        last = (ev.get("timestamp"), rl)
        except OSError:
            continue
        if not last or not last[0]:
            continue
        snap = parse_iso(last[0])
        # Match windows by length, not by slot name: 300 min = 5h, 10080 min = 7d.
        rl = last[1]
        windows = {w.get("window_minutes"): w for w in (rl.get("primary"), rl.get("secondary")) if w}
        out = {"snap": snap}
        for key in ("five", "seven"):
            w = windows.get(WINDOW_MIN[key]) or {}
            out[key] = (
                window_left(w.get("used_percent"), w.get("resets_at"), WINDOW_MIN[key], snap),
                w.get("resets_at"),
            )
        return out
    return None


def cell(usage, key):
    left, reset = usage[key]
    if left is None:
        return "00%"
    return f"{round(100 - left)}% ({reset_in(reset).removeprefix('resets ') or 'resetting'})"


def line(label, usage):
    if usage is None:
        return f"{label:<12} no data"
    return f"{label:<12} 5h {cell(usage, 'five')}  |  7d {cell(usage, 'seven')}"


def label_color():
    # Charcoal for the Claude/Codex/Gemini labels; the percentage keeps the CSS status colour.
    # Follows the active theme: ~/.config/glass-themes/current -> light or dark.
    theme = os.path.realpath(os.path.expanduser("~/.config/glass-themes/current"))
    return "#9A9AA3" if theme.endswith("dark") else "#3A3A3F"


def main():
    c = claude()
    x = codex()
    a = omp("agy")

    def weekly_exhausted(u):
        # 7d window still live and fully used: it blocks the service regardless of the 5h window.
        return u is not None and u["seven"][0] is not None and round(100 - u["seven"][0]) >= 100

    def bar_pct(u):
        if weekly_exhausted(u):
            return "100%"
        if u is None or u["five"][0] is None:
            return "00%"
        return f"{round(100 - u['five'][0])}%"

    # One waybar module per tool: usage.py cc|cx|agy.
    which = sys.argv[1] if len(sys.argv) > 1 else "cc"
    label, own = {"cc": ("Claude", c), "cx": ("Codex", x), "agy": ("Gemini", a)}[which]
    # Pango markup (waybar custom modules leave escape=false): dim label, status-coloured %.
    text = f'<span foreground="{label_color()}">{label}</span> {bar_pct(own)}'

    # Color by 5h percent used: 0-50 green, 50-80 yellow, 80-100 red.
    left = own["five"][0] if own else None
    cls = []
    if weekly_exhausted(own):
        cls.append("critical")
    elif left is not None:
        used = 100 - left
        cls.append("ok" if used < 50 else "warning" if used < 80 else "critical")

    tooltip = "\n".join([
        line("Claude Code", c),
        line("Codex", x),
    ])

    print(json.dumps({"text": text, "tooltip": tooltip, "class": cls}))


if __name__ == "__main__":
    main()
