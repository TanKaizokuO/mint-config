#!/usr/bin/env bash
# Switch the liquid-glass desktop between dark and light.
# Usage: glass-theme.sh [dark|light|toggle]   (default: toggle)
# Every themed app reads its config through ~/.config/glass-themes/current,
# so switching = repoint that link, then tell each running app to reload.
set -u
dir="$HOME/.config/glass-themes"
cur="$(basename "$(readlink "$dir/current")")"
want="${1:-toggle}"
[ "$want" = toggle ] && { [ "$cur" = dark ] && want=light || want=dark; }
case "$want" in dark|light) ;; *) echo "usage: $0 [dark|light|toggle]" >&2; exit 2;; esac

ln -sfn "$want" "$dir/current"

# Apps that follow the current symlink with no reload from this script:
# yazi and btop (restart open instances), Antigravity (follows gsettings
# color-scheme via the portal). swaylock and VS Code stay fixed by choice.

# Starship: switch the palette name in starship.toml. Starship re-reads the
# file on every prompt, so no reload is needed.
case "$want" in light) PAL=glass_smoke ;; *) PAL=red_mountain ;; esac
# --follow-symlinks keeps an install.sh symlink intact instead of replacing it.
sed -i --follow-symlinks "s/^palette = .*/palette = '$PAL'/" "$HOME/.config/starship.toml"

# tmux.conf sources current/tmux.conf; re-source it in a running server
# (harmless when no server is running).
tmux source-file "$HOME/.tmux.conf" 2>/dev/null || true

# Sway borders (+ SwayFX blur/shadow tint)
swaymsg reload >/dev/null

# Waybar: a full restart is the reliable way to pick up new CSS. Wait (max ~2s)
# for the old process to exit first, so the new one doesn't start alongside it.
pkill -x waybar || true
for _ in $(seq 20); do pgrep -x waybar >/dev/null || break; sleep 0.1; done
swaymsg exec waybar >/dev/null

# Notifications
makoctl reload 2>/dev/null

# Kitty: SIGUSR1 = reload config in every open window
pkill -USR1 -x kitty 2>/dev/null

# GTK apps. libadwaita (GTK4) reads ~/.config/gtk-4.0/gtk.css, which WhiteSur's
# installer made a symlink to its Dark or Light stylesheet.
if [ "$want" = light ]; then
  gtk=WhiteSur-Light-grey; scheme=prefer-light; icons=Papirus; dark=0; css=gtk-Light.css
else
  gtk=WhiteSur-Dark-grey;  scheme=prefer-dark;  icons=Papirus-Dark; dark=1; css=gtk-Dark.css
fi
gsettings set org.gnome.desktop.interface gtk-theme "$gtk"
gsettings set org.gnome.desktop.interface color-scheme "$scheme"
gsettings set org.gnome.desktop.interface icon-theme "$icons"
for f in "$HOME/.config/gtk-3.0/settings.ini" "$HOME/.config/gtk-4.0/settings.ini"; do
  sed -i -e "s/^gtk-theme-name=.*/gtk-theme-name=$gtk/" \
         -e "s/^gtk-icon-theme-name=.*/gtk-icon-theme-name=$icons/" \
         -e "s/^gtk-application-prefer-dark-theme=.*/gtk-application-prefer-dark-theme=$dark/" "$f"
done
ln -sfn "$HOME/.config/gtk-4.0/$css" "$HOME/.config/gtk-4.0/gtk.css"
ln -sfn "$HOME/.config/gtk-4.0/$css" "$HOME/.config/gtk-4.0/gtk-dark.css"

notify-send "Glass theme" "Switched to $want"
