#!/usr/bin/env bash
# install.sh — Symlink dotfiles to their expected locations.
# Usage: ./install.sh          (interactive — asks before overwriting)
#        ./install.sh --force  (overwrites without asking)
set -euo pipefail

DOTFILES="$(cd "$(dirname "$0")" && pwd)"
FORCE=false
[[ "${1:-}" == "--force" ]] && FORCE=true

link() {
    local src="$1" dst="$2"
    if [[ -e "$dst" || -L "$dst" ]]; then
        if $FORCE; then
            rm -rf "$dst"
        else
            echo "  EXISTS: $dst (skipping; use --force to overwrite)"
            return
        fi
    fi
    mkdir -p "$(dirname "$dst")"
    ln -sf "$src" "$dst"
    echo "  LINKED: $dst -> $src"
}

echo "=== Dotfiles Installer ==="
echo "Source: $DOTFILES"
echo

# Files that follow the active glass theme link into ~/.config/glass-themes/current,
# which glass-theme.sh repoints between dark and light.
THEME="$HOME/.config/glass-themes/current"

# ── Theme ────────────────────────────────────────────────
echo "[glass-themes]"
link "$DOTFILES/glass-themes/dark"        "$HOME/.config/glass-themes/dark"
link "$DOTFILES/glass-themes/light"       "$HOME/.config/glass-themes/light"
if [[ ! -e "$THEME" ]]; then
    ln -sfn dark "$THEME"
    echo "  LINKED: $THEME -> dark"
fi

# ── Window Managers ──────────────────────────────────────
echo "[sway]"
link "$DOTFILES/sway/config"              "$HOME/.config/sway/config"
link "$DOTFILES/sway/config-swayfx"       "$HOME/.config/sway/config-swayfx"
for f in screenshot.sh autostart.sh glass-theme.sh keys.sh keys.py lock.sh; do
    link "$DOTFILES/sway/scripts/$f"      "$HOME/.config/sway/scripts/$f"
done
for f in "$DOTFILES"/sway/themes/*.conf; do
    link "$f"                             "$HOME/.config/sway/themes/$(basename "$f")"
done

echo "[i3]"
link "$DOTFILES/i3/config"                "$HOME/.config/i3/config"

echo "[waybar]"
link "$DOTFILES/waybar/config.jsonc"      "$HOME/.config/waybar/config.jsonc"
link "$THEME/waybar.css"                  "$HOME/.config/waybar/style.css"
for f in wifi_backend.py wifi_popover.py wifi_popover.css usage.py fetch_omp_usage.py fetch_claude_usage.py; do
    link "$DOTFILES/waybar/scripts/$f"    "$HOME/.config/waybar/scripts/$f"
done
link "$DOTFILES/waybar/vendor/gtklayershell" "$HOME/.config/waybar/vendor/gtklayershell"

echo "[polybar]"
link "$DOTFILES/polybar/config.ini"       "$HOME/.config/polybar/config.ini"
link "$DOTFILES/polybar/launch.sh"        "$HOME/.config/polybar/launch.sh"
link "$DOTFILES/polybar/scripts/network-menu.sh" "$HOME/.config/polybar/scripts/network-menu.sh"

# ── Compositor / Notifications ───────────────────────────
echo "[picom]"
link "$DOTFILES/picom/picom.conf"         "$HOME/.config/picom/picom.conf"

echo "[mako]"
link "$THEME/mako.conf"                   "$HOME/.config/mako/config"

echo "[dunst]"
link "$DOTFILES/dunst/dunstrc"            "$HOME/.config/dunst/dunstrc"

# ── Launcher ─────────────────────────────────────────────
echo "[rofi]"
link "$THEME/rofi.rasi"                   "$HOME/.config/rofi/config.rasi"

echo "[fuzzel]"
link "$THEME/fuzzel.ini"                  "$HOME/.config/fuzzel/fuzzel.ini"

# ── Terminals ────────────────────────────────────────────
echo "[kitty]"
link "$DOTFILES/kitty/kitty.conf"         "$HOME/.config/kitty/kitty.conf"
link "$THEME/kitty.conf"                  "$HOME/.config/kitty/current-theme.conf"

echo "[alacritty]"
link "$DOTFILES/alacritty/alacritty.toml" "$HOME/.config/alacritty/alacritty.toml"

echo "[foot]"
link "$DOTFILES/foot/foot.ini"            "$HOME/.config/foot/foot.ini"

echo "[tmux]"
link "$DOTFILES/tmux/tmux.conf"           "$HOME/.tmux.conf"

# ── TUI apps ─────────────────────────────────────────────
echo "[btop]"
link "$DOTFILES/btop/btop.conf"           "$HOME/.config/btop/btop.conf"
link "$THEME/btop.theme"                  "$HOME/.config/btop/themes/glass.theme"

echo "[yazi]"
link "$DOTFILES/yazi/yazi.toml"           "$HOME/.config/yazi/yazi.toml"
link "$DOTFILES/yazi/keymap.toml"         "$HOME/.config/yazi/keymap.toml"
link "$THEME/yazi-theme.toml"             "$HOME/.config/yazi/theme.toml"

# ── Prompt ───────────────────────────────────────────────
echo "[starship]"
link "$DOTFILES/starship/starship.toml"   "$HOME/.config/starship.toml"

# ── Shell ────────────────────────────────────────────────
echo "[zsh]"
link "$DOTFILES/zsh/.zshrc"               "$HOME/.zshrc"
[[ -f "$DOTFILES/zsh/.zshenv" ]] && link "$DOTFILES/zsh/.zshenv" "$HOME/.zshenv"

echo "[bash]"
link "$DOTFILES/bash/.bashrc"             "$HOME/.bashrc"
link "$DOTFILES/bash/aliases.bash"        "$HOME/.config/bash/aliases.bash"
link "$DOTFILES/bash/keybinds.bash"       "$HOME/.config/bash/keybinds.bash"
link "$DOTFILES/bash/prompt.bash"         "$HOME/.config/bash/prompt.bash"
link "$DOTFILES/bash/functions/system.bash" "$HOME/.config/bash/functions/system.bash"
link "$DOTFILES/bash/functions/utils.bash"  "$HOME/.config/bash/functions/utils.bash"

# ── Fastfetch ────────────────────────────────────────────
echo "[fastfetch]"
link "$DOTFILES/fastfetch/config.jsonc"   "$HOME/.config/fastfetch/config.jsonc"
link "$DOTFILES/fastfetch/assets/jedi.png" "$HOME/.config/fastfetch/assets/jedi.png"

# ── Desktop environment ──────────────────────────────────
echo "[fontconfig]"
link "$DOTFILES/fontconfig/fonts.conf"    "$HOME/.config/fontconfig/fonts.conf"

echo "[environment.d]"
link "$DOTFILES/environment.d/50-electron-wayland.conf" "$HOME/.config/environment.d/50-electron-wayland.conf"

echo "[git]"
link "$DOTFILES/git/ignore"               "$HOME/.config/git/ignore"

# ── User scripts and services ────────────────────────────
echo "[bin]"
for f in "$DOTFILES"/bin/*; do
    link "$f"                             "$HOME/.local/bin/$(basename "$f")"
done

echo "[systemd]"
for f in "$DOTFILES"/systemd/user/*; do
    link "$f"                             "$HOME/.config/systemd/user/$(basename "$f")"
done

# ── Hermes AI ────────────────────────────────────────────
echo "[hermes]"
link "$DOTFILES/hermes/config.yaml"       "$HOME/.hermes/config.yaml"

echo
echo "Done! Restart your shell or WM to pick up changes."
echo "Enable services with: systemctl --user daemon-reload && systemctl --user enable --now usage-fetch.timer claude-usage-fetch.timer weekly-maintenance.timer brave-volume-guard.service"
