---
name: repo-map
description: |
  Complete new open-source project analysis — a 5-operation pipeline that mirrors
  how senior agents actually dissect an unfamiliar repo. Op1 = init-deep: generate
  hierarchical AGENTS.md knowledge base (structure/conventions/entrypoints/anti-patterns),
  gated by a deterministic file-system harness. Op2 = project profile: core function
  list + application scenarios + core highlights/advantages (product-level view).
  Op3 = iterative comparative research: classify the project's nature, run competitive
  analysis (high-similarity repos), deep paper analysis for capability/key-technique
  projects, domain-knowledge survey, and distill reusable atomic capabilities —
  with hard anti-hallucination (strip marketing fluff to bottom-layer mechanisms +
  paper backing) and horizontal/vertical comparison for true differentiation.
  Op4 = gap & opportunity analysis: find what the project CANNOT satisfy (gaps) and
  whether concepts cross-pollinate into new technologies (opportunities), persisted to a
  shared store so future analyses continuously track them. Op5 = knowledge asset
  persistence: index every artifact under a distinctive name into the shared GitHub
  knowledge repo ({{KNOWLEDGE_REPO_URL}}).
  Use when the user points at a repo/directory they have never analyzed and wants a
  thorough understanding, or explicitly asks for /init-deep, a project profile /
  核心功能 / 应用场景 / 核心亮点, or a competitive / paper-backed analysis.
  Triggers: 'analyze this repo', 'map this repo', 'repo-map', '/repo-map',
  'understand a new open-source project', '核心功能', '应用场景', '核心亮点',
  '竞品分析', '和 X 对比', '/init-deep'.
type: autonomous-repo-analysis
category: writing
model: jasolar/DeepSeek-V4-Flash-0731
allowedTools:
  - task
  - bash
  - read
  - glob
  - grep
  - ast_grep_search
  - lsp_symbols
  - background_output
  - background_cancel
  - todowrite
  - write
  - edit
likelyInvocations: 5
autoInvoke: false
metadata:
  harness: {{REPO_MAP_HOME}}/harness
  version: "3.4"
---

# repo-map

Five-operation pipeline for analyzing a **new open-source project**. Each
operation answers a different question; they compose into a complete,
accumulating understanding. You are the **orchestrator** — you spawn subagents
for heavy work, you do not rebuild/implement the target yourself. Gates decide
progress.

**awesome-list mode**: when the target is a curated awesome list
(`- [Title](URL)` bullet entries, no code structure), the goal is NOT to
analyze the list itself but its **member projects AND papers**: parse all →
**score + rank every entry by analysis value** (value_score) → **enqueue all into
the waitlist** (`analysis_index` status='waitlisted') recording each entry's
**core functions** → **auto deep-dive in rank order** (github → clone + Op1-Op5;
arxiv/blog → gap-paper deep-analysis). See §awesome-list mode below.

```
Op1  /init-deep       What is its STRUCTURE?   → hierarchical AGENTS.md
     awesome-list     Which members are WORTH analyzing? → parse + score + rank ALL + waitlist + auto deep-dive
Op2  Profile          What does it DO?         → core fns + scenarios + highlights
     awesome-list     How COVERED is it?       → coverage map (entries/domains/stars)
Op3  Comparative      How does it RELATE?      → competitors/papers/domain + atomic capabilities
     awesome-list     How does it COMPARE?     → vs other awesome lists
Op4  Gap/Opportunity  What is MISSING / what's NEXT? → gaps + cross-pollination opportunities (→ shared store)
Op5  Persist          Where does it LIVE?      → distinctive-named indexable assets (→ GitHub knowledge repo)
     awesome-list     Index + sync           → analysis_index updated + pushed to GitHub
```

Read each operation's playbook (`references/op1-init-deep.md`,
`references/op2-profile.md`, `references/op3-research.md`,
`references/op4-gap-opportunity.md`, `references/op5-persist.md`) only when that
operation starts. Read the **deterministic classification schema**
(`references/taxonomy/KNOWLEDGE-TAXONOMY.md` + `DISPATCH.md` + `capabilities.md`)
**before** Op3 and Op4 — it routes every project to the right search plan and
gap/opportunity bin. Read `references/incremental.md` **before Op1 on every
run** to classify Fresh / Refresh / Same-domain and decide the delta scope.
Awesome-list mode's shared board lives in `references/analysis_index.sql`
(project index + waitlist) and `references/waitlist.sql` (waitlist extension).
deep-dive mode's two-ontology schema + grounding contract lives in
`references/deepdive.sql` (6 tables + v_dd_convergence view) and
`references/deepdive.md` (the deep-dive playbook).

**Harness:** `gates.py` (G1–G5, file-system quality) drives **Op1** (→ Q1).
`depth_check.py` (deterministic `path:LINE` anchor gate) drives **Op2/Op3** (→ Q2/Q3),
so a capability claim without a resolvable source anchor is structurally rejected —
no LLM judgment in the verdict. Op2/Op3 also keep their playbook-level gates
(anti-hallucination + differentiation) for semantic truth. Every op's gate is
surfaced through the unified **Quality gates Q1–Q5** contract below — no op is
ungated. **awesome-list mode reuses the same harness** but G1 (analyzable) is the
only relevant gate (README exists + has content); G3/G4 (AGENTS.md/doc checks) are
skipped.

### Quality gates Q1–Q5 — every op gets a hard, verdict-producing gate

**Every operation ends with a gate that MUST produce a verdict (PASS/FAIL).** A
run is not allowed to drift to a vague "looks done" — each op has an explicit,
decidable PASS condition; the completion report (below) is only produced by the
hard gate chain. This unifies the pipeline: Op1 keeps its scripted G1–G5, and
Op2–Op5 gain the same contract (decidable PASS condition + attempt budget +
failure visibility) that Op1 already has.

| Op | Gate | PASS condition (decidable) |
|----|------|-----------------------------|
| **Q1** (structure) | `gates.py` G1–G5 (standard) / G1 only (awesome) | AGENTS.md / awesome entries parsed & scored; gate verdict PASS or SKIP(G5, recorded) |
| **Q2** (profile) | `depth_check.py` (mechanical) | PROFILE.md produced; **`depth_check.py --min-anchors 5` PASS** — every claimed core function has a resolvable `file:LINE` anchor, no unanchored mechanism claim |
| **Q3** (compare) | `depth_check.py` (mechanical) | comparative doc + ATOMIC-CAPABILITIES.md produced; **`depth_check.py --min-anchors 3` PASS** — ≥1 EXTRACTED bottom-layer capability, each `file:LINE` anchor resolves, paper/vendor URLs resolve via `citation_check.py` |
| **Q4** (gap/opp) | board gate | gap/opportunity findings written to `project_open_items` (≥1 item) **or** explicit "no new gaps" verdict recorded |
| **Q5** (persist) | push gate | asset copied into work-log + `git commit` + `git push` **all succeeded** |

**Gate protocol (every op, identical):**
1. At the end of each op, evaluate its Q-gate PASS condition against the actual
   artifact (not the intent). No artifact → FAIL.
2. FAIL → rework the op (attempt budget **3**). On exhaust → **Oracle once** →
   if still FAIL, mark that op's gate FAILED and **continue to the completion
   report** (do not loop forever).
3. A FAILED op gate does NOT silently end the run — it forces a **PARTIAL/FAILED**
   completion report (see below). The report is the only "done" signal.

> **Rationale:** previously only Op1 had a scripted gate; Op2–Op5 were soft rules
> that an agent could bypass without being caught, so a run could end (or stall)
> with no gate verdict and no report. Q1–Q5 gives every op a decidable PASS +
> budget + forced-report fallback, so no op can end silently.

---

## Decision tree

```
User points at a repo/dir
├─ **is an awesome-list** (大量 `- [Title](URL)` 链接 / 无代码结构)
│   → awesome mode: 解析列表 → 排序评估 → 纳入 waitlist（记录核心功能+理由）→
│     展示 waitlist → 需要时从 waitlist 拉取→clone→标准 Op1-Op5 分析 → push GitHub
├─ asks "why / how / what does it look like"          → Op1 first (structure is the base)
├─ asks "what does it do / featured / who's it for"    → Op2
├─ asks "how does it compare / vs X / is it any good"  → Op3
├─ asks "缺口 / 机会 / what's missing / cross-pollination" → Op4 (and read the shared gap store)
├─ asks "persist / save / upload / 存到知识库"                → Op5
├─ asks "understand this project" / "/repo-map"               → Op1 → Op2 → Op3 → Op4 → Op5 (full run)
├─ **高价值项目/方向值得深入分析** / `/deep-dive <path>`      → **deep-dive mode** (两本体 + 外部锚定, see below)
├─ **re-analyze a MAPPED project / refresh / 增量更新**        → **Refresh mode** (diff-driven delta, see below)
└─ **same paradigm as a known domain / 新增同领域项目**        → **Same-domain mode** (bin-reuse delta, see below)
```

Defaults: a bare `/repo-map <path>` runs the **full 5-op chain**. A user who
names one operation gets that operation. In a full run, Op4 first **reads** the
shared gap/opportunity store (does this repo fill/seed anything?) then writes
new findings, and Op5 persists every asset. That closes the loop: analysis
accumulates across projects.

### awesome-list mode — detection and flow

**Detection**: the target README contains a large number of `- [Title](URL)`
bullet entries (typically 50+) grouped under `##`/`###` category anchors,
with no code manifests (no package.json/Cargo.toml/go.mod). A single
`- [Title](URL)` link count ≥ 50 is the heuristic threshold.

**Target is the member projects, not the list.** In awesome mode, `Op1` maps to
*curation of the list's members*, and the real deliverable is a set of
recommended projects that each get analyzed with the standard Op1–Op5 pipeline.

**Flow** (per awesome-list target):
1. **Parse all**: extract ALL member projects AND papers from the README
   (title, URL, category, stars, description, source_type, vendor).
2. **Score + rank ALL (automatic)**: score every entry with the **analysis-value
   formula** (op1-init-deep.md Phase 2):
   `value = .35*gap_fill + .20*paradigm_relevance + .25*novelty + .15*atomic_value + .05*maintenance`.
   **stars is a tiebreaker, NOT the sort key.** `gap_fill` = fills an unfilled
   `project_open_items` item; `novelty` = differs from the ~545 already-analyzed
   docs (247 repos/631 papers); `atomic_value` = real bottom-layer mechanism
   (vs link-collection marketing). **Consistency**: ranking phase reads a frozen
   gap-board snapshot (never writes it) + deterministic rule-scoring → ranking is
   reproducible and order-independent (see op1-init-deep.md 一致性保证).
3. **UPSERT ranked results** — every entry into `analysis_index` with
   `status='waitlisted'`, recording `source_type` (github/arxiv/blog),
   `core_functions` + `why_worth` + `value_score` + 5 component scores. Idempotent
   (re-run only refreshes scores). Analyzed entries keep status='analyzed'.
4. **Auto deep-dive in rank order** — iterate `waitlisted` by `value_score DESC`,
   **each entry automatically** (optionally capped to top N / value threshold):
   `github` → clone (`{{REPOS_DIR}}/<org>/<repo>/`, persistent full
   clone) → standard repo-map pipeline (Op1→Op5); `arxiv`/`blog` → **paper analysis** (op1-init-deep.md 分支 B — ALL papers are
   surface-analyzed: webfetch abstract → extract core mechanism → map paradigm →
   score → ingest; waitlist is a REGISTRATION state, NOT "skipped-unread" — every
   paper must complete surface analysis. deep-dive only papers that are high-value
   OR fill an open `project_open_items` gap OR hit a surprise signal — novel
   mechanism / cross-paradigm / high influence / unique method — so unexpected
   value isn't missed by known-gap bias). Set status='analyzed' +
   analysis_path + n_gaps + n_opportunities after each. **This phase may write the
   gap board** (gap-paper fills); the ranking phase never does.
5. **Sync to GitHub** — after enqueueing the waitlist and/or after each
   deep-dive: `git add -A && git commit && git push` to sync
   `analysis_index` + analysis artifacts to the work-log repo.

### deep-dive mode — 两本体 + 外部锚定的深入分析

**触发**：用户显式 `/deep-dive <项目|方向>`，或分析中发现值得深入的高价值
项目/方向。deep-dive 不是"再跑一次 Op1-Op5"，而是**把每个判定节点锚定到现实
依据**，消灭所有依赖"LLM 主观判断"的节点。目标是**构建并验证两本体**：
关键概念本体（`deepdive_concepts`）+ 思维本体（`deepdive_methods/findings/
errors`）。**每条写入本体的知识都必须有外部锚点**（Wikidata QID / URL 解析通过 /
真实代码符号 / 缺口板行）——无锚点 → 不信任 → 不入本体。

**外部锚定（替换主观判断）**：
- 概念 grounding：`harness/wikidata_ground.py` 把概念解析到 Wikidata QID。
  `grounded`/`partial` → 采纳；`not_found` → 标记待补；`hallucination`（过短/通用词）
  → **拒绝**（这是抓 LLM 幻觉的方式，非自报）。
- 引用验证：`harness/citation_check.py` URL 解析。`resolves`（200）才可信；
  `broken`/`not_found` → 剔除。findings 的 verified=1 仅当引用校验通过。
- 原子价值：`harness/atomic_score.py` 从真实 clone 代码符号计数得 v_atomic，
  替代 LLM 读描述判断营销 vs 机制。
- 收敛：`harness/convergence.py` SQL 判定（末层新概念/发现/缺口全 0 = 收敛）。
- 自我改进：`harness/regression_check.py` 要求 AFTER 错误复发率严格低于 BEFORE
  才算改进，否则不采纳。

**Flow**（详见 `references/deepdive.md`）：基线（Op1-Op5 + 两本体上下文）→ 逐层
深挖（每层四齿轮：概念探索→深搜补全→缺口确认→思维本体累积，全外部锚定）→ 收敛
判定 → 递归自我改进（回归验证）→ 完成报告。Board DB 加 6 表 + v_dd_convergence
视图（`references/deepdive.sql`，幂等可重放）。

### Runtime contract (project path, language, completion signal)

**Project path — never ask "what's the project dir".** Resolve it by hard
precedence, and NEVER stop to ask "confirm the project directory":

```
1. explicit <path> argument  → use it
2. else current working dir (cwd) → USE IT DIRECTLY. The user launched
   opencode from the project dir; cwd IS the project. Do not treat this as
   ambiguity. (This is the #1 source of the old "confirm project dir" prompt
   — eliminated.)
Only if cwd is itself a container that is NOT a single project (e.g. a
workspace root (a directory holding many repos)): pick the most likely
sub-project from evidence (git history / recent activity / closest package
manifest) as the recommended default and CONTINUE (Confirmation rule 1) —
do not block on it.
```

**Language — respond in Chinese.** Unless the user writes in another language,
all deliverable summaries, gate verdicts, and completion messages are in
Chinese (指令原文用中文时尤其如此). Keep code paths, taxonomy paradigm ids
(A1–A12), and table names in English.

**Completion signal — make "done" unmistakable.** Every operation that finishes
prints a loud one-line marker **carrying its Q-gate verdict**; a full run ALWAYS
ends with a completion block — **success AND failure alike**:

```
✓ Op1 完成 → AGENTS.md 层级写入 <paths>  gate: Q1 <PASS/FAIL>
✓ Op2 完成 → 画像 <paths>                  gate: Q2 <PASS/FAIL>
✓ Op3 完成 → 对比+原子能力 <paths>          gate: Q3 <PASS/FAIL>
✓ Op4 完成 → 缺口/机会已写入共享库 <n 条>   gate: Q4 <PASS/FAIL>
✓ Op5 完成 → 已持久化并推送 <names>         gate: Q5 <PASS/FAIL>

═══ repo-map 完成 ═══
result: <SUCCESS / PARTIAL / FAILED / ABORTED>
· 5 gate verdicts: Q1–Q5 (<PASS×N> / <FAIL×M>) · 无待确认项 · 产物路径
· 分类归属: <paradigm_id 名称 (A 轴 bin，来自 Op3 taxonomy 分类)>
· 应用建议: 生态地图→<landscape 文档路径> · 生态位置→<单项目分析文档 §七>
·           关键缺口→<缺口分析/<project>的缺口和机会分析.md>   (摘要+指针，见下)
· 操作建议: <✅直接用/⚠️评估后用/🕐跟踪/🔴风险/❌暂不采用 行动结论，直接给人看>
·（Refresh 模式则注明 diff 范围 · ABORTED 则注明失败 gate + 已尝试次数）
```

**分类归属与应用建议**：这两行是完成报告的一部分，每个 run 都要给出，不可省略。
- **分类归属**：从 Op3 的 taxonomy 分类结果取该项目的 paradigm（A1–A12 bin + 名称）。awesome-mode 则取该成员项目映射到的 paradigm。
- **应用建议（三要素，缺一不可）**：综合 Op2 核心功能 + Op3 comparative + Op4 缺口板，给出生态级的定位分析。**完成报告只放三要素摘要 + 指向各自完整载体的指针**（方案A：三要素拆开落位，完整内容在各载体文档，避免在报告内重复生态全景全文）：

  1. **生态地图** —— 该 paradigm 生态完整地图（基础设施→框架→应用→工具/数据集 分层 + 每层代表项目 + 演化谱系）。**载体**：独立 landscape 文档
     `<domain>/<paradigm>-landscape-<paradigm>生态全景-<YYYY>.md`（仅按需新建，见 op3；已有则引用）。来自 Op3 domain 全景 + taxonomy paradigm bin。
  2. **生态位置** —— 本项目处于生态哪一层、上下游/替代/互补是谁、成熟度与差异化。**载体**：本项目的单项目分析文档（Op2 §七 生态位置）。来自 Op2 核心功能 + Op3 横向对比。
  3. **关键缺口** —— 生态内未填缺口（`project_open_items` 该 paradigm 的 status!='filled'）+ 本项目能填哪个/填不了哪个。**载体**：`缺口分析/<project>的缺口和机会分析.md`（Op4 专用目录）。无缺口写"暂无已识别缺口"而非留空。

  报告内的三要素各用一行摘要（1-2 句）+ 载体路径，不重复完整内容。无生态信息则写
  "暂无明确适用场景"而非省略三要素结构。

- **操作建议（决策导向，直接给人看）**：这是完成报告里**面向使用者（人）的行动结论**，
  不是项目分析本身。与应用建议的分工：**应用建议**分析「这个项目在生态中是什么」，
  **操作建议**告诉决策者「人应该怎么做」。完整论证在 Op2 九「战略/选型建议」，报告里
  只给精炼行动结论。按决策标签组织（每个 run 至少给出 1 个主要标签）：
  ```
  ✅ 直接用   —— <最佳适用场景>（成熟度: vX.X / ⭐N / 测试✓）  来自 Op2 五·最佳 + 七 成熟度
  ⚠️ 评估后用 —— <需先评估的点: license/集成成本/依赖稳定性/能力是否够>
  🕐 跟踪     —— <等什么时机/哪类缺口补上再用>  来自 Op4 project_open_items 未填项
  🔴 风险     —— <短板/license 限制/维护风险/被替代可能>  来自 Op2 九 短板 + Op3 对比
  ❌ 暂不采用 —— <判死情况: 无真实机制/广告吹嘘/license 不可用>
  ```
  必须给**可执行动作**（怎么接入/什么场景用/什么时候用/注意什么），不是复述功能。
  没有明确建议就写"建议仅跟踪，暂不引入"而非留空。

**Hardened rules (A + C):**
- **SUCCESS** = Q1–Q5 all PASS.
- **PARTIAL** = ≥1 op completed but ≥1 Q-gate FAILED (budget exhausted).
- **FAILED/ABORTED** = a gate failed at budget exhaustion and Oracle couldn't
  recover, or the run aborted before completing — **still prints the block**,
  never a silent stop.
- The block is printed **regardless of outcome**. There is NO path where a run
  ends without printing it: a gate that can't pass does not loop forever — it
  records FAILED and forces the report. ABORTED is not a silent exit.

A run is ONLY complete when that block is printed. Silence or a vague trailing
sentence is not "done". If you catch yourself about to end a run without the
block, you have NOT finished — print it.

### Incremental modes (baseline detection — run before Op1 on ANY run)

Classify Fresh / Refresh / Same-domain first (`references/incremental.md`):

| Mode | Trigger | What's delta |
|------|---------|--------------|
| Fresh | no `project_baselines` row | everything — full 5-op |
| Refresh | baselined + `git diff` non-empty | the git diff since `last_analyzed_sha` (delta Op1/2/4) |
| Same-domain | paradigm bin (A1–A12) has prior analyses | alignment to the bin: existing competitors/papers/gaps define the Op3 baseline — **locate the NEW mechanism, don't rescan the landscape** |

Core rule shared by both incremental modes: **search the delta against your
baseline, never re-scan the whole landscape.** Refresh diffs against the
project's own last git state; Same-domain diffs against its paradigm bin's
existing assets. The taxonomy makes both "delta" well-defined.

Full mechanics: `references/incremental.md` + the bin/DISPATCH tables.

---

## Confirmation handling (runs in EVERY operation)

Every Op may hit a decision point mid-run. Resolve it by this fixed rule —
**never stall on a decision you can make, never auto-decide one you can't:**

1. **Has a recommended default?** — the evidence (code anchors, taxonomy bin,
   gap-store, prior analyses) supports one clearly-better branch → **auto-take
   the recommendation and continue**; record the decision + reason so the user
   can audit it later (note it in the run output / run.json).
2. **No recommendation / genuinely ambiguous** — both branches are defensible
   and evidence does not dominate → **STOP and ask the human**. Present the
   options + what each implies; on confirmation, **continue the remaining
   steps** (do not restart or abandon the run).
3. **Stdlib actions already authorized by the run are NOT confirmation points.**
   Op5 persistence is a **forced closing step**, never a question: the user
   launched `/repo-map`, which implicitly authorizes commit+push (→ GitHub
   work-log) once operations 1–5 complete. COMMIT AND PUSH WITHOUT ASKING. Do
   NOT present "push to GitHub?" as a decision.
   Only genuinely OFF-PLAN irreversible actions require asking even with a
   recommendation — e.g. deleting an existing file that is NOT in this run's
   artifact list, or overwriting a prior paradigm/gap record that this run did
   not produce. If the action is in the standard pipeline's output contract, do
   it; if it reaches outside the run plan, ask.

Auto-approved decisions are never silent: each carries a one-line reason
(e.g. `auto: paradigm A2 via WeKnora/bin reuse — continue`). A run with zero
pending confirmations should read "no blockers" at handoff.

---

## Operation 1 — init-deep (hierarchical knowledge base)

**Goal:** exhaustive structural knowledge base: root AGENTS.md + per-subdir
docs. Gated by harness G1–G5.

```
init --repo <path>  (refresh_state.py)
DISCOVERY  → parallel task(explore) [structure/entry/conv/anti-pattern/build/tests]
             + dynamic agent scaling (>/100 files, /10k lines, depth≥4, large files,
               monorepo, multi-language) + direct bash census + read root/entry/config
             + LSP codemap (entry symbols, workspace symbols, ref centrality)
gate g1 (analyzable)  → PASS→persist
SCORING    → 8-factor weighted matrix (file count 3x, subdir 2x, code ratio 2x,
             unique patterns 1x, module boundary 2x, symbol density 2x, exports 2x,
             ref centrality 3x) → AGENTS_LOCATIONS {path,score,reason}
gate g2 (stack)   → PASS→persist
GENERATE   → write root AGENTS.md (50–150 lines: OVERVIEW/STRUCTURE/WHERE TO LOOK/
             CODE MAP/CONVENTIONS/ANTI-PATTERNS/UNIQUE STYLES/COMMANDS/NOTES) +
             per-subdir docs via task(category="writing") in parallel (30–80 lines,
             never repeat parent). File rule: exists→Edit, else→Write.
gate g3 (docs exist) + g4 (structurally sound)   → PASS
REVIEW     → dedup, remove generic/parent-dupes, trim, telegraphic style
gate g5 (build/test, may SKIP w/ recorded reason) → PASS
finish --summary
```

Exit codes: `0` PASS / `1` FAIL / `2` BLOCKED / `3` SKIP (G5, must be recorded).
Attempt budget 3 per gate; on exhaust → oracle once → `harness/ABORTED.md`.

**Full Op1 mechanics: `references/op1-init-deep.md` + `harness/README.md`.**

---

## Operation 2 — project profile (product-level view)

**Goal:** answer "what does this project honestly DO, for whom, and why is it
better" — a profile of **core functions (enumerated) + application scenarios +
core highlights/advantages**. This is the product lens the AGENTS.md structure
omits.

Grounded in how real sessions profiled repos: read README + docs + entry
behavior, then **fan out parallel explore agents, one per functional cluster**,
each returning verifiable facts (file paths + code evidence), NOT marketing
claims. Aggregate into a `PROFILE.md` at the repo root.

Structure (see `references/op2-profile.md` for the exact dimension template):
```
# <PROJECT> — Profile
## CORE FUNCTIONS        enumerate each capability; for each: what it does clean +
                          the code path/entry that proves it exists
## PROBLEM IT SOLVES     pain → solution mapping, with evidence
## APPLICATION SCENARIOS who/what-situation/why-this-not-that
## CORE HIGHLIGHTS       differentiating advantages (vs generic alternatives)
## LIMITATIONS           documented gaps (honesty ground)
```

**Content gate (non-scriptable):** every claimed core function must be anchored
to a real code path or doc — no anchor → drop the claim (anti-marketing).

---

## Operation 3 — iterative comparative research (the differentiator)

**Goal:** know a project's true worth by comparing it — and only by stripping
marketing fluff down to bottom-layer mechanisms, then comparing laterally +
vertically, then distilling reusable atomic capabilities.

### 3.1 Classify into the taxonomy FIRST → choose research path

**MANDATORY before any Op3 search** — classify against the deterministic
taxonomy (`references/taxonomy/KNOWLEDGE-TAXONOMY.md`):

1. **Axis A — Technology Paradigm** (the spine): assign 1 primary + 0..2
   secondary from **A1–A12** using judge-keywords from Op1/Op2 evidence.
2. **Axis B — Project Nature**: classify (below).
3. Record `A-primary` — it selects the **Op3 search dispatch** table
   (`references/taxonomy/DISPATCH.md`) and becomes the **Op4 gap/opportunity
   aggregation bin** (same id → `project_open_items.domain`).

Do not dispatch until the project has a paradigm class. The taxonomy already
knows which competitors/papers/standards a paradigm needs — this is the search
efficiency + precision multiplier.

| B: Nature | Research actions |
|-----------|------------------|
| Platform / architecture | find + deep-dive **high-similarity competitors** (A→competitor) |
| Capability / key technique | competitive analysis **+ deep paper search** (A→papers) |
| Comprehensive (capability+platform) | both **+ landscape benchmark** |
| High-value domain knowledge | **+ single-topic knowledge survey** (atomic/reference capabilities) |

A-primary dispatch column + B-nature jointly determine the lens. If the project
shows a mechanism with no existing A-paradigm, run the **taxonomy extension rule**
(§4 in KNOWLEDGE-TAXONOMY.md) to add one before dispatching.

### 3.2 Iterative deepening (2–3 rounds until convergent)

Loop: analyze → surface gaps/new capabilities → deepen → reanalyze → converge.
"Relative clarity" = gaps filled + capabilities understood + fluff removed.
Each round targets the newly-identified unknowns, never re-reads settled ground.

### 3.3 Anti-Hallucination — THE core discipline

A huge share of project "features" are **advertising copy with no substantive
content or bottom-layer tech behind them**. They add nothing to atomic-capability
accumulation. **For every claimed feature ask:**

```
Is there REAL bottom-layer mechanism?   (API/algo/protocol/kernel/inner design)
Is there PAPER backing?                 (cite the paper / public derivation)
Does it actually differ from competitors at the mechanism level?
  →  fails any = marketing fluff  →  DROP from the capability set
  →  all substantiated      = real capability  →  promote to atomic capability
```

Clarify ambiguous features **to the bottom-layer technology and mechanism**
before comparing — never compare surface claims.

### 3.4 Comparative positioning (only AFTER bottom-level clarity)

- **Horizontal** vs same-layer tools; **vertical** vs upstream/downstream stack
  (predecessor/evolution/substitute).
- Establish the TRUE difference & advantage, not the claimed one.
- e.g. both "GraphRAG": dissect construction method, retrieval mechanism, real
  scaling/update win, when to pick which — not "both do graph RAG".
- **Output must have distinguishability + searchability**: phrase the
  differentiation so a search/reader can locate it (tech keywords + paper titles +
  comparison table).

### 3.5 Distill & reuse

- Proven real capabilities → **reusable atomic capabilities**.
- Project-to-project reference patterns → **project reference capabilities**.
- Deliverables: `references/op3-research.md` defines the `COMPARISON.md` /
  `ATOMIC-CAPABILITIES.md` artifacts.

---

## Operation 4 — gap & opportunity analysis (knowledge closed-loop)

**Goal:** beyond "what this is" — find what it **CANNOT satisfy** (gaps) and
whether concepts **cross-pollinate into new technologies** (opportunities), then
**persist both to a shared store** so every future analysis continuously tracks
them. This is what makes analysis accumulate instead of evaporate.

```
BIN by taxonomy (deterministic): every gap/opportunity's `domain` = the
   project's Axis A primary paradigm id (assigned already in Op3.1). Same
   paradigm's gaps accumulate into ONE evolving picture instead of scattering
   (references/taxonomy/KNOWLEDGE-TAXONOMY.md).
READ the shared gap/opportunity store FIRST:
   aeterna_memory_search / aeterna_knowledge_query / sqlite analysis.db
   → does THIS repo FILL a known gap?   (update that gap's progress 0→1)
   → does it SEED a new opportunity?    (increment convergence count)
GAP ANALYSIS (two modes):
   A. external/competitive survey: websearch+webfetch+grep_app_searchGitHub → persist
   B. self-repo audit: component × {svc/test/migration/integration/frontend} ✅/⚠️/❌ → numbered gaps
    Gap record: {id, kind, domain(A-paradigm), gap_type, description(scope), severity,
                 demand_weight, fill_progress, priority=sev×demand×(1-fill_progress),
                 needer, status, originating_project}
OPPORTUNITY ANALYSIS (cross-pollination → new concept):
   when ≥N (real: 3) independent analyses converge on an emergent direction,
   promote observation → opportunity/new concept.
   Opportunity record: {id, type(convergence/align/cluster), direction, confidence,
                        description, contributingProjects[], domain, originating_project}
PERSIST to shared store:
    analysis.db `project_open_items` (unified gap+opp table)
    (schema: references/op4_analysis_store.sql) ← canonical registry
    + aeterna_memory_add {content, tags:[gap-analysis], layer:project, importance}
    + 〈project〉的缺口和机会分析.md (→ Op5 uploads)
```

**Anti-hallucination carries over:** a gap claim needs a cited source (landscape
evidence / audit table / code path) — uncited gap = fluff again. A gap's
`fill_progress` only rises when a later project demonstrably fills it. An opportunity
is a *derived* signal (≥3 converging independent analyses), not a one-project
summary.

**Full Op4 mechanics: `references/op4-gap-opportunity.md`.**

---

## Operation 5 — knowledge asset persistence

**Goal:** turn every artifact from Op1–Op4 into **durable, indexable knowledge
assets** — distinctive-named files pushed to the shared GitHub knowledge repo.
This is how finished analyses become a searchable library.

```
Target: {{KNOWLEDGE_REPO_URL}}  (canonical clone:
        {{KNOWLEDGE_REPO_DIR}} — source of truth for new writes)
NAMING — distinctive + searchable (core demand):
   <domain>/<subject>作为<role>的<analysis-type>.md
   e.g. 本体工程/semantica/okf-rs作为代码到本体的竞品分析.md
        推理优化/幻觉/Reverify阻止AI自说自话地的过度自信的综述分析.md
FLOW (real command chain):
   cp "<artifact>" "$W/<topic>/<distinctive-name>.md"
   git add -A && git status --short     # verify only intended files
   git commit -m "docs(<category>): <subject analysis-type>"
   git push origin main 2>&1 | tail -8 && echo "PUSH_EXIT=${PIPESTATUS[0]}"
```

Rules: work in ONE canonical clone; one distinctive file per deliverable
(one-subject-per-file = indexable); never push secrets (the repo's remote
already embeds a PAT — don't add more); don't commit `__pycache__`/temp/run.json.

**After Op5, MUST print the execution summary** covering:
generated filenames, upload locations (`{{KNOWLEDGE_REPO_URL}}/<domain>/<filename>`),
and the project's core highlights (2-4 distinctive findings from Op2/Op3).
See `references/op5-persist.md` §Execution summary for the exact template.

**Full Op5 mechanics: `references/op5-persist.md`.**

---

## Compose, don't rebuild

- `analyze-mode`/`search-mode` conventions govern how exploration fires
  (parallel explore/librarian, `load_skills=[]` + `run_in_background=true`,
  Oracle/Artistry escalation on complexity).
- `/project-init` — stack detection for Op1 G2/G5.
- `librarian` agent — remote/OSS/paper research for Op2/Op3.
- `ponytail` — Op1 G4 trim checklist.
- `aeterna_memory*` / `supermemory` — the shared gap/opportunity store read in
  Op4 and the atomic-capability register.
- These are optional; the skill is self-contained.

## Honest boundaries

- Op1 produces a knowledge base, not a modified codebase.
- Op3's verdict is the **opposite of a hype summary** — it deliberately deletes
  claims it cannot substantiate at the mechanism/paper level.
- Op4 is a **shared-store writer**: persistence is mandatory; a gap/opportunity
  that isn't recorded is worthless. But it only writes cited findings.
- Op5's naming rule is what makes assets findable — a bare "analysis.md" is a
  failed persist.
- A repo with no analyzable source or purely-marketing README: Op1 G1 FAILs and
  Op3 strips it to nothing — tell the user, don't force a sham run.