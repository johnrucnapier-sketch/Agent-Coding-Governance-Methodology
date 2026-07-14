#!/bin/sh
# Compatibility entry point retained for pre-V3 hook configurations.
set -eu
SELF_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$SELF_DIR/acgm-hook.sh" session-start
