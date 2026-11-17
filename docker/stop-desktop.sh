#!/usr/bin/env bash
set -u

DISPLAY_NUM=${PYCHEMQT_DISPLAY:-99}
WEB_PORT=${PYCHEMQT_WEB_PORT:-6080}
RUNDIR=${PYCHEMQT_RUNDIR:-/opt/pychemqt}
PIDDIR="$RUNDIR/pids"
VENV=${PYCHEMQT_VENV:-/opt/pychemqt-venv}

for name in pychemqt websockify x11vnc openbox xvfb; do
    pidfile="$PIDDIR/$name.pid"
    if [ -f "$pidfile" ]; then
        pid="$(cat "$pidfile")"
        kill "$pid" 2>/dev/null || true
        rm -f "$pidfile"
    fi
done

pkill -f "$VENV/bin/python pychemqt.py" 2>/dev/null || true
pkill -f "websockify.*${WEB_PORT}" 2>/dev/null || true
pkill -f "x11vnc.*:${DISPLAY_NUM}" 2>/dev/null || true
pkill -f "Xvfb :${DISPLAY_NUM}" 2>/dev/null || true

echo "Desktop stopped."
