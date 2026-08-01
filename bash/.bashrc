# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac

# History
HISTSIZE=1000
HISTFILESIZE=2000
HISTCONTROL=ignoreboth
shopt -s histappend
shopt -s checkwinsize

# Core Configuration Directory
BASH_CONFIG_DIR="$HOME/.config/bash"

# Create config directory if it doesn't exist
[[ ! -d "$BASH_CONFIG_DIR" ]] && mkdir -p "$BASH_CONFIG_DIR"

# Source module files
source_if_exists(){
  [[ -f "$1" ]] && source "$1"
}

# Source modules in order
source_if_exists "$BASH_CONFIG_DIR/aliases.bash"
source_if_exists "$BASH_CONFIG_DIR/keybinds.bash"
source_if_exists "$BASH_CONFIG_DIR/prompt.bash"
source_if_exists "$BASH_CONFIG_DIR/functions/system.bash"
source_if_exists "$BASH_CONFIG_DIR/functions/utils.bash"

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$("$HOME/miniconda3/bin/conda" 'shell.bash' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
        . "$HOME/miniconda3/etc/profile.d/conda.sh"
    else
        export PATH="$HOME/miniconda3/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<


[[ -f "$HOME/.local/bin/env" ]] && . "$HOME/.local/bin/env"
export PATH="$HOME/.npm-global/bin:$PATH"


# Added by Antigravity CLI installer
export PATH="$HOME/.local/bin:$PATH"
[[ -f "$HOME/.cargo/env" ]] && . "$HOME/.cargo/env"
