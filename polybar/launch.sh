#!/usr/bin/env bash

# Terminate already running bar instances
killall -q polybar

# Wait until the processes have been shut down (with timeout)
timeout=10
while pgrep -u "$UID" -x polybar >/dev/null && [[ $timeout -gt 0 ]]; do
  sleep 1
  ((timeout--))
done

# Launch Polybar on each connected monitor
if command -v xrandr &>/dev/null; then
  for m in $(xrandr --query | grep " connected" | cut -d" " -f1); do
    echo "---" | tee -a /tmp/polybar_$m.log
    MONITOR=$m polybar --reload bar 2>&1 | tee -a /tmp/polybar_$m.log & disown
  done
else
  polybar --reload bar & disown
fi

echo "Bars launched..."