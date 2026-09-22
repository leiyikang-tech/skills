# Incremental Analysis Protocol (项目刷新 + 核心领域新增)

Read this **before** starting any repo-map run to decide which baseline mode
applies. It answers: *am I analyzing fresh, refreshing a mapped project, or
adding to a known domain?* Modes differ in what counts as "known" and therefore
what work is *delta* vs *full*.

Two baseline modes (they can combine):

| Mode | Baseline is | Trigger | What's delta |
|------|-------------|---------|--------------|
| **Fresh** | nothing | first analysis of a path | everything (full 5-op) |
| **Refresh** | this project's last-analyzed git state | project already mapped + re-run | the git diff since last-mapped sha |
| **Same-domain** | the A-paradigm bin's existing assets | new project lands on an existing paradigm (A1–A12 with prior analyses) | alignment to the bin (competitors/papers/gaps already known) |

`Refresh` and `Same-domain` share one rule that defines the whole protocol:
**search the delta against your baseline, never re-scan the whole landscape.**
The taxonomy (`references/taxonomy/KNOWLEDGE-TAXONOMY.md`) is what makes a
"delta" well-defined: Refresh diffs against the *project*, Same-domain diffs
against the *paradigm bin* — both are deterministic now.

---

## 0. Baseline detection (do this first, every run)

```bash
# 1) Was this repo mapped before? -> project_baselines row exists?
python3 - <<'PY'
import sqlite3, os
db=os.path.expanduser("{{ANALYSIS_DB}}")
con=sqlite3.connect(db)
path=os.path.abspath(sys.argv[1] if len(sys.argv)>1 else ".")
r=con.execute("SELECT last_analyzed_sha, paradigm_id, mapped_at FROM project_baselines WHERE repo_path=?",(path,)).fetchone()
print("baseline:", r if r else "NONE -> Fresh")
PY
# 2) If baselined: how much changed since?
git -C <repo> log -1 --format=%H              # current HEAD
git -C <repo> diff --stat <last_analyzed_sha>..HEAD  # the delta
```

Classification (deterministic):
- No `project_baselines` row → **Fresh** (full 5-op).
- Row exists AND `git diff` non-empty → **Refresh** (delta Op1/Op2/Op4; Op3 re-check).
- Row exists AND no diff (unchanged) → **no-op** — tell user nothing changed, skip work.
- (either of the above) AND the A-paradigm has prior analyses in its bin →
  ALSO qualifies as **Same-domain** where bin assets define the Op3 baseline.

---

## 1. Refresh mode — project-version delta (git-diff driven)

Goal: update a mapped project for what **changed since last analysis**, without
re-discovering/re-generating the whole thing. Only the delta is analyzed; the
map's stable parts stay untouched.

### 1.1 Compute the delta
```bash
git -C <repo> diff --name-status <last_sha>..HEAD      # M/A/D/R per file
git -C <repo> diff --stat  <last_sha>..HEAD            # size signal
git -C <repo> log --oneline <last_sha>..HEAD           # what was done
```
Changes that matter → **Op1 delta scope**:
- `A` (added) new module / new language / new entrypoint → score + doc IF distinct domain
- `M` (modified) touched existing dir → re-verify that dir's AGENTS.md still true, **edit** only the stale lines
- `D` (deleted) removed module → **remove** its per-dir AGENTS.md (or fold to parent)
- `R` (renamed) → update the doc's header path, keep body
- dependency/stack change (package.json/pyproject/deps add/remove) → re-run G2 detect_stack + G5

### 1.2 Op1 delta mechanics (do NOT rerun discovery/scoring/generate wholesale)
1. **scope** = dirs/files in the diff only; read those entrypoints + configs, spawn
   explore agents ONLY for the touched clumps (dynamic-scale per delta size, not repo size).
2. **edit, don't rewrite**: `edit` the affected AGENTS.md; unchanged docs untouched.
   Update the `Generated | Commit` header to the new sha.
3. Re-run G1–G5 (cheap file checks) to re-certify the whole map still holds.
4. If the delta changes the verdicts (new deps, new entrypoint, different stack):
   re-verify and record it.

### 1.3 Re-classify paradigm (A-axis can drift)
The diff may move the project to a new/additional paradigm (e.g. it gained a
search feature → A1 → A1+A2). Re-run the §3.1 taxonomy classification on the
**delta**; update `project_baselines.paradigm_id` if it changed.

### 1.4 Op2 ~ Op5 on refresh
- **Op2**: regenerate only the sections affected by the delta (new core fns /
  scenarios / limits); keep stable claims.
- **Op3**: do NOT re-benchmark the whole landscape. Check only: did the delta
  add a new capability worth comparing? Same-domain bin handles deep compare.
- **Op4**: the diff may **fill a previously-recorded gap** → bump that gap's
  `progress` 0→1. It may add a new gap → append. This is how the closed loop
  actually turns.
- **Op5**: persist the delta as an *update* to the existing distinctive-named
  file (one subject = one file; edit in place, re-push), plus any new assets.

### 1.5 Update the baseline
```sql
UPDATE project_baselines SET last_analyzed_sha=<new HEAD>, paradigm_id=?, mapped_at=now WHERE repo_path=?;
```

---

## 2. Same-domain mode — paradigm-bin delta (reuse, don't rescan)

Goal: analyze a new project that sits in a paradigm (A1–A12) we already know.
The bin's **existing assets are the baseline** — competitors, papers, domain
surveys, gap progress. We only locate this project's *difference* within the
bin, then fold its findings back in.

### 2.1 Assemble the bin baseline (WHAT to reuse — this is the speed win)
```sql
-- known competitors / comparisons in this bin
SELECT name_zh, dispatch FROM project_paradigms WHERE paradigm_id=<A>;
-- gaps & opportunities already tracked in this bin
SELECT kind,id,description,progress FROM v_op4_open_items WHERE domain=<A>;
```
Plus: prior work-log competitive analyses in the bin (Axis D residence dirs) and
the bin's `capabilities.md` rows. **This is your starting search surface** — you
do not re-discover it.

### 2.2 Locate the delta (what's NEW vs the bin)
Only three questions; everything else is already known:
1. **New mechanism?** Does this project add a bottom-layer mechanism the bin
   hasn't catalogued? (→ new capability row, possible taxonomy-extension if a
   genuine new paradigm)
2. **Fills a tracked gap?** Does it solve a `project_gaps` row in this bin →
   bump that gap's `progress`.
3. **Differentiates how?** vs the bin's already-compared competitors — a NEW row
   in the existing comparison matrix, not a full re-survey (10-dim template
   applies only to the new entrant vs the bin's leaders, not vs every prior tool).

### 2.3 Anti-hallucination + reuse guard
- Only the delta claims are NEW; inherited bin claims stay attributed to the bin,
  not re-verified ad nauseam.
- If the project is a me-too (no new mechanism, fills nothing, doesn't
  differentiate) → say so plainly; don't fabricate differentiation to justify
  another report.

### 2.4 Close the loop
- Append the new capability/mechanism to the bin's `capabilities.md` + Op4 store.
- Op5: persist one distinctive file in the bin's residence dir
  (`<domain>/<subject>作为<role>的<analysis-type>.md`).
- Update `project_baselines` for this project.

---

## 3. Combining the modes (refresh of a known-domain project)

A project already mapped that also belongs to a known bin → both apply:
- **Refresh** handles the project-version delta (1.1–1.5).
- **Same-domain** handles bin-alignment for any NEW capability the refresh
  surfaced in 1.4 (2.2–2.4).
Run Refresh first, then Same-domain on the resulting new-capability set.

---

## 4. Baseline store (analysis.db `project_baselines`)

New table (apply with `references/taxonomy/incremental.sql`):
```sql
CREATE TABLE IF NOT EXISTS project_baselines (
  repo_path        TEXT PRIMARY KEY,
  last_analyzed_sha TEXT,          -- git HEAD the map was generated at
  paradigm_id      TEXT,           -- A1..A12 primary (axis A)
  artifacts        TEXT,           -- json: {root_kb, dirs[], profile, comparison}
  mapped_at        TEXT            -- ISO timestamp
);
```
Holds the "what do I already know about THIS project" state that Refresh diffs
against. Written after every successful analysis; read at every run start.