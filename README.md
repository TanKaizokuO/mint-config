# dotfiles

Personal configuration files for my Linux workstation (IdeaPad Pro 5, Arrow Lake).

**Theme:** Catppuccin Mocha across the entire stack.

## What's Included

### Core
| Config | Path | Description |
|--------|------|-------------|
| **Sway** | `sway/` | Wayland compositor — dual-monitor, HiDPI, Catppuccin colors |
| **i3** | `i3/` | X11 tiling WM — same keybinds, Polybar + Picom |
| **Hermes** | `hermes/` | AI agent config — providers, toolsets, personalities |
| **Starship** | `starship/` | Cross-shell prompt (OMP alternative) — Catppuccin rainbow segments |

### Bars & Notifications
| Config | Used with |
|--------|-----------|
| **Waybar** | Sway (Wayland) |
| **Polybar** | i3 (X11) |
| **Mako** | Sway notifications |
| **Dunst** | i3 notifications |

### Terminals
| Config | Notes |
|--------|-------|
| **Kitty** | Primary — Catppuccin Mocha, HurmitNF, 80% opacity |
| **Alacritty** | Secondary — dark theme, JetBrainsMono NF |
| **Foot** | Lightweight Wayland fallback |

### Shell & Tools
| Config | Notes |
|--------|-------|
| **Zsh** | Zinit + fzf-tab + zoxide + vi-mode + tmux helpers |
| **Bash** | Modular: aliases, keybinds, prompt, functions |
| **Tmux** | C-a prefix, vi-copy, vim pane switching |
| **Rofi** | App launcher — Catppuccin glass |
| **Picom** | X11 compositor — shadows, rounded corners, transparency |
| **Fastfetch** | System info — custom Jedi logo, boxed layout |

## Install

```bash
git clone https://github.com/TanKaizokuO/mint-config.git ~/dotfiles
cd ~/dotfiles
chmod +x install.sh
./install.sh          # interactive — skips existing files
./install.sh --force  # overwrites everything
```

## Structure

```
dotfiles/
├── install.sh
├── sway/
│   ├── config
│   └── scripts/screenshot.sh
├── i3/
│   └── config
├── hermes/
│   └── config.yaml
├── waybar/
│   ├── config.jsonc
│   └── style.css
├── polybar/
│   ├── config.ini
│   ├── launch.sh
│   └── scripts/network-menu.sh
├── kitty/
│   ├── kitty.conf
│   └── current-theme.conf
├── alacritty/
│   └── alacritty.toml
├── foot/
│   └── foot.ini
├── tmux/
│   └── tmux.conf
├── mako/
│   └── config
├── dunst/
│   └── dunstrc
├── rofi/
│   └── config.rasi
├── picom/
│   └── picom.conf
├── starship/
│   └── starship.toml
├── fastfetch/
│   ├── config.jsonc
│   └── assets/jedi.png
├── bash/
│   ├── .bashrc
│   ├── aliases.bash
│   ├── keybinds.bash
│   ├── prompt.bash
│   └── functions/
│       ├── system.bash
│       └── utils.bash
└── zsh/
    ├── .zshrc
    └── .zshenv
```
