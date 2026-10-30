#!/bin/sh
# Usage: mode.sh [full|compact|toggle]   (ohne Argument = toggle)
export PATH="$HOME/.local/bin:$HOME/eww/target/release:$PATH"
export GDK_BACKEND=x11
CFG="$HOME/.config/eww-viper"
FILE="$CFG/mode"
cur=$(cat "$FILE" 2>/dev/null || echo full)

case "$1" in
  full|compact) new="$1" ;;
  toggle|"")    if [ "$cur" = compact ]; then new=full; else new=compact; fi ;;
  *) echo "Usage: mode.sh [full|compact|toggle]"; exit 1 ;;
esac

echo "$new" > "$FILE"
eww -c "$CFG" close viper-music viper-music-compact >/dev/null 2>&1
if [ "$new" = compact ]; then
  eww -c "$CFG" open viper-music-compact
else
  eww -c "$CFG" open viper-music
fi
