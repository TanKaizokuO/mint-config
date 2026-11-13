[[ -f "$HOME/.cargo/env" ]] && . "$HOME/.cargo/env"

# tmux string-matches LANG/LC_CTYPE for "UTF-8" instead of calling nl_langinfo(),
# so bare "en_IN" (which IS UTF-8) makes it mangle every glyph into "_".
export LANG=en_IN.UTF-8
export LC_CTYPE=en_IN.UTF-8
