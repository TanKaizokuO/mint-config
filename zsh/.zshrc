  

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
eval "$(zoxide init --cmd cd zsh)"


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
export PATH="$PATH:$HOME/.modular/bin"
# Add this to your ~/.bashrc or ~/.zshrc file
open_with_ranger() {
    selected_file=$(find ~ -maxdepth 4 -type f 2>/dev/null | fzf --preview 'cat {}')
    [ -n "$selected_file" ] && ranger --selectfile="$selected_file"
}

alias rzf='open_with_ranger'
push_code() {
    # Start in the current directory
    dir="$PWD"
    
    # Traverse up until we find a .git directory or reach the root
    while [ "$dir" != "/" ]; do
        if [ -d "$dir/.git" ]; then
            # If .git directory is found, run push.sh from the found directory
            (cd "$dir" && bash push.sh)
            return
        fi
        # Move up one directory
        dir=$(dirname "$dir")
    done
    
    # If no git repo was found
    echo "No git repository found in this directory or its parents."
}


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

alias update-onegai='sudo -v && sudo apt update 2>&1 | lolcat && sudo apt upgrade -y 2>&1 | lolcat && sudo apt autoremove -y 2>&1 | lolcat && flatpak update -y 2>&1 | lolcat'
# alias wifi-fix='sudo service network-manager restart'
alias oyasumi='shutdown now'
alias o='xdg-open'
alias hotspot-on='nmcli device wifi hotspot ifname wlp1s0f0 ssid "${HOTSPOT_SSID:-Haoshoku}" password "${HOTSPOT_PASS:?Set HOTSPOT_PASS}"'
alias hotspot-off='nmcli connection down Hotspot-1'
alias open-ports='sudo ss -tuln'
alias active-connections='nmcli connection show --active'

# export OPENROUTER_API_KEY  # set in ~/.secrets or env
# export ANTHROPIC_BASE_URL="https://openrouter.ai/api"
# export ANTHROPIC_AUTH_TOKEN="$OPENROUTER_API_KEY"
# export ANTHROPIC_API_KEY="" 

# export ANTHROPIC_MODEL="openrouter/free"
# # export ANTHROPIC_DEFAULT_SONNET_MODEL="qwen/qwen2.5-72b-instruct"
# # export ANTHROPIC_DEFAULT_HAIKU_MODEL="qwen/qwen2.5-72b-instruct"
# # export CLAUDE_CODE_SUBAGENT_MODEL="qwen/qwen2.5-72b-instruct"



[[ -f "$HOME/.local/bin/env" ]] && . "$HOME/.local/bin/env"

export PATH="$HOME/.npm-global/bin:$PATH"


# Added by Antigravity CLI installer
export PATH="$HOME/.local/bin:$PATH"

# Composio CLI
export COMPOSIO_INSTALL_DIR="$HOME/.composio"
export PATH="$COMPOSIO_INSTALL_DIR:$PATH"


export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH

