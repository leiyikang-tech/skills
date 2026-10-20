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
OPENCODE_COMMAND_DIR="${OPENCODE_COMMAND_DIR:-$HOME/.config/opencode/command}"

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
[ -f "$DEST/harness/cleanup.py" ] || { echo "ERROR: harness/cleanup.py not installed"; exit 1; }
if find "$DEST" -type f ! -name 'install.sh' | xargs grep -l "{{[A-Z_]*}}" 2>/dev/null; then
  echo "ERROR: unsubstituted placeholder left in installed files"
  exit 1
fi

# ---- convenience: ensure the shared analysis DB dir exists ----
mkdir -p "$(dirname "$ANALYSIS_DB")"

# ---- register opencode slash-commands (commands/*.md -> opencode command dir) ----
# The skill ships repo-map.md + awesome-map.md as command templates. Without this,
# /repo-map (and siblings) resolve to whatever stale copy sits in the opencode
# command dir, not this install. Copying the materialized commands keeps the
# slash-command and the skill on the same (substituted) paths.
if [ -d "$DEST/commands" ]; then
  mkdir -p "$OPENCODE_COMMAND_DIR"
  cp -f "$DEST"/commands/*.md "$OPENCODE_COMMAND_DIR/"
  echo "  commands -> $OPENCODE_COMMAND_DIR/ ($(ls "$DEST"/commands/*.md 2>/dev/null | wc -l) registered)"
fi

echo "installed: $DEST"
echo "  REPO_MAP_HOME=$REPO_MAP_HOME"
echo "  ANALYSIS_DB=$ANALYSIS_DB"
echo "  REPOS_DIR=$REPOS_DIR"
echo "  KNOWLEDGE_REPO_URL=$KNOWLEDGE_REPO_URL"
echo "  KNOWLEDGE_REPO_DIR=$KNOWLEDGE_REPO_DIR"

# ---- dependency check (non-fatal: warn, never fail the install) ----
# repo-map's playbooks rely on two external tools that are NOT bundled:
#   codegraph  self-project symbol graph (npm @colbymchenry/codegraph, MIT)
#   refcode    cross-project reference retrieval (sibling skill, leiyikang-tech/skills)
warn_dep() {
  local name="$1" hint="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "  WARN  $name: MISSING -> $hint"
    return 1
  fi
  echo "  ok    $name: $(command -v "$name")"
  return 0
}
missing=0
warn_dep codegraph "npm install -g @colbymchenry/codegraph@latest" || missing=1
warn_dep refcode  "bash <refcode-dir>/install.sh" || missing=1
if [ "$missing" -ne 0 ]; then
  echo "  NOTE: missing tools above are required by repo-map's playbooks (codegraph for the"
  echo "        self-project symbol graph, refcode for peer file:line evidence). Until they are"
  echo "        installed, Op1/Op2/Op3 fall back to explore agents for those steps."
fi

echo "OK: SKILL.md + references + harness materialized with real paths."