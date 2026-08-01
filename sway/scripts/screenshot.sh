#!/usr/bin/env bash
# screenshot.sh [region|full]
# region -> select area | full -> whole output(s)
# Always: save to ~/Pictures/Screenshots + copy to clipboard + mako popup.
set -euo pipefail

mode="${1:-region}"
dir="$HOME/Pictures/Screenshots"
mkdir -p "$dir"
file="$dir/$(date +'%Y-%m-%d_%H-%M-%S').png"

case "$mode" in
    region)
        # slurp returns non-zero if the selection is cancelled -> abort quietly
        geom="$(slurp)" || exit 0
        grim -g "$geom" "$file"
        ;;
    full)
        grim "$file"
        ;;
    *)
        echo "usage: screenshot.sh [region|full]" >&2
        exit 1
        ;;
esac

# Copy to clipboard
wl-copy < "$file"

# Notify (thumbnail = the screenshot itself)
notify-send -i "$file" "Screenshot saved" "${file/#$HOME/~}"
