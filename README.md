# dotfiles

Personal configuration files for my Linux workstation (IdeaPad Pro 5, Arrow Lake).

**Theme:** "liquid glass", dark and light variants (`glass-themes/`), toggled with `Super+Shift+T`. Sway, Waybar, Mako, Rofi, Fuzzel, Kitty, tmux, btop, yazi and Starship all follow it.

## What's Included

### Core
| Config | Path | Description |
|--------|------|-------------|
| **Sway** | `sway/` | Wayland compositor: dual-monitor, HiDPI, app autostart, cliphist, drop-down terminal, lid switch |
| **SwayFX** | `sway/config-swayfx` | Blur, rounded corners and shadows on top of the Sway config (`sway -c ~/.config/sway/config-swayfx`) |
| **Glass themes** | `glass-themes/` | Dark/light palettes per app; `~/.config/glass-themes/current` points at the active one |
| **i3** | `i3/` | X11 tiling WM: same keybinds, Polybar + Picom |
| **Hermes** | `hermes/` | AI agent config: providers, toolsets, personalities |
| **Starship** | `starship/` | Cross-shell prompt; palette switched by `glass-theme.sh` |

### Bars & Notifications
| Config | Used with |
|--------|-----------|
| **Waybar** | Sway (Wayland): grouped pills, Wi-Fi popup, Claude/Codex usage meters |
| **Polybar** | i3 (X11) |
| **Mako** | Sway notifications |
| **Dunst** | i3 notifications |

### Terminals
| Config | Notes |
|--------|-------|
| **Kitty** | Primary: glass theme, JetBrainsMono NFM |
| **Alacritty** | Secondary: wallpaper palette, JetBrainsMono NFM |
| **Foot** | Lightweight Wayland fallback, same palette |

### Shell & Tools
| Config | Notes |
|--------|-------|
| **Zsh** | Zinit + fzf-tab + zoxide + atuin + vi-mode + tmux helpers |
| **Bash** | Modular: aliases, keybinds, prompt, functions |
| **Tmux** | `~/.tmux.conf`: C-b prefix, top status bar, TPM (resurrect, continuum, sessionx, vim-tmux-navigator) |
| **Rofi** | App launcher (XWayland, so no SwayFX blur) |
| **Fuzzel** | Wayland launcher and cliphist picker (`Ctrl+Alt+V`) |
| **Yazi** | TUI file manager (`Super+X`); `Ctrl+O` opens the folder in VS Code |
| **btop** | Resource monitor with the glass theme |
| **Picom** | X11 compositor: shadows, rounded corners, transparency |
| **Fastfetch** | System info: custom Jedi logo, boxed layout |
| **fontconfig / environment.d / git** | Font hinting, native-Wayland Electron, global gitignore |

### Scripts & services
| File | Purpose |
|------|---------|
| `sway/scripts/autostart.sh` | Opens daily apps on their workspaces at login, each waiting for the previous window |
| `sway/scripts/glass-theme.sh` | Switches dark/light and reloads every themed app |
| `sway/scripts/lock.sh` | swaylock over a cached, blurred copy of the wallpaper |
| `sway/scripts/keys.sh` | `Super+/` searchable keybinding cheatsheet |
| `waybar/scripts/usage.py` | Usage pills; reads caches filled by `fetch_omp_usage.py` / `fetch_claude_usage.py` |
| `systemd/user/*usage-fetch.*` | 30-second timers refreshing those caches |
| `bin/failed-units-check.sh` | Login notification if any systemd unit failed |
| `bin/brave-volume-guard` + service | Logs and resets Brave's hidden stream-volume drops |
| `bin/weekly-maintenance.sh` + timer | Weekly cache cleanup |
| `systemd/user/daypane.service` + `glass-themes/*/daypane.css` | daypane calendar/tasks daemon; popup on `Super+Shift+D` or clicking the Waybar clock. Its `config.toml` (calendar credentials) is not tracked |

### Local-only values
Secrets and machine-specific targets are read from the environment (e.g. `~/.secrets`), never committed:
`HOTSPOT_PASS` (optional `HOTSPOT_SSID`) for `hotspot-on`, `LAB_SSH_TARGET` for `ssh_to_lab`, and `AWS_PROFILE`.
Wallpapers are not tracked; edit the `output * bg` line in `sway/config`.

## Install

```bash
git clone https://github.com/TanKaizokuO/mint-config.git ~/dotfiles
cd ~/dotfiles
chmod +x install.sh
./install.sh          # interactive: skips existing files
./install.sh --force  # overwrites everything (deletes existing targets, including directories)
```

### Waybar Wi-Fi popup

The network pill opens a GTK3 popup; Escape, an outside click, or a second pill click closes it.
Opening uses cached NetworkManager state; Refresh explicitly requests a scan.
Requires Python 3 with PyGObject, GTK3, libnm, and gtk-layer-shell on a layer-shell compositor.
On Ubuntu/Mint: `sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-nm-1.0 libgtk-layer-shell0 gir1.2-gtklayershell-0.1`.
The bundled Ubuntu noble 0.8.2-1build2 x86-64 GtkLayerShell typelib is a fallback when the system typelib is absent; its copyright notice is included.
Offline backend regressions: `/usr/bin/python3 -m unittest discover -s waybar/tests -v`.

## Structure

```
dotfiles/
├── install.sh
├── glass-themes/{dark,light}/   # waybar.css, mako.conf, rofi.rasi, fuzzel.ini, kitty.conf,
│                                # sway-colors.conf, swayfx.conf, tmux.conf, btop.theme, yazi-theme.toml
├── sway/
│   ├── config
│   ├── config-swayfx
│   ├── themes/*.conf
│   └── scripts/{autostart,glass-theme,keys,lock,screenshot}.sh, keys.py
├── i3/config
├── hermes/config.yaml
├── waybar/
│   ├── config.jsonc
│   ├── scripts/{usage,fetch_omp_usage,fetch_claude_usage,wifi_backend,wifi_popover}.py
│   ├── tests/
│   └── vendor/gtklayershell/
├── polybar/{config.ini,launch.sh,scripts/network-menu.sh}
├── kitty/kitty.conf
├── alacritty/alacritty.toml
├── foot/foot.ini
├── tmux/tmux.conf
├── dunst/dunstrc
├── picom/picom.conf
├── btop/btop.conf
├── yazi/{yazi.toml,keymap.toml}
├── starship/starship.toml
├── fastfetch/{config.jsonc,assets/jedi.png}
├── fontconfig/fonts.conf
├── environment.d/50-electron-wayland.conf
├── git/ignore
├── bin/{failed-units-check.sh,brave-volume-guard,weekly-maintenance.sh}
├── systemd/user/*.service, *.timer
├── bash/{.bashrc,aliases.bash,keybinds.bash,prompt.bash,functions/}
└── zsh/{.zshrc,.zshenv}
```
