#!/usr/bin/env bash
set -u
FILE="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/p2000-monitor.desktop"
rm -f "$FILE"; echo 'P2000 autostart verwijderd.'
