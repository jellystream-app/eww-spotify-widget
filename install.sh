#!/bin/sh
set -e
D="$HOME/.config/eww-viper"
mkdir -p "$D"
cp -r "$(dirname "$0")/eww-viper/." "$D/"
chmod +x "$D/start.sh" "$D/scripts/music.py"
echo "Installed to $D  ->  run: $D/start.sh"
