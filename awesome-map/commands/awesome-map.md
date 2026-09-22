---
description: Analyze an awesome-list's member projects AND papers — score + rank all entries by analysis value, enqueue into the waitlist, then auto deep-dive in rank order
argument-hint: [<path-to-awesome-list-README>]  (defaults to the current working directory)
---

<command-instruction>
# awesome-map — waitlist + on-demand analysis of an awesome list's member projects

Calls **repo-map's awesome-list branch** (SKILL.md §awesome-list mode). No
duplicate logic. The TARGET is the awesome list's **member projects**, NOT the
list README itself.

## Flow

1. **Parse all**: extract ALL member projects AND papers from the README
   (title, URL, category, stars, description, source_type, vendor).
2. **Score + rank ALL (automatic)**: every entry gets a `value_score` via
   `value = .35*gap_fill + .20*paradigm_relevance + .25*novelty + .15*atomic_value + .05*maintenance`.
   `gap_fill` = fills an unfilled `project_open_items` item (73 gap + 29 opp
   open, concentrated in A1/A10/A12/A3/A7); `novelty` = differs from the ~545
   already-analyzed docs (247 repos/631 papers); `atomic_value` = real bottom-layer
   mechanism vs link-collection. stars is a TIEBREAKER, never the sort key.
   **Consistency**: ranking reads a frozen gap-board snapshot (never writes it) +
   deterministic rule-scoring → reproducible, order-independent.
3. **UPSERT ranked results**: every entry into `analysis_index` with
   status='waitlisted', recording `source_type` (github/arxiv/blog),
   `core_functions` (awesome/README description + paper abstract one-liner) +
   `why_worth` + `value_score` + 5 component scores. Idempotent.
4. **Auto deep-dive in rank order**: iterate `waitlisted` by `value_score DESC`,
   each entry automatically (optionally capped to top N / value threshold),
   branching on `source_type`:
   - `github` → clone to `{{REPOS_DIR}}/<org>/<repo>/` (persistent
     full clone) → standard repo-map pipeline (Op1 → Op2 → Op3 → Op4 → Op5)
   - `arxiv`/`blog` → **paper analysis** (op1-init-deep.md 分支 B): ALL papers are
     surface-analyzed — webfetch abstract → extract core mechanism → map paradigm
     → score → ingest (waitlist is a REGISTRATION state, NOT "skipped-unread";
     every paper must complete surface analysis). deep-dive only papers that are
     high-value OR fill an open `project_open_items` gap OR hit a surprise signal
     (novel mechanism / cross-paradigm / high influence / unique method)
   → set status='analyzed' + analysis_path + n_gaps + n_opportunities after each.
   This phase may write the gap board; the ranking phase never does.
5. **Sync to GitHub**: after enqueueing the ranked results and/or after each
   deep-dive: `git add -A && git commit && git push` to sync `analysis_index`
   + analysis artifacts to the work-log repo.

**Completion signal (hardened — same contract as repo-map):** every finished
stage prints a loud marker carrying its Q-gate verdict; the run ALWAYS ends with
a completion block — **success and failure alike**:
`═══ awesome-map 完成 ═══ result: SUCCESS/PARTIAL/FAILED/ABORTED · 解析<N>条(项目/论文) ·
已入 waitlist <N> · 已深挖 <N> · 已推送 <names> · 分类归属:<paradigm (A1–A12)>
· 应用建议:<三要素摘要+指针> · 操作建议:<决策标签行动结论>`（分类归属取成员项目映射到的 paradigm；应用建议三要素
以摘要+指针给出，指向完整载体：生态地图→landscape 文档、生态位置→单项目分析文档、
关键缺口→缺口分析/<project>的缺口和机会分析.md；不在报告内重复生态全景全文；
写"暂无明确适用场景"而非省略三要素）. 操作建议 = 决策导向行动结论（直接给人看，
非项目分析）：✅直接用/⚠️评估后用/🕐跟踪/🔴风险/❌暂不采用 + 可执行动作，完整论证在
Op2 九 战略/选型建议；无明确建议写"建议仅跟踪，暂不引入". A run is only complete when that
block is printed; a stage that can't pass its Q-gate records FAILED and forces the
report — never a silent stop. Do not end on silence or a vague trailing sentence.

Read `references/op1-init-deep.md` §awesome-list mode + §从 waitlist 拉取后如何分析
and `references/op5-persist.md` §Analysis index sync for mechanics.
`references/waitlist.sql` for the waitlist schema, `references/analysis_index.sql` for the board.

Do NOT echo the embedded PAT token in output, prompts, or logs.
</command-instruction>