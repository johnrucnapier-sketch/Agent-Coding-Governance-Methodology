#!/bin/sh
# Build a release only from committed bytes. PACKAGE_MANIFEST.json must already
# have been generated and committed by the release owner.
set -eu

SELF_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SELF_DIR/.." && pwd)
cd "$ROOT"

if [ -n "$(git status --porcelain --untracked-files=all)" ]; then
  echo "release build refused: the working tree is not clean" >&2
  echo "提交或移走所有非 ignored 改动后再构建发布包。" >&2
  exit 1
fi

python3 -m unittest discover -s tests -v
python3 scripts/generate-package-manifest.py --check
python3 scripts/release_check.py --require-package-manifest

VERSION=$(tr -d '[:space:]' < VERSION)
DIST_DIR=${ACGM_DIST_DIR:-"$ROOT/dist"}
ARCHIVE_BASENAME="Agent-Coding-Governance-Methodology-$VERSION.tar.gz"
ARCHIVE="$DIST_DIR/$ARCHIVE_BASENAME"
CHECKSUM="$ARCHIVE.sha256"

mkdir -p "$DIST_DIR"
git archive \
  --format=tar.gz \
  --prefix="Agent-Coding-Governance-Methodology-$VERSION/" \
  --output="$ARCHIVE" \
  HEAD

python3 - "$ARCHIVE" "$CHECKSUM" <<'PY'
from pathlib import Path
import hashlib
import sys

archive = Path(sys.argv[1])
checksum = Path(sys.argv[2])
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
print(f"sha256 {digest}")
PY

echo "release archive: $ARCHIVE"
echo "checksum:        $CHECKSUM"
