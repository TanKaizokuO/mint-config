#!/usr/bin/env bash
# Weekly user-level cleanup. Root-side cleanup is handled by unattended-upgrades + journald cap.
LOG=~/.local/state/maintenance/weekly.log
{
  echo "== $(date -Is)"
  before=$(df --output=avail -B1M / | tail -1)
  find ~/.cache/thumbnails -type f -atime +30 -delete 2>/dev/null
  find ~/.gradle/daemon -name '*.log' -mtime +14 -delete 2>/dev/null
  ~/.local/bin/uv cache prune >/dev/null 2>&1
  command -v docker >/dev/null && systemctl is-active -q docker && docker image prune -f >/dev/null 2>&1
  after=$(df --output=avail -B1M / | tail -1)
  echo "freed $((after-before)) MiB; / at $(df --output=pcent / | tail -1 | tr -d ' ')"
} >>"$LOG" 2>&1
tail -1 "$LOG" | xargs -I{} notify-send -a maintenance "Weekly cleanup" "{}" 2>/dev/null || true
