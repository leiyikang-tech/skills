#!/usr/bin/env bash
# Install the refcode-build skill (the write-side front door to refcode).
# It needs the refcode engine; install refcode first if you have not:
#   cd refcode && bash install.sh
#
#   Usage: bash install.sh [SKILL_DIR=...] [REFCODE_HOME=...]
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills}"
REFCODE_HOME="${REFCODE_HOME:-$SKILL_DIR/refcode}"
DEST="$SKILL_DIR/refcode-build"

mkdir -p "$DEST"
cp "$SRC/SKILL.md" "$DEST/SKILL.md"
rm -rf "$DEST/.git" "$DEST/install.sh"
sed -i "s#{{REFCODE_HOME}}#$REFCODE_HOME#g" "$DEST/SKILL.md"

if grep -q "{{[A-Z_]*}}" "$DEST/SKILL.md"; then
  echo "ERROR: unsubstituted placeholder left in SKILL.md" >&2
  exit 1
fi
[ -x "$REFCODE_HOME/refcode" ] || {
  echo "WARNING: refcode engine not found at $REFCODE_HOME/refcode" >&2
  echo "         install it first: cd refcode && bash install.sh" >&2
}

echo "refcode-build installed at $DEST"
echo "  needs the refcode engine at $REFCODE_HOME (provides the refcode-build command)"
