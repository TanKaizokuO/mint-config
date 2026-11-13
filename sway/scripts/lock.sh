#!/bin/sh
# Lock the screen with a blurred copy of the current wallpaper.
#
# The wallpaper is whatever variety last set (it records the path in
# ~/.config/variety/wallpaper/wallpaper.jpg.txt); if variety isn't running we
# fall back to the "output * bg" line in the sway config. The blurred copy is
# cached per source image + mtime, so only the first lock after a wallpaper
# change pays for the convert; every later lock (including before-sleep) is
# instant.

set -eu

# Never stack a second lock on top of a live one: two swaylock instances both
# grab the keyboard, the typed password gets split between them, and neither
# accepts it — the screen sits on the red "wrong" indicator with no way back in.
if pgrep -x swaylock >/dev/null 2>&1; then
    exit 0
fi

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/swaylock"
FALLBACK_COLOR=13160F

wallpaper=""
variety_state="$HOME/.config/variety/wallpaper/wallpaper.jpg.txt"
if [ -r "$variety_state" ]; then
    wallpaper=$(head -n1 "$variety_state")
fi
if [ ! -r "$wallpaper" ]; then
    wallpaper=$(awk '/^output \* bg /{ $1=""; $2=""; $3=""; sub(/ fill$| fit$| stretch$| center$| tile$/,""); sub(/^ +/,""); print; exit }' "$HOME/.config/sway/config")
    # The sway config may spell the path with ~; sway expands it, test(1) does not.
    case "$wallpaper" in "~/"*) wallpaper="$HOME/${wallpaper#\~/}" ;; esac
fi
[ -r "$wallpaper" ] || exec swaylock -f -c "$FALLBACK_COLOR"

mkdir -p "$CACHE_DIR"
key=$(printf '%s %s' "$wallpaper" "$(stat -c %Y "$wallpaper")" | md5sum | cut -d' ' -f1)
blurred="$CACHE_DIR/$key.png"

if [ ! -s "$blurred" ]; then
    # Downscale, blur, scale back up: far cheaper than blurring at full size,
    # and the result is indistinguishable. -fill black -colorize dims it so the
    # password indicator stays readable over bright wallpapers.
    convert "$wallpaper" \
        -resize 1920x1080^ -gravity center -extent 1920x1080 \
        -resize 20% -blur 0x6 -resize 500% \
        -fill black -colorize 25% \
        "$blurred.tmp.png" && mv "$blurred.tmp.png" "$blurred"
    # Drop stale blurs from older wallpapers.
    find "$CACHE_DIR" -maxdepth 1 -name '*.png' ! -name "$key.png" -delete
fi

exec swaylock -f -i "$blurred" -s fill \
    --indicator-radius 90 --indicator-thickness 8 \
    --ring-color 2B332E --key-hl-color D5A06A --bs-hl-color 858F91 \
    --inside-color 13160Fcc --text-color D5D8D4 \
    --line-color 00000000 --separator-color 00000000 \
    --inside-ver-color 13160Fcc --ring-ver-color 1F7290 --text-ver-color D5D8D4 \
    --inside-wrong-color 13160Fcc --ring-wrong-color C47A35 --text-wrong-color D5D8D4 \
    --inside-clear-color 13160Fcc --ring-clear-color 858F91 --text-clear-color D5D8D4
