---
name: refcode-build
description: Build and extend the refcode corpus database — the shared SQLite of indexed open-source projects that refcode queries. Use when the user says "refcode-build", "form the database", "build the corpus DB", "建库", "索引这些仓库", "add a corpus", "refresh pins", "批量索引", or asks how the reference-code DB is produced. This is the build-side front door to the same engine refcode queries; it is NOT for querying code (use refcode for that).
---

# refcode-build — form the reference-code database

`refcode` is two front doors onto **one engine and one SQLite**:

```
refcode        → extract · classify · register · query     (read side)
refcode-build  → register · index · refresh · dump         (write side, this skill)
```

The database is built in two steps: **register** a corpus (its definition:
url + pinned sha + licence), then **index** it (clone → tree-sitter extract →
store symbols + BM25 body windows). Nothing is downloaded until you index.

## Standalone commands

Installed on PATH (`~/.local/bin`):

```bash
refcode-build                       # == refcode-build index --all  (index every registered corpus)
refcode-build index <slug> <url> [--sha <sha>] [--licence L]   # one project
refcode-build index --all [--limit N] [--dry-run]              # batch
refcode-build add --from seed/corpora.json                     # register from a manifest
refcode-build refresh --dry-run                                # is each pin stale?
refcode-build dump --out refcode.dump.sql                      # full-content SQL export (large; inspect/backup)
refcode-build stats                                            # what's in the DB
```

All map onto the `refcode` engine (`corpus add`, `index`, `refresh`, `dump`,
`stats`); `refcode-build` adds no logic, it is the write-side alias.

## The loop

```bash
# 0. one-time: register the seed corpora (definitions only, no source)
refcode-build add --from <skill>/seed/corpora.json

# 1. dry-run: see exactly what a full build would clone
refcode-build index --all --dry-run

# 2. build (clones are shallow; large repos dominate wall time)
refcode-build index --all

# 3. confirm + share
refcode-build stats
refcode-build dump --out refcode.dump.sql     # inspect/backup (large); NOT a git artifact
```

## DB + sharing

- DB: `${REFCODE_DB:-~/.refcode/refcode.db}` (one SQLite file; schema in the
  `refcode` skill's `references/refcode.sql`).
- Clone cache: `${REFCODE_REPOS:-~/.refcode/repos/<slug>}`.
- **Share the definition, never the index.** Commit the manifest
  (`seed/corpora.json`: url + 40-hex sha + licence + use_policy, a few KB,
  rebuildable byte-identical). The built index is a binary `.db` of tens of MB —
  a GitHub *release asset* at most, never in git.

## Adding a project

```bash
refcode-build index myproj https://github.com/owner/repo --sha <40hex> --licence MIT
```

- Pin the **full 40-char sha** (short hashes make `git fetch --depth 1` fail).
- `--licence` is required for honest sharing; a curated row (`refcode-build add`)
  outranks the heuristic classifier.
- Unmapped languages still get plain-text BM25; they just lose symbol extraction.

## Honesty notes

- `index --all` clones every registered corpus — read the `--dry-run` list first;
  ClickHouse/Elasticsearch/Lucene are GB-scale shallow clones.
- Extract quality varies by language: ~11 languages have real tree-sitter tags
  queries, the rest fall back to a generic `def`-node heuristic.
- A build is only "done" when `stats` shows the project's `symbols` > 0 (or you
  accept a legitimately empty one, e.g. a docs-only repo).
