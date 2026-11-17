#!/usr/bin/env bash
set -euo pipefail

/opt/pychemqt/start-desktop.sh
exec tail -f /dev/null
