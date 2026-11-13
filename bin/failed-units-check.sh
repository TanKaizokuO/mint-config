#!/usr/bin/env bash
# Login check (launched from sway autostart): notify if any system or user unit has failed.
sleep 20   # let login-time units settle first
f=$( { systemctl --failed --no-legend --plain; systemctl --user --failed --no-legend --plain; } | awk '{print $1}' | paste -sd' ')
[ -n "$f" ] && notify-send -u critical -a systemd "Failed services" "$f"
exit 0
