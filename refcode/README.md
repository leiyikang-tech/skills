# refcode — cross-project reference-code retrieval

The portable core of XERJ's *"open-source project → retrieval documents"* pipeline,
with no server and no daemon: **one self-contained SQLite file** (FTS5 BM25 +
tree-sitter symbols). It lets an agent answer *"how did project X implement Y?"*
with a real `file:line` instead of re-deriving it — the discipline XERJ's own
contributors use.

It is a companion to [`repo-map/`](../repo-map/): repo-map analyses **one** repo,
refcode supplies the **peers'** actual implementations so Op3 mechanism claims
carry a peer `file:line` instead of an assertion.

## The four capabilities

| verb | what it does | XERJ origin |
|---|---|---|
| **extract** | source file → doc `{language, symbols[], defs, body}` (tree-sitter AST; per-language `TAGS_QUERY`, else a generic definition-node heuristic) | `xerj-autoindex/…/extract/code.rs` |
| **classify** | project → `{languages, domain, dependency_names}` (heuristic; curated rows win) | `xerj-hub/src/{catalogue,router}.rs` |
| **register** | project → a pinned corpus row `url + 40-hex sha + licence + use_policy` (the tiny shareable manifest, no source) | `tools/xerj-code/hub/*.json` |
| **query** | BM25 over body windows (FTS5) **+** exact symbol lookup, symbols ranked first | `xccode::run_code_query` |

## Install

```bash
bash install.sh                     # -> $HOME/.agents/skills/refcode (+ venv + grammars)
bash install.sh REFCODE_HOME=/opt/skills/refcode NO_VENV=1   # custom dir, no venv
```

The installer also drops two **standalone commands** into `${BIN_DIR:-$HOME/.local/bin}`:
`refcode` (full CLI) and `refcode-build` (build front door).

Grammars are compiled PyPI wheels (`tree-sitter-<lang>`, see `requirements.txt`) —
no runtime download. 25 languages.

## Use

```bash
R="$HOME/.agents/skills/refcode/refcode"

$R route /path/to/target/repo                      # which corpora answer this? (reads its lockfiles)
$R index tantivy https://github.com/quickwit-oss/tantivy --licence MIT
$R corpus add --from seed/corpora.json             # register the seed corpus table
$R query "segment merge policy" -k 5               # symbols first, then BM25 passages
$R def SegmentMeta                                 # exact symbol -> file:line
$R verify report.md                                # check every [slug] path:line anchor resolves
$R refresh --dry-run                               # git ls-remote -> STALE/fresh per pin
$R dump --out refcode.dump.sql
```

## Where the database lives — and can it be on GitHub?

- Live DB: `${REFCODE_DB:-$HOME/.refcode/refcode.db}` (one SQLite file, WAL).
  Repos cache: `${REFCODE_REPOS:-$HOME/.refcode/repos/<slug>}`.
- **On GitHub — yes, but share the *definition*, not the index** (XERJ's corpus-hub
  rule). This repo ships `seed/corpora.json` (a few KB: url + sha + licence).
  Anyone rebuilds a byte-identical index with `corpus add` + `index`.
- Do **not** commit the live `.db` (binary, churns, merges badly). For a
  ready-to-query copy, attach it as a **release asset** (or use git-lfs):
  `gh release upload <tag> refcode.db`.

## Honest limits

- Symbol quality varies by grammar: 11 languages ship a real `TAGS_QUERY`; the rest
  use a generic heuristic. Body retrieval works regardless.
- `classify` domain is a heuristic; `dependency_names` is only as good as the
  lockfiles present at the indexed root (index a workspace member with no lockfile
  → no deps; register them explicitly via `corpus add`).
- **Not a code graph** — no call/reference edges (that is `codegraph`). refcode is
  the retrieval layer: symbols + BM25 passages.
- Licence discipline is metadata, not enforcement: respect `use_policy`
  (`approach-only` corpora are read for design, never copied).

## Layout

```
SKILL.md              the agent-facing skill
refcode               launcher (path-relative; prefers ./.venv)
refcode.py            the engine (extract / classify / register / query / verify / refresh)
bin/refcode           standalone command template (materialized to $BIN_DIR)
bin/refcode-build     write-side command template (build front door)
references/refcode.sql  the schema
seed/corpora.json     the seed corpus table (curated domain -> projects)
install.sh            template materializer
requirements.txt      tree-sitter grammar wheels
```
