#!/bin/sh
# ~/.config/sway/scripts/autostart.sh
#
# Opens the daily apps on their workspaces at login. Started by `exec` (not
# exec_always) in the sway config, so `swaymsg reload` never relaunches them.
#
# Each heavy app starts as soon as the previous one's window appears, capped at
# WAIT_CAP seconds, instead of fixed sleeps. Sway pushes window events to us,
# so nothing polls.
#
# Kitty, Orca and ChatGPT are placed by `assign` rules in the sway config.
# Brave and VS Code are NOT assigned (so $mod+b / $mod+c open on the current
# workspace); this script moves only their first startup window instead.
#
# Log: $XDG_RUNTIME_DIR/sway-autostart.log (cleared each boot).

set -u

RUNDIR="${XDG_RUNTIME_DIR:-/tmp}"
LOG="$RUNDIR/sway-autostart.log"
PIDFILE="$RUNDIR/sway-autostart.pid"
WAIT_CAP=15
ORCA_BIN="$HOME/Applications/orca/orca-linux.AppImage"

log() { printf '%s %s\n' "$(date +%T)" "$*" >>"$LOG"; }

# Only one run at a time (guards against starting it by hand during a session).
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    exit 0
fi
echo "$$" >"$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT HUP INT TERM

# True if a window whose app_id (Wayland) or class (XWayland) matches the
# case-insensitive regex $1 is already open.
has_window() {
    swaymsg -t get_tree | jq -e --arg re "$1" '
        [.. | objects | select(.pid?)
            | (.app_id // .window_properties.class // "")
            | select(test($re; "i"))] | length > 0' >/dev/null 2>&1
}

# Start "$@" at lowered CPU priority and print the con_id of its first window
# matching regex $1, or nothing if none appears within WAIT_CAP seconds.
# The listener starts before the app so a fast window isn't missed. Events go
# through a FIFO so we can kill the listener the moment jq finds a match; a
# plain pipeline would hang until the next window event or the cap.
launch_and_wait() {
    re=$1; shift
    fifo="$RUNDIR/sway-autostart.$$.fifo"
    rm -f "$fifo"; mkfifo "$fifo"
    exec 3<>"$fifo" # read-write open never blocks
    swaymsg -t subscribe -m '["window"]' >&3 2>/dev/null &
    sub=$!
    sleep 0.2 # let the subscription connect before the app can map a window
    # nice 5 also lowers disk priority (best-effort I/O follows the nice level).
    nice -n 5 "$@" >/dev/null 2>&1 3>&- &
    timeout "$WAIT_CAP" jq -n -r --arg re "$re" '
        first(inputs
            | select(.change == "new")
            | select((.container.app_id // .container.window_properties.class // "") | test($re; "i"))
            | .container.id)' <&3 2>/dev/null
    kill "$sub" 2>/dev/null
    exec 3>&-
    rm -f "$fifo"
}

# place WORKSPACE REGEX COMMAND [ARGS...]
place() {
    ws=$1; re=$2; shift 2
    if has_window "$re"; then
        log "skip $1: window already open"
        return
    fi
    if ! command -v "$1" >/dev/null 2>&1; then
        log "skip $1: command not found"
        return
    fi
    id=$(launch_and_wait "$re" "$@")
    if [ -n "$id" ]; then
        # Focus stays where it is; only the new window moves.
        swaymsg "[con_id=$id] move container to workspace number $ws" >/dev/null 2>&1
        log "placed $1 on workspace $ws"
    else
        log "no window from $1 after ${WAIT_CAP}s; continuing"
    fi
}

log "autostart begin"
swaymsg workspace number 1 >/dev/null 2>&1

# Terminal: light, full priority, placed by its assign rule. Starts alongside Brave.
if ! has_window '^kitty$'; then
    kitty >/dev/null 2>&1 &
    log "started kitty"
fi

place 1 '^brave-browser$'                                 brave-browser
place 3 '^(com\.microsoft\.VSCode|code-url-handler|Code)$' code
place 4 '^orca$'                                          "$ORCA_BIN"
# Force native Wayland: under XWayland it is blurry on the 1.5x laptop screen.
# --ozone-platform-hint=auto is ignored by this app; these two flags work.
place 5 'chatgpt'                                         chatgpt --enable-features=UseOzonePlatform --ozone-platform=wayland

log "autostart done"
