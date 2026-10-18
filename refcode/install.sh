#!/usr/bin/env bash
# Install the refcode skill: materialize the template into the skill registry,
# create its private venv, and install the tree-sitter grammar wheels.
#
# The GitHub package is a portable TEMPLATE: machine paths appear as
# {{REFCODE_HOME}}. This installer substitutes the real path at install time,
# so the clone stays pristine (same convention as the repo-map skill).
#
#   Usage: bash install.sh [SKILL_DIR=...] [REFCODE_HOME=...] [BIN_DIR=...] [NO_VENV=1]
#
#   Defaults: SKILL_DIR=$HOME/.agents/skills  REFCODE_HOME=$SKILL_DIR/refcode
#             BIN_DIR=$HOME/.local/bin   (the `refcode` + `refcode-build` commands)
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills}"
REFCODE_HOME="${REFCODE_HOME:-$SKILL_DIR/refcode}"
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
DEST="$REFCODE_HOME"   # refcode is self-contained: no other home dir needed

mkdir -p "$DEST"
cp -r "$SRC"/. "$DEST"/
rm -rf "$DEST/.git" "$DEST/install.sh" "$DEST/.venv" "$DEST/__pycache__"

sed -i "s#{{REFCODE_HOME}}#$REFCODE_HOME#g" "$DEST/SKILL.md"

if find "$DEST" -type f \( -name '*.md' -o -name '*.py' -o -name '*.sql' \) \
     ! -name 'install.sh' | xargs grep -l "{{[A-Z_]*}}" 2>/dev/null; then
  echo "ERROR: unsubstituted placeholder left in installed files" >&2
  exit 1
fi

if [[ "${NO_VENV:-0}" != "1" ]]; then
  python3 -m venv "$DEST/.venv"
  "$DEST/.venv/bin/pip" install -q --upgrade pip
  "$DEST/.venv/bin/pip" install -q -r "$SRC/requirements.txt"
fi

[ -f "$DEST/SKILL.md" ] || { echo "ERROR: SKILL.md not installed" >&2; exit 1; }
[ -x "$DEST/refcode" ] || { echo "ERROR: launcher not executable" >&2; exit 1; }

# Standalone commands on PATH: `refcode` (full) + `refcode-build` (write-side front door).
mkdir -p "$BIN_DIR"
for w in refcode refcode-build; do
  sed "s#{{REFCODE_HOME}}#$REFCODE_HOME#g" "$DEST/bin/$w" > "$BIN_DIR/$w"
  chmod +x "$BIN_DIR/$w"
done

echo "refcode installed at $DEST"
echo "  run:  $DEST/refcode stats      (or: $BIN_DIR/refcode)"
echo "  build: $BIN_DIR/refcode-build index --all"
echo "  db:   \${REFCODE_DB:-$HOME/.refcode/refcode.db}   (set REFCODE_DB to relocate)"
