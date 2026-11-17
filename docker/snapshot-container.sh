#!/usr/bin/env bash
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
STAMP=$(date +%Y%m%d-%H%M%S)
DEST="$REPO/docker/backups/$STAMP"
VENV=${PYCHEMQT_VENV:-/opt/pychemqt-venv}
RUNTIME=${PYCHEMQT_RUNDIR:-/opt/pychemqt}
CONFIG=${PYCHEMQT_CONFIG:-/root/.pychemqt}

mkdir -p "$DEST"

if [ -d "$CONFIG" ]; then
    mkdir -p "$DEST/pychemqt-config"
    cp -a "$CONFIG/." "$DEST/pychemqt-config/"
    rm -f "$DEST/pychemqt-config/pychemqt.log"
fi

if [ -d "$RUNTIME" ]; then
    mkdir -p "$DEST/pychemqt-runtime"
    find "$RUNTIME" -maxdepth 1 -type f -name '*.sh' -exec cp -a {} "$DEST/pychemqt-runtime/" \;
fi

"$VENV/bin/pip" freeze | sort >"$DEST/pip-freeze.txt"
apt-mark showmanual 2>/dev/null | sort >"$DEST/apt-manual.txt" || true
git -C "$REPO" status --short >"$DEST/git-status.txt" 2>/dev/null || true

cat >"$DEST/restore.txt" <<EOF
Container state snapshot: $STAMP

Rebuild the image on the Docker host:
  cd "$REPO"
  docker build -t pychemqt-ready docker

Run with the source and saved config mounted:
  docker run -d --name pychemqt \\
    -p 127.0.0.1:6080:6080 \\
    -v "$REPO:/workspace/pychemqt" \\
    -v "$DEST/pychemqt-config:/root/.pychemqt" \\
    pychemqt-ready

If the repository is mounted at a different path, add:
  -e PYCHEMQT_APP=/path/to/pychemqt

The saved runtime scripts are in:
  $DEST/pychemqt-runtime

Full image backup from the host:
  "$REPO/docker/backup.sh" pychemqt
EOF

echo "Container snapshot created: $DEST"
