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

# ── Window Managers ──────────────────────────────────────
echo "[sway]"
link "$DOTFILES/sway/config"              "$HOME/.config/sway/config"
link "$DOTFILES/sway/scripts/screenshot.sh" "$HOME/.config/sway/scripts/screenshot.sh"

echo "[i3]"
link "$DOTFILES/i3/config"                "$HOME/.config/i3/config"

echo "[waybar]"
link "$DOTFILES/waybar/config.jsonc"      "$HOME/.config/waybar/config.jsonc"
link "$DOTFILES/waybar/style.css"         "$HOME/.config/waybar/style.css"

echo "[polybar]"
link "$DOTFILES/polybar/config.ini"       "$HOME/.config/polybar/config.ini"
link "$DOTFILES/polybar/launch.sh"        "$HOME/.config/polybar/launch.sh"
link "$DOTFILES/polybar/scripts/network-menu.sh" "$HOME/.config/polybar/scripts/network-menu.sh"

# ── Compositor / Notifications ───────────────────────────
echo "[picom]"
link "$DOTFILES/picom/picom.conf"         "$HOME/.config/picom/picom.conf"

echo "[mako]"
link "$DOTFILES/mako/config"              "$HOME/.config/mako/config"

echo "[dunst]"
link "$DOTFILES/dunst/dunstrc"            "$HOME/.config/dunst/dunstrc"

# ── Launcher ─────────────────────────────────────────────
echo "[rofi]"
link "$DOTFILES/rofi/config.rasi"         "$HOME/.config/rofi/config.rasi"

# ── Terminals ────────────────────────────────────────────
echo "[kitty]"
link "$DOTFILES/kitty/kitty.conf"         "$HOME/.config/kitty/kitty.conf"
link "$DOTFILES/kitty/current-theme.conf" "$HOME/.config/kitty/current-theme.conf"

echo "[alacritty]"
link "$DOTFILES/alacritty/alacritty.toml" "$HOME/.config/alacritty/alacritty.toml"

echo "[foot]"
link "$DOTFILES/foot/foot.ini"            "$HOME/.config/foot/foot.ini"

echo "[tmux]"
link "$DOTFILES/tmux/tmux.conf"           "$HOME/.config/tmux/tmux.conf"

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

# ── Hermes AI ────────────────────────────────────────────
echo "[hermes]"
link "$DOTFILES/hermes/config.yaml"       "$HOME/.hermes/config.yaml"

echo
echo "Done! Restart your shell or WM to pick up changes."
