#!/usr/bin/env bash
set -euo pipefail

DISPLAY_NUM=${PYCHEMQT_DISPLAY:-99}
VNC_PORT=${PYCHEMQT_VNC_PORT:-5900}
WEB_PORT=${PYCHEMQT_WEB_PORT:-6080}
RUNDIR=${PYCHEMQT_RUNDIR:-/opt/pychemqt}
LOGDIR="$RUNDIR/logs"
PIDDIR="$RUNDIR/pids"
VENV=${PYCHEMQT_VENV:-/opt/pychemqt-venv}
APP=${PYCHEMQT_APP:-/workspace/pychemqt}
RUNTIME_DIR=${PYCHEMQT_RUNTIME_DIR:-/tmp/runtime-root}

if [ ! -f "$APP/pychemqt.py" ]; then
    echo "pychemqt.py not found in $APP" >&2
    exit 1
fi

mkdir -p "$LOGDIR" "$PIDDIR" "$RUNTIME_DIR"
chmod 700 "$RUNTIME_DIR"

pkill -f "$VENV/bin/python pychemqt.py" 2>/dev/null || true
pkill -f "websockify.*${WEB_PORT}" 2>/dev/null || true
pkill -f "x11vnc.*:${DISPLAY_NUM}" 2>/dev/null || true
pkill -f "Xvfb :${DISPLAY_NUM}" 2>/dev/null || true
sleep 1

nohup setsid Xvfb ":${DISPLAY_NUM}" -screen 0 1440x900x24 -nolisten tcp \
    >"$LOGDIR/xvfb.log" 2>&1 </dev/null &
echo $! >"$PIDDIR/xvfb.pid"
sleep 2

DISPLAY=":${DISPLAY_NUM}" nohup setsid openbox \
    >"$LOGDIR/openbox.log" 2>&1 </dev/null &
echo $! >"$PIDDIR/openbox.pid"
sleep 1

nohup setsid x11vnc -display ":${DISPLAY_NUM}" -forever -shared \
    -rfbport "$VNC_PORT" -localhost -nopw -noxdamage -quiet \
    >"$LOGDIR/x11vnc.log" 2>&1 </dev/null &
echo $! >"$PIDDIR/x11vnc.pid"
sleep 2

nohup setsid websockify --web=/usr/share/novnc "0.0.0.0:${WEB_PORT}" \
    "127.0.0.1:${VNC_PORT}" \
    >"$LOGDIR/websockify.log" 2>&1 </dev/null &
echo $! >"$PIDDIR/websockify.pid"
sleep 2

cd "$APP"
DISPLAY=":${DISPLAY_NUM}" \
XDG_RUNTIME_DIR="$RUNTIME_DIR" \
QTWEBENGINE_DISABLE_SANDBOX=1 \
QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --no-sandbox" \
nohup setsid "$VENV/bin/python" pychemqt.py --nosplash \
    >"$LOGDIR/pychemqt.log" 2>&1 </dev/null &
echo $! >"$PIDDIR/pychemqt.pid"
sleep 6

echo "Desktop started."
echo "Open: http://localhost:${WEB_PORT}/vnc.html?autoconnect=1&resize=scale"
