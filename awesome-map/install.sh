#!/usr/bin/env bash
# Install awesome-map skill into the active skill registry.
# Materializes a portable template ({{PLACEHOLDER}} tokens) into a working
# copy with real paths, leaving the GitHub clone pristine. Requires the
# repo-map skill to be installed (awesome-map drives repo-map's awesome-list
# mode). Point REPO_MAP_HOME at the installed repo-map skill directory.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills}"
REPO_MAP_HOME="${REPO_MAP_HOME:-$HOME/.sisyphus/repo-map}"
REPOS_DIR="${REPOS_DIR:-$HOME/.sisyphus/repos}"
KNOWLEDGE_REPO_URL="${KNOWLEDGE_REPO_URL:-}"

DEST="$SKILL_DIR/awesome-map"
rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")"
cp -r "$SRC" "$DEST"

find "$DEST" -type f \( -name '*.md' -o -name '*.py' -o -name '*.sql' \) ! -name 'install.sh' | while read -r f; do
  sed -i \
    -e "s#{{REPO_MAP_HOME}}#$REPO_MAP_HOME#g" \
    -e "s#{{REPOS_DIR}}#$REPOS_DIR#g" \
    -e "s#{{KNOWLEDGE_REPO_URL}}#$KNOWLEDGE_REPO_URL#g" \
    "$f"
done

[ -f "$DEST/SKILL.md" ] || { echo "ERROR: SKILL.md not installed"; exit 1; }
if find "$DEST" -type f ! -name 'install.sh' | xargs grep -lE "\{\{[A-Z_]+\}\}" 2>/dev/null; then
  echo "ERROR: unsubstituted placeholder left in installed files"
  exit 1
fi

echo "installed: $DEST (drives repo-map at $REPO_MAP_HOME)"
echo "OK: awesome-map materialized with real paths."