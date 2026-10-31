#!/bin/sh
# Usage: mode.sh [full|compact|toggle|reload]   (no argument = toggle)
export PATH="$HOME/.local/bin:$HOME/eww/target/release:$PATH"
export GDK_BACKEND=x11
CFG="$HOME/.config/eww-viper"
FILE="$CFG/mode"
cur=$(cat "$FILE" 2>/dev/null || echo full)

case "$1" in
  full|compact) new="$1" ;;
  toggle|"")    if [ "$cur" = compact ]; then new=full; else new=compact; fi ;;
  reload)       new="$cur" ;;
  *) echo "Usage: mode.sh [full|compact|toggle|reload]"; exit 1 ;;
esac

echo "$new" > "$FILE"
python3 "$CFG/scripts/render.py" || exit 1
eww -c "$CFG" reload >/dev/null 2>&1
eww -c "$CFG" close viper-music viper-music-compact >/dev/null 2>&1
if [ "$new" = compact ]; then
  eww -c "$CFG" open viper-music-compact
else
  eww -c "$CFG" open viper-music
fi
