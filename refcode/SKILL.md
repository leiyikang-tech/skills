---
name: refcode
description: Extract, classify, register and query reference code across many open-source projects, so an agent can cite real peer implementations (file:line) instead of re-deriving them. Turns a folder or a git URL into searchable "retrieval documents" (tree-sitter symbols + BM25 body windows) in one self-contained SQLite DB (FTS5). Use when building/porting a subsystem and you need how a peer project solved it; when adding reference-code retrieval to an analysis workflow (e.g. repo-map Op3); or when you want a reusable, shareable corpus of pinned projects. Triggers - refcode, reference code, 参考代码, 找实现, how did X implement Y, cite file:line, corpus of projects, index an open-source project for retrieval.
---

# refcode — reference-code retrieval across projects

The portable core of XERJ's "repo → retrieval documents" pipeline, with no server
and no daemon: **one SQLite file**. It exists so a coding or analysis agent can
answer *"how did project X implement Y?"* with a real `file:line`, the way XERJ's
own contributors do (`xerj search` / `xerj def`).

## The four capabilities

| verb | what it does | XERJ origin |
|---|---|---|
| **extract** | one source file → one doc `{language, symbols[], defs, body}`; tree-sitter AST, per-language `TAGS_QUERY` where the grammar ships one, else a generic definition-node heuristic | `xerj-autoindex/src/extract/code.rs` |
| **classify** | project → `{languages, domain, dependency_names}` (domain from lockfile deps + name/keyword hints; **heuristic**, never claimed as ground truth) | `xerj-hub/src/{catalogue,router}.rs` |
| **register** | a project → a pinned corpus row `url + 40-hex sha + licence + use_policy`; the tiny, shareable manifest (no source) | `tools/xerj-code/hub/*.json` |
| **query** | BM25 over body windows (FTS5) **+** exact symbol lookup, symbols ranked first | `xccode::run_code_query` (`passage.rs`, `fields.rs`) |

## Install / runtime

Grammars live in the skill's own venv (compiled wheels, no runtime download):

```bash
/root/.agents/skills/refcode/.venv/bin/python --version   # 3.12
/root/.agents/skills/refcode/.venv/bin/pip freeze | grep tree-sitter
```

`./refcode` (bash launcher) auto-selects `.venv/bin/python`, falling back to
`python3`. 25 language grammars installed: python, rust, javascript, typescript, go,
java, c, cpp, ruby, php, c_sharp, bash, scala, haskell, kotlin, swift, lua,
elixir, json, yaml, toml, html, css, sql, markdown (see `requirements.txt`).

> If a grammar host is unreachable, grammars are **per-language PyPI wheels**
> (`tree-sitter-<lang>`), not the runtime-downloading `tree-sitter-language-pack`.

## Usage

```bash
R=/root/.agents/skills/refcode/refcode

# 1) index a local folder OR a git URL (shallow clone, optional pinned sha)
$R index xerj-hub /path/to/xerj/engine/crates/xerj-hub --licence Apache-2.0
$R index tantivy https://github.com/quickwit-oss/tantivy --sha 3a55bc98... --licence MIT

# 2) query: symbols first, then BM25 body windows, each with file:line
$R query "how is the BM25 score computed" -k 5
$R def route_ranked                      # exact symbol lookup
$R query "..." --project qdrant --json   # scoped / machine-readable

# 3) register corpora from a manifest (XERJ corpus.json-compatible)
$R corpus add --from seed/corpora.json
$R corpus list
$R corpus export > corpora.json          # the shareable artifact

# 4) which corpora answer a target repo? (reads its lockfiles)
$R route /path/to/target/repo

# 5) freshness + portability
$R refresh --dry-run                     # git ls-remote -> STALE/fresh per pin
$R stats
$R verify report.md                      # check every [slug] path:line peer-anchor resolves
$R dump --out refcode.dump.sql           # git-friendly text dump
```

## Where the database lives

- Default: `$REFCODE_DB`, else `~/.refcode/refcode.db` (a single SQLite file; WAL).
  Override per call with `--db`.
- For the shared analysis home, point it at
  `/root/.sisyphus/db/refcode.db` (sibling of repo-map's `analysis.db`).
- Clone cache: `$REFCODE_REPOS`, else `~/.refcode/repos/<slug>`.

**Can it live on GitHub?** Yes — but push the *manifest + a text dump*, not the
binary index. This is exactly XERJ's corpus-hub rule ("share the definition, not
the index"):

- ✅ commit `seed/corpora.json` (a few hundred bytes: url + sha + licence) and
  `refcode dump --out refcode.dump.sql` (diffable SQL). Anyone rebuilds byte-identical
  indices with `corpus add` + `index`.
- ✅ or publish the binary `.db` as a **release asset** (not in git history).
- ❌ do not commit the live WAL `.db` — binary, churns, merges badly.

## Honest limits

- **Symbol extraction quality varies by grammar.** 11 languages ship a proper
  `TAGS_QUERY` (python, rust, javascript, go, java, c, cpp, ruby, php, c_sharp,
  lua); the rest use a generic definition-node heuristic (function/class/struct/
  enum/trait/…). Body retrieval works regardless of symbol quality.
- **`classify` domain is a heuristic**, and `dependency_names` is only as good as
  the lockfiles present at the indexed root — a crate indexed from inside a
  workspace (no lockfile) yields no deps. Register deps explicitly via `corpus add`.
- **Not a code graph.** No call/reference edges (that is `codegraph`). refcode is
  the *retrieval* layer: symbols + BM25 passages.
- **Licence discipline is metadata, not enforcement.** `use_policy`
  (`adapt-with-attribution` / `approach-only` / `mixed`) is recorded for the agent
  to respect; refcode never copies code anywhere.

## Wiring into repo-map

repo-map's Op3 research agents must cite real implementations. Add **Op3.5**:
`refcode route <target-repo>` → pull the matching corpora → `refcode query "…"`
→ hand the agent `file:line` evidence. The Q6 gate (`depth_check.py`) then checks
every cross-project mechanism claim resolves to a real `ref_symbols` anchor.
