#!/bin/sh
# GNOME has no layer-shell -> eww runs through XWayland
export PATH="$HOME/.local/bin:$HOME/eww/target/release:$PATH"
export GDK_BACKEND=x11
CFG="$HOME/.config/eww-viper"
MODE=$(cat "$CFG/mode" 2>/dev/null || echo full)
python3 "$CFG/scripts/render.py" || exit 1
eww -c "$CFG" kill 2>/dev/null
eww -c "$CFG" daemon
sleep 1
if [ "$MODE" = compact ]; then
  eww -c "$CFG" open viper-music-compact
else
  eww -c "$CFG" open viper-music
fi
