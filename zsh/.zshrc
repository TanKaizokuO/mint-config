  

ZINIT_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}/zinit/zinit.git"


if [ ! -d $ZINIT_HOME ]; then
	mkdir -p "$(dirname $ZINIT_HOME)"
	git clone https://github.com/zdharma-continuum/zinit.git "$ZINIT_HOME"
fi


source "${ZINIT_HOME}/zinit.zsh"

zinit light zsh-users/zsh-syntax-highlighting
zinit light zsh-users/zsh-completions
zinit light zsh-users/zsh-autosuggestions
zinit light Aloxaf/fzf-tab



autoload -U compinit && compinit
zinit cdreplay -q

#bindings
zstyle ':completion:*' menu no
zstyle ':fzf-tab:complete:cd:*' fzf-preview 'ls --color $realpath'
zstyle ':fzf-tab:complete:__zoxide_z:*' fzf-preview 'ls --color $realpath'
bindkey -v

eval "$(fzf --zsh)"


HISTSIZE=10000
HISTFILE=~/.zsh_history
SAVEHIST=$HISTSIZE
HISTDUP=erase
setopt appendhistory
setopt sharehistory
setopt hist_ignore_space
setopt hist_ignore_all_dups
setopt hist_ignore_dups
setopt hist_save_no_dups
setopt hist_find_no_dups
command -v nala &>/dev/null && alias apt='nala'



#custom functions

tmux-select() {
    # Use fd if available (much faster), otherwise fall back to find with limits
    if command -v fd &> /dev/null; then
        selected_directory=$(fd -t d -d 4 . ~ 2>/dev/null | fzf)
    else
        # Limit search depth and suppress errors for faster performance
        selected_directory=$(find ~ -maxdepth 4 -type d 2>/dev/null | fzf)
    fi
    
    # Exit if no directory selected
    if [[ -z $selected_directory ]]; then
        echo "No directory selected. Exiting."
        return 1
    fi

    # Create session name from directory basename, replacing dots with underscores
    selected_name=$(basename "$selected_directory" | tr . _)
    
    # Check if we're inside a tmux session
    if [[ -z "$TMUX" ]]; then
        # Not in tmux - attach or create new session
        if tmux has-session -t="$selected_name" 2> /dev/null; then
            # Session exists, attach to it
            tmux attach -t "$selected_name"
        else
            # Create new session and attach
            tmux new-session -s "$selected_name" -c "$selected_directory"
        fi
    else
        # Inside tmux - switch or create session
        if tmux has-session -t="$selected_name" 2> /dev/null; then
            # Session exists, switch to it
            tmux switch-client -t "$selected_name"
        else
            # Create new detached session and switch to it
            tmux new-session -ds "$selected_name" -c "$selected_directory"
            tmux switch-client -t "$selected_name"
        fi
    fi
}

# Define the function in your .bashrc or .zshrc
tmux-select-session() {
    # Get the list of tmux sessions
    sessions=$(tmux list-sessions -F "#S" 2>/dev/null)

    if [[ -z "$sessions" ]]; then
        echo "No tmux sessions found."
        return 1
    fi

    # Use fzf to select a session
    selected_session=$(echo "$sessions" | fzf --height=10 --border --prompt="Select tmux session: ")

    if [[ -z "$selected_session" ]]; then
        echo "No session selected. Exiting."
        return 1
    fi

    # Attach to the selected session
    if [[ -z "$TMUX" ]]; then
        tmux attach-session -t "$selected_session"
    else
        tmux switch-client -t "$selected_session"
    fi
}

# Define the custom function
fzf_cd() {
    local dir
    dir=$(find . ~ -maxdepth 3 -type d 2>/dev/null | fzf) && cd "$dir"
}

bindkey -s '^N' 'fzf_cd :. ^M'
bindkey -s '^E' 'tmux-select :. ^M'
bindkey -s '^T' 'tmux-select-session :. ^M'
bindkey -s '^[[23\;2D' 'tmux detach'



#source /opt/ros/jazzy/setup.zsh
# Removed 2026-08-04: PATH entry for /home/ubuntu/.modular/bin — stale path from a
# previous Ubuntu install; that directory does not exist under this home.
# Add this to your ~/.bashrc or ~/.zshrc file
open_with_ranger() {
    selected_file=$(find ~ -maxdepth 4 -type f 2>/dev/null | fzf --preview 'cat {}')
    [ -n "$selected_file" ] && ranger --selectfile="$selected_file"
}

alias rzf='open_with_ranger'
# Disabled 2026-08-04: this called /home/ubuntu/githubrepos/backend/push.sh, a stale
# path from a previous Ubuntu install. push.sh no longer exists anywhere under this
# home, so the function always failed. To revive it, set PUSH_SCRIPT below to the
# script's real location and uncomment. (The repo-root walk is now git rev-parse,
# which also handles worktrees and submodules, where .git is a file rather than a dir.)
#
# PUSH_SCRIPT="$HOME/path/to/push.sh"
# push_code() {
#     local root
#     root=$(git rev-parse --show-toplevel 2>/dev/null) || {
#         echo "No git repository found in this directory or its parents."
#         return 1
#     }
#     (cd "$root" && "$PUSH_SCRIPT")
# }


bindkey -s '^F' 'open_with_ranger :. ^M'

alias nixins='nix-env -iA'

eval "$(starship init zsh)"
# --- ADD THIS CODE TO YOUR ~/.zshrc ---
export NVM_DIR="$HOME/.nvm"

# Lazy-load nvm
# This function will run the first time you use 'nvm', 'node', 'npm', etc.
load_nvm() {
  # Check if nvm is already loaded to avoid loading it multiple times
  # 'command -v nvm' will return the path if loaded, or just 'nvm' if it's a function
  if [ "$(command -v nvm)" = "nvm" ]; then
    # Source the nvm script to fully load it
    . "$NVM_DIR/nvm.sh"
    . "$NVM_DIR/bash_completion"
  fi
}

# Create aliases for all node-related commands to trigger the lazy loader
alias nvm='load_nvm; nvm'
alias node='load_nvm; node'
alias npm='load_nvm; npm'
alias npx='load_nvm; npx'
# Add any others you use, like yarn, pnpm, etc.
# alias yarn='load_nvm; yarn'

# zprof
export NEWT_COLORS='root=#cdd6f4,#1e1e2e;window=#cdd6f4,#1e1e2e;shadow=#181825,#181825;title=#cba6f7,#1e1e2e;button=#1e1e2e,#a6e3a1;actbutton=#cdd6f4,#89b4fa;checkbox=#a6e3a1,#1e1e2e;actcheckbox=#1e1e2e,#a6e3a1;entry=#1e1e2e,#cdd6f4;label=#cdd6f4,#1e1e2e;listbox=#cdd6f4,#1e1e2e;actlistbox=#1e1e2e,#cdd6f4;textbox=#cdd6f4,#1e1e2e;acttextbox=#cdd6f4,#1e1e2e;scroll=#1e1e2e,#cdd6f4'



#ascii art
# figlet "When do you think people die?... When they are forgotten!" | lolcat
alias night-mode-on='redshift -m randr -r -t 3500:3500 -l 19.07:72.87 &'
alias night-mode-off='pkill -f redshift'

# Clears the legacy /etc/apt/sources.list only when it is non-empty (real repos live in
# sources.list.d/), keeping a .bak and saying so, instead of truncating unconditionally.
clear_legacy_sources() {
    [ -s /etc/apt/sources.list ] || return 0
    sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak &&
    sudo truncate -s 0 /etc/apt/sources.list &&
    echo "cleared non-empty /etc/apt/sources.list (backup: /etc/apt/sources.list.bak)"
}

# Only a wrong sudo password aborts; after that every step runs even if an earlier one failed.
alias update-onegai='sudo -v && { clear_legacy_sources; sudo apt update; sudo apt upgrade -y; sudo apt autoremove -y; flatpak update -y; flatpak uninstall --unused -y; if [ -f /var/run/reboot-required ]; then echo "Reboot required"; fi; }'
# alias wifi-fix='sudo service network-manager restart'
alias oyasumi='shutdown now'
alias o='xdg-open'
alias hotspot-on='nmcli device wifi hotspot ifname wlp1s0f0 ssid "${HOTSPOT_SSID:-Haoshoku}" password "${HOTSPOT_PASS:?Set HOTSPOT_PASS}"'
alias hotspot-off='nmcli connection down Hotspot-1'
alias open-ports='sudo ss -tuln'
alias active-connections='nmcli connection show --active'



[[ -f "$HOME/.local/bin/env" ]] && . "$HOME/.local/bin/env"

export PATH="$HOME/.npm-global/bin:$PATH"


# Added by Antigravity CLI installer
export PATH="$HOME/.local/bin:$PATH"

# Composio CLI
export COMPOSIO_INSTALL_DIR="$HOME/.composio"
export PATH="$COMPOSIO_INSTALL_DIR:$PATH"


export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH


# Target kept out of the repo: export LAB_SSH_TARGET=user@host in ~/.secrets or env.
alias ssh_to_lab='ssh "${LAB_SSH_TARGET:?Set LAB_SSH_TARGET}"'

# Electron apps (VS Code) native Wayland instead of XWayland
export ELECTRON_OZONE_PLATFORM_HINT=auto

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"

export PATH=$HOME/development/flutter/bin:$PATH
# export AWS_PROFILE=...  # set in ~/.secrets or env

# atuin: searchable, deduplicated shell history on Ctrl+R (replaces fzf's Ctrl+R).
# Up-arrow stays the normal per-session history.
eval "$(atuin init zsh --disable-up-arrow)"

# zoxide must be initialized last so it wraps the final PATH/cd setup
eval "$(zoxide init --cmd cd zsh)"
