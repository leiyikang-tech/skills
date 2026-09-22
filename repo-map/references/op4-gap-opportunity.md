# Op4 — Gap & Opportunity Analysis (unified demand board)

Goal: find (1) what this project **CANNOT satisfy** (gaps) and (2) whether
multiple concepts **cross-pollinate into new technologies** (opportunities)
— then persist both to a **single unified demand board** so every future
analysis continuously tracks them and **who needs them**. This is the
operation that makes analysis accumulate instead of evaporate.

Grounded in real sessions: the `KnowledgeGap` / `Opportunity` dataclasses
(an internal finance-core module), the project spec (Part 3 trend engine +
Part 4 knowledge-gap awareness), and persisted gap docs.

Read this file when Op4 starts.

---

## 0. Bin by the taxonomy (deterministic aggregation)

**Before** detecting/persisting any gap or opportunity, classify the project's
**Axis A primary paradigm** (`references/taxonomy/KNOWLEDGE-TAXONOMY.md`) — the
same id already assigned in Op3.1. This id is the **aggregation bin**:

- `project_open_items.domain` = **A-paradigm id** (A1–A12), not a free-form topic.
- The reuse loop (§5) reads the *bin's* existing items first, then checks whether
  THIS project fills/extends them — same-paradigm accumulation is what makes
  analysis compound instead of scatter.

Why: without the taxonomy, demands from a dozen projects land in 12 unrelated
buckets and never aggregate. With it, all demands on, say, retrieval-enhancement
(A2) form one evolving picture. Never persist with a free-form domain — always
the A-paradigm id (optionally + secondary ids).

---

## Two real modes (choose by target)

### Mode A — External / competitive gap survey
"what does the current tooling landscape NOT cover" (patent tools, memory
systems, agent harnesses). Workflow, from real sessions:
```
websearch_web_search_exa  (multiple, parallel — landscape sweep)
→ webfetch / grep_app_searchGitHub  (per-claim code/doc-level evidence)
→ ctx_reduce  (drop consumed outputs, keep lean)
→ aeterna_memory_add  (persist findings; often mid-flight, not just at end)
```
Use when the question is "compared to X, what's missing / what hole exists".

### Mode B — Self-repo gap audit
"what does THIS project fail to deliver". Real artifact
(`implementation-gap-analysis.md`): build a
`方向(component) × {服务层/测试/模型迁移/集成wiring/前端}` table with ✅/⚠️/❌,
then a numbered 缺口(未完成) list — each gap = `{component, 定位(where),
原因(why missing), 改进建议(action)}`. Authentik doc adds gap-confirmed(✅/❌) +
root-cause deviation + 路标 A/B + decision matrix.

---

## Gap analysis — the record to produce

Inherit the real `KnowledgeGap` dataclass fields + your required ones:

```
GAP RECORD (persist to shared store)
  id                — stable unique id (gap_<project>_<n>)
  kind              — 'gap'
  domain            ← A-paradigm id (the aggregation bin)
  gap_type          — factual | procedural | conditional | structural | unknown_unknown
  description       ← APP. SCENARIO context (what scenario can't be met)
  severity          0-1
  demand_weight     0-1   (how much it matters)
  fill_progress     0-1   (0.0 → 1.0 as it gets filled across projects)
  priority          = severity × demand_weight × (1 - fill_progress)   ← the sort key
  originating_project ← which analysis surfaced it
  suggested_sources / last_attempted — where to look next
  discovered_at / tags
```

Gap detection is 5-layer (from an internal gap_detector module):
**Identify → Classify(gap_type) → Prioritize(demand-weighted) → Fill(inject +
track progress) → Identify unknown-unknowns** (DSP / DK + UUB).

## Opportunity analysis — cross-pollination → new concepts

A single project's features rarely reveal opportunity. Opportunity = **multiple
analyses cross-pollinating into a systemic signal none alone shows.** Inherit
the real `Opportunity` dataclass + scanner (`opportunity_scanner.py`):

```
OPPORTUNITY RECORD (persist to shared store)
  kind              — 'opp'
  type              — industry_convergence | style_convergence |
                      macro_micro_align | contrarian_cluster
  direction         — bullish | bearish | neutral   (how "forwardable" it is)
  confidence        0-1
  description       ← APP. SCENARIO (the new capability/scenario this spawns)
  contributingProjects []   ← which projects/analyses crossed to form it
  domain / tags
  discovered_at
```

Cross-pollination detector = occurrence-count over converging evidence with a
convergence threshold (real code uses `MIN_CONVERGENCE_COUNT = 3`): when ≥N
independent analyses point at the same emergent direction, promote it from
"observation" to "opportunity / new concept". Adapt: `_scan_industry_convergence`,
`_scan_style_convergence`, `_scan_macro_micro_alignment`, `_scan_valuation_clusters`.
For repo analysis these become: same mechanism appearing across projects,
complementary tools that compose, a pattern extending to a new domain.

---

## The unified demand board

**One table replaces the old separate `project_gaps` + `project_opportunities`.**

Schema: `project_open_items` (see `op4_analysis_store.sql`).
Key columns:

| Column | Meaning |
|--------|---------|
| `item_id` | `gap_<project>_<n>` / `opp_<project>_<n>` |
| `kind` | `gap` / `opp` |
| `domain` | A-paradigm id (the aggregation bin) |
| `priority` | sort key (gap: sev×dw×(1-fill); opp: confidence) |
| `needer` | **WHO needs it** — the project/domain that will consume this (see §5) |
| `status` | `discovered` → `analyzing` → `filled` / `skipped` / `closed` |
| `scheduled_at` | **when analysis is planned** ("when will it be analyzed") |
| `analyzed_at` | when analysis actually started |
| `filled_by_project` | which project filled it |
| `filled_at` | when it was filled |
| `fill_progress` | 0-1; replaces old `progress` |
| `extra` | JSON: gap-specific (gap_type, severity, demand_weight) or opp-specific (type, direction, confidence) |

Status machine:
```
discovered → analyzing → filled | skipped | closed
```

---

## 5. Claim-and-track protocol (the reuse loop that makes it a KNOWLEDGE CLOSED-LOOP)

This is the mechanism behind "持续关注" and "谁需要什么样的缺口/机会":

### Before analysis (every new run) — READ + CLAIM
```
SELECT * FROM project_open_items
 WHERE domain = '<this project's A-paradigm>'
   AND status = 'discovered'
 ORDER BY priority DESC LIMIT N;
```
For each claimed item, **claim it** (UPDATE):
```
UPDATE project_open_items
   SET status = 'analyzing',
       needer = '<current project>',
       scheduled_at = '<now>',
       analyzed_at = NULL
 WHERE item_id = '<item>';
```
This answers **"who needs this"** (needer = current project) and
**"when will it be analyzed"** (scheduled_at = now). A claimed item is
now being worked by a specific consumer — it is no longer an orphan.

### After analysis — FILL or CLOSE
For each gap/opportunity that THIS analysis addresses:
- **Filled** (real mechanism found):
  ```
  UPDATE project_open_items
     SET status = 'filled',
         fill_progress = 1.0,
         filled_by_project = '<current project>',
         filled_at = '<now>'
   WHERE item_id = '<item>';
  ```
- **Partially filled** (progress rose, not complete):
  ```
  UPDATE project_open_items
     SET fill_progress = <new value>,
         status = 'analyzing'   (still open, keep working)
   WHERE item_id = '<item>';
  ```
- **Not relevant / no mechanism** → `status = 'skipped'` (analyzed, confirmed no gap).

### New gap/opportunity discovered in THIS run → INSERT
```
INSERT INTO project_open_items (item_id, kind, domain, description, priority,
  status, discovered_at, tags, originating_project, extra)
VALUES ('gap_<project>_<n>', 'gap', '<A-id>', '...', <priority>,
  'discovered', '<now>', '...', '<current project>',
  '{"gap_type":"...","severity":...,"demand_weight":...}');
```

### The closed-loop invariant
Every future `repo-map` run of any repo in this paradigm:
1. **Reads** `project_open_items WHERE domain=? AND status='discovered'` — surfaces
   previously-recorded demands ("持续关注").
2. **Claims** them (needer = this project) — now "who needs" is tracked.
3. **Fills** what it can, **appends** what it finds.

Analysis compounds across projects because the board is shared and each
run claims/pushes progress — not because "I remember analyzing this before".

---

## Persist to the shared analysis DB (canonical)
The shared analysis database `{{ANALYSIS_DB}}` is the durable
registry. Schema in `op4_analysis_store.sql` — one unified `project_open_items`
table (no separate gap/opp tables). Apply with:
```
sqlite3 {{ANALYSIS_DB}} < op4_analysis_store.sql
```

> **CANONICAL DB CONVENTION (fix applied 2026-09):** All repo-map *board* tables —
> `analysis_index`, `project_open_items`, `project_paradigms`, `project_baselines`,
> and the `v_*` views — live in **`{{ANALYSIS_DB}}`** (HOME). The
> `{{ANALYSIS_DB}}` (WORK) DB is reserved for the doc/session
> catalog (`analysis_docs`, `sessions`, `session_events`) and is **NOT** the board
> registry. Earlier references pointed the board schema at the WORK path, which
> caused the waitlist/gap board to be written to the wrong DB. Always apply board
> schema + UPSERTs against `{{ANALYSIS_DB}}`.

For the reusable-atomic-capability register, reuse `aeterna.knowledge_propose`
(pattern | reference) so gap-backed capabilities surface via governance.

---

## Guardrails

- **Filter template/system noise** before treating a user message as a real
  trigger: strip `<system-reminder>`, `[analyze-mode]`, `[search-mode]`,
  `<compartment…>` — only genuine user prompts are evidence.
- **Don't persist a gap you can't cite** — a gap claim needs the source
  (competitor landscape / self-audit table / code path). Uncited gap = marketing
  fluff again (same anti-hallucination discipline as Op3).
- **opportunity ≠ aggregation** — an opportunity is a *derived* signal (crossing
  ≥3 converging independent analyses), not a summary of one project's features.
- **track fill_progress honestly** — a gap's progress only rises when a later
  project demonstrably fills it. Don't assert closure; update from evidence.
- **claim before analyze** — every item you work on should have `needer` set and
  `status='analyzing'`. Don't leave orphans as `discovered` without a consumer.

## Deliverables
- `project_open_items` rows (unified demand board) in the shared analysis DB.
- `缺口分析/<项目>的缺口和机会分析.md` in the work-log knowledge repo
  （**专用目录** `缺口分析/`，统一观察和对比；→ Op5 uploads it）。
- Reusability proof: this run *claimed* N existing items (with needer set) and
  *filled/closed* M, and *added* K new ones (list them).
