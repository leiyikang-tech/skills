---
name: awesome-map
description: Analyze an awesome-list's member projects AND papers — parse + score + rank ALL entries by analysis value, enqueue into the waitlist, then auto deep-dive in rank order. Loads repo-map's awesome-list mode.
version: "1.0"
---

# awesome-map — waitlist + on-demand analysis of an awesome list's member projects

**awesome-map is a thin orchestrator over repo-map's awesome-list mode.** It
calls **repo-map's awesome-list branch** (SKILL.md §awesome-list mode) — no
duplicate logic. It exists as its own skill so a user can invoke just the
awesome-list analysis without running the full repo-map 5-op pipeline.

The TARGET is the awesome list's **member projects**, NOT the list README itself.

> Requires the **repo-map** skill to be installed (it supplies the harness,
> references, and the Op1–Op5 pipeline that awesome-map drives). Install
> `repo-map` from this repo first (`bash repo-map/install.sh`), then this skill
> can reference `{{REPO_MAP_HOME}}/SKILL.md §awesome-list mode`.

## Flow

1. **Parse all**: extract ALL member projects AND papers from the README
   (title, URL, category, stars, description, source_type, vendor).
2. **Score + rank ALL (automatic)**: every entry gets a `value_score` via
   `value = .35*gap_fill + .20*paradigm_relevance + .25*novelty + .15*atomic_value + .05*maintenance`.
   `gap_fill` = fills an unfilled `project_open_items` item; `novelty` = differs
   from the already-analyzed docs; `atomic_value` = real bottom-layer mechanism vs
   link-collection. **stars is a TIEBREAKER, never the sort key.** Consistency:
   ranking reads a frozen gap-board snapshot (never writes it) + deterministic
   rule-scoring → reproducible, order-independent.
3. **UPSERT ranked results**: every entry into `analysis_index` with
   `status='waitlisted'`, recording `source_type` (github/arxiv/blog),
   `core_functions` + `why_worth` + `value_score` + 5 component scores.
   Idempotent.
4. **Auto deep-dive in rank order**: iterate `waitlisted` by `value_score DESC`,
   each entry automatically (optionally capped to top N / value threshold),
   branching on `source_type`:
   - `github` → clone to `{{REPOS_DIR}}/<org>/<repo>/` (persistent full clone)
     → standard repo-map pipeline (Op1 → Op2 → Op3 → Op4 → Op5)
   - `arxiv`/`blog` → **paper analysis** (op1-init-deep.md 分支 B): ALL papers
     are surface-analyzed — webfetch abstract → extract core mechanism → map
     paradigm → score → ingest (waitlist is a REGISTRATION state, NOT
     "skipped-unread"; every paper must complete surface analysis). deep-dive
     only papers that are high-value OR fill an open `project_open_items` gap OR
     hit a surprise signal (novel mechanism / cross-paradigm / high influence /
     unique method). Set status='analyzed' + analysis_path + n_gaps +
     n_opportunities after each. **This phase may write the gap board**; the
     ranking phase never does.
5. **Sync to GitHub**: after enqueueing the ranked results and/or after each
   deep-dive: `git add -A && git commit && git push` to sync `analysis_index` +
   analysis artifacts to the knowledge repo.

## Mechanics to read

- `{{REPO_MAP_HOME}}/references/op1-init-deep.md` §awesome-list mode + §从 waitlist 拉取后如何分析
- `{{REPO_MAP_HOME}}/references/op5-persist.md` §Analysis index sync
- `{{REPO_MAP_HOME}}/references/waitlist.sql` (waitlist schema),
  `{{REPO_MAP_HOME}}/references/analysis_index.sql` (board)

## Completion signal

Every finished stage prints a loud marker carrying its Q-gate verdict; the run
ALWAYS ends with a completion block — **success and failure alike**:
`═══ awesome-map 完成 ═══ result: SUCCESS/PARTIAL/FAILED/ABORTED · 解析<N>条(项目/论文) ·
已入 waitlist <N> · 已深挖 <N> · 已推送 <names>` … A run is only complete when
that block is printed; a stage that can't pass its Q-gate records FAILED and
forces the report — never a silent stop.