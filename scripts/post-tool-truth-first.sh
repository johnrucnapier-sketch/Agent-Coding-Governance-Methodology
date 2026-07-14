#!/bin/sh
# Compatibility entry point retained for pre-V3 hook configurations.
# V3 reports to Claude and the Event Ledger; it never appends to user files.
set -eu
SELF_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$SELF_DIR/acgm-hook.sh" posttool
