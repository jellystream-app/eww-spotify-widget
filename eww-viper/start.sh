#!/bin/sh
# GNOME has no layer-shell -> eww runs through XWayland
export PATH="$HOME/.local/bin:$HOME/eww/target/release:$PATH"
export GDK_BACKEND=x11
CFG="$HOME/.config/eww-viper"
eww -c "$CFG" kill 2>/dev/null
eww -c "$CFG" daemon
sleep 1
eww -c "$CFG" open viper-music
