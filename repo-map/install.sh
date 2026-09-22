#!/usr/bin/env bash
# Install repo-map skill into the active skill registry.
#
# This package ships as a portable TEMPLATE: machine-specific paths appear as
# {{PLACEHOLDER}} tokens (REPO_MAP_HOME / ANALYSIS_DB / REPOS_DIR /
# KNOWLEDGE_REPO_URL / KNOWLEDGE_REPO_DIR). This installer substitutes real
# paths at install time and materializes a working copy into the skill
# registry, leaving the GitHub clone pristine and portable.
#
#   Usage:  bash install.sh [SKILL_DIR=<skill-registry-dir>] [REPO_MAP_HOME=...]
#                            [ANALYSIS_DB=...] [REPOS_DIR=...]
#                            [KNOWLEDGE_REPO_URL=...] [KNOWLEDGE_REPO_DIR=...]
#
#   Defaults (overridable via env):
#     SKILL_DIR            $HOME/.agents/skills   (skill registry)
#     REPO_MAP_HOME        $HOME/.sisyphus/repo-map
#     ANALYSIS_DB          $HOME/.sisyphus/db/analysis.db
#     REPOS_DIR            $HOME/.sisyphus/repos
#     KNOWLEDGE_REPO_URL   the git URL of the knowledge repo you persist to
#     KNOWLEDGE_REPO_DIR   the local clone of that knowledge repo
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${SKILL_DIR:-$HOME/.agents/skills}"
REPO_MAP_HOME="${REPO_MAP_HOME:-$HOME/.sisyphus/repo-map}"
ANALYSIS_DB="${ANALYSIS_DB:-$HOME/.sisyphus/db/analysis.db}"
REPOS_DIR="${REPOS_DIR:-$HOME/.sisyphus/repos}"
KNOWLEDGE_REPO_URL="${KNOWLEDGE_REPO_URL:-}"
KNOWLEDGE_REPO_DIR="${KNOWLEDGE_REPO_DIR:-}"

DEST="$SKILL_DIR/repo-map"
rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")"
cp -r "$SRC" "$DEST"

# ---- substitute placeholders in the materialized copy ----
# install.sh itself is excluded: its sed patterns legitimately contain
# {{TOKEN}} regex literals and must not be rewritten.
subst() {
  local f
  find "$DEST" -type f \( -name '*.md' -o -name '*.py' -o -name '*.sql' \) ! -name 'install.sh' | while read -r f; do
    sed -i \
      -e "s#{{REPO_MAP_HOME}}#$REPO_MAP_HOME#g" \
      -e "s#{{ANALYSIS_DB}}#$ANALYSIS_DB#g" \
      -e "s#{{REPOS_DIR}}#$REPOS_DIR#g" \
      -e "s#{{KNOWLEDGE_REPO_URL}}#$KNOWLEDGE_REPO_URL#g" \
      -e "s#{{KNOWLEDGE_REPO_DIR}}#$KNOWLEDGE_REPO_DIR#g" \
      "$f"
  done
}
subst

# ---- sanity: the installed skill resolves its own references + harness ----
[ -f "$DEST/SKILL.md" ] || { echo "ERROR: SKILL.md not installed"; exit 1; }
[ -d "$DEST/references" ] || { echo "ERROR: references/ not installed"; exit 1; }
[ -f "$DEST/harness/gates.py" ] || { echo "ERROR: harness/gates.py not installed"; exit 1; }
if find "$DEST" -type f ! -name 'install.sh' | xargs grep -l "{{[A-Z_]*}}" 2>/dev/null; then
  echo "ERROR: unsubstituted placeholder left in installed files"
  exit 1
fi

# ---- convenience: ensure the shared analysis DB dir exists ----
mkdir -p "$(dirname "$ANALYSIS_DB")"

echo "installed: $DEST"
echo "  REPO_MAP_HOME=$REPO_MAP_HOME"
echo "  ANALYSIS_DB=$ANALYSIS_DB"
echo "  REPOS_DIR=$REPOS_DIR"
echo "  KNOWLEDGE_REPO_URL=$KNOWLEDGE_REPO_URL"
echo "  KNOWLEDGE_REPO_DIR=$KNOWLEDGE_REPO_DIR"
echo "OK: SKILL.md + references + harness materialized with real paths."