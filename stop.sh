#!/usr/bin/env bash
# Stop Biomni-Desk started with ./start.sh
cd "$(dirname "$0")"
for name in web backend; do
    pidfile="ui_data/$name.pid"
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        kill "$pid" 2>/dev/null && echo "Stopped $name ($pid)" || echo "$name was not running"
        rm -f "$pidfile"
    fi
done
