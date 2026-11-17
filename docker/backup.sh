#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
    echo "Run this script on the Docker host, not inside the container." >&2
    exit 1
fi

CONTAINER=${1:-${PYCHEMQT_CONTAINER:-pychemqt}}
TAG=${2:-$(date +%Y%m%d-%H%M%S)}
IMAGE=${PYCHEMQT_IMAGE:-pychemqt-ready}
REPO=${PYCHEMQT_HOST_REPO:-$(pwd)}
SAVE_IMAGE=${PYCHEMQT_SAVE_IMAGE:-1}
BACKUP_REPO=${PYCHEMQT_BACKUP_REPO:-0}
BACKUP_DIR=${PYCHEMQT_BACKUP_DIR:-"$HOME/pychemqt-backup-$TAG"}

mkdir -p "$BACKUP_DIR"
BACKUP_DIR=$(cd "$BACKUP_DIR" && pwd)

docker inspect "$CONTAINER" >"$BACKUP_DIR/container-inspect.json"
docker commit "$CONTAINER" "$IMAGE:$TAG"
docker cp "$CONTAINER:/root/.pychemqt" "$BACKUP_DIR/pychemqt-config"
docker cp "$CONTAINER:/opt/pychemqt" "$BACKUP_DIR/pychemqt-runtime"

if [ "$SAVE_IMAGE" = "1" ]; then
    docker save "$IMAGE:$TAG" -o "$BACKUP_DIR/pychemqt-image.tar"
    LOAD_IMAGE="docker load -i \"$BACKUP_DIR/pychemqt-image.tar\""
else
    LOAD_IMAGE="# image not saved; use $IMAGE:$TAG on this host"
fi

if [ "$BACKUP_REPO" = "1" ]; then
    tar --exclude='.git' --exclude='pychemqt-backup-*' \
        -czf "$BACKUP_DIR/pychemqt-repo.tar.gz" \
        -C "$(dirname "$REPO")" "$(basename "$REPO")"
fi

cat >"$BACKUP_DIR/restore.txt" <<EOF
$LOAD_IMAGE
docker run -d --name pychemqt \\
  -p 127.0.0.1:6080:6080 \\
  -v "$REPO:/workspace/pychemqt" \\
  -v "$BACKUP_DIR/pychemqt-config:/root/.pychemqt" \\
  "$IMAGE:$TAG"
EOF

echo "Backup created: $BACKUP_DIR"
echo "Image: $IMAGE:$TAG"
echo "Restore instructions: $BACKUP_DIR/restore.txt"
