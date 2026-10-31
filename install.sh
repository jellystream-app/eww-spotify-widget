#!/bin/sh
set -e
D="$HOME/.config/eww-viper"
SRC="$(cd "$(dirname "$0")" && pwd)/eww-viper"
mkdir -p "$D"
KEEP=""
if [ -f "$D/config.ini" ]; then KEEP=$(mktemp); cp "$D/config.ini" "$KEEP"; fi
cp -r "$SRC/." "$D/"
if [ -n "$KEEP" ]; then cp "$KEEP" "$D/config.ini"; rm -f "$KEEP"; fi
chmod +x "$D/start.sh" "$D/mode.sh" "$D/scripts/music.py" "$D/scripts/render.py"
python3 "$D/scripts/render.py"
echo "Installed to $D"
echo "Start:  $D/start.sh"
echo "Config: $D/config.ini   (apply with: $D/mode.sh reload)"
