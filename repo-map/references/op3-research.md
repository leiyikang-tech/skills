# Op3 — Comparative Research playbook (the differentiator)

Goal: know a project's true worth by stripping marketing fluff to **bottom-layer
mechanism**, comparing **laterally + vertically**, and distilling **reusable
atomic capabilities**. This is the operation that separates real understanding
from hype. Grounded in the competitive-deep-research session (ses_005ec1af —
9-competitor parallel survey, SURVEY-02 matrix).

Read this file when Op3 starts.

---

## 3.1 Classify into the taxonomy FIRST → then choose research path

**MANDATORY first action before any search:** classify the project against the
deterministic taxonomy (`references/taxonomy/KNOWLEDGE-TAXONOMY.md`):

1. **Axis A — Technology Paradigm**: assign 1 primary + 0..2 secondary from
   A1–A12 (judge-keywords from Op1/Op2 evidence, NOT the README).
2. **Axis B — Project Nature**: classify from the table below.
3. Record `A-primary` — it selects the `Op3 dispatch` column and becomes the
   **Op4 gap/opportunity aggregation bin** (same id flows into `project_gaps.domain`).

Do **not** proceed to dispatch until the project has a paradigm class. This is
why search is precise: the taxonomy already knows which competitors/papers/
standards a given paradigm needs.

| B: Nature | Evidence | Op3 research actions |
|-----------|----------|----------------------|
| 平台 / 架构类 | framework/runtime/platform/full-stack, layered modules | find + deep-dive **high-similarity competitors** (A `Op3 dispatch` → competitor) |
| 能力 / 关键技术类 | algorithms, DSP, low-level libs, single sharp mechanism | competitive **+ deep paper search** (A → papers) |
| 综合性 (capability+platform mixed) | both | both **+ 7-layer landscape benchmark** |
| 领域知识高价值 | domain-heavy, data/ontology rich, benchmarks | **+ single-topic knowledge survey** → atomic/reference capabilities |

The cross-cutting rule: the **A-primary dispatch column + B nature** jointly
determine the research lens. Pick the lens that maximizes learning about the
underlying technology, never the lens that makes the repo look good. Per-paradigm
dispatch tables (which competitors/domains/standards/papers) live in
`references/taxonomy/DISPATCH.md` — extend that table, don't ramble here.

If the project exhibits a mechanism with no existing A-paradigm, run the
**taxonomy extension rule** (§4 in KNOWLEDGE-TAXONOMY.md) to add one before
dispatching — determinism must not be skipped, it must absorb novelty.

## 3.2 Iterative deepening (2–3 rounds until convergent)

```
Loop:  analyze → surface gaps + new capabilities → deepen → reanalyze → converge
Exit:  "相对清晰" = 缺口填满 + 已知能力理解透 + 广告被剥离
```
- Each round targets **only the newly-identified unknowns** — never re-reads settled ground.
- On timeout/lost background task: **re-fire with the verbatim re-delivery request**
  ("Please re-deliver your COMPLETE structured markdown... do not reference an
  earlier file, write it out") — NEVER guess from memory.
- To build a comparison matrix, first check the taxonomy/bin
  (`references/taxonomy/DISPATCH.md`): an A-paradigm row often fixes the
  comparison axes (scenario taxonomy / who-to-compare). **Auto-take that as the
  default** (Confirmation handling rule 1) → don't stall. Only if the bin gives
  no axis AND two axis-splits are equally defensible → use the `question` tool
  to disambiguate (rule 2), then continue.

### Forcing prompt — paste verbatim into EVERY self-project + competitor research agent

This is the code-graph-rag forcing directive (proven to stop README-parroting).
Append to every `task(...)` research prompt in Op3:

```
TOOL-ONLY ANSWERS. You answer ONLY from tool results, never from prior knowledge
or pattern-matching. Answer directly, ONE explore call, never grep first.
You MUST dive into the source code itself. Do not just describe the files;
explain what the code *does* — the mechanism, the control flow, the data shape.
Cite your sources: every factual claim must cite the file path (+ line where
possible) it came from. Read the main entry point(s) and the deepest 2-3 modules.
If the answer is not in the tool results, say so and dig again — do not invent.
```

For the self-project, build a symbol graph first (`codegraph index <repo>`), then
read real bodies via `codegraph query/callers/callees` — a capability that cannot
be traced to a real symbol + line is a hypothesis, not a fact.

## 3.3 Anti-Hallucination — THE core discipline

A large share of a project's "features" is **advertising copy with no substantive
content or bottom-layer tech behind it**. It adds nothing to atomic-capability
accumulation. For EVERY claimed feature apply the demand-test:

```
对一个功能宣称，逐层追问:
1. 有无真实底层机制?   (API/算法/协议/内核/内部设计 — 抠到最底层技术，非表面描述)
2. 有无论文支撑?       (能引用论文/公开推导，否则只是名词)
3. 与竞品是否在机制层面真不同? (不是"都做X"级的表面差异)
   ─ 任一不过 = 广告语 → 从能力集合剔除
   ─ 全部通过 = 真实能力 → 晋升为原子能力
```

### Anti-hallucination mechanics (verified from real session hits)

1. **Self ground-truth via `gh api` / `curl api.github.com` directly** — the self-project's
   stars/license/created/pushed/stats come from authoritative API data, NOT the researcher's memory.
2. **Freeze verified facts to `ctx_memory` (PROJECT_RULES) after merging** — so later
   deliverables cite the SAME canonical snapshot, never re-derive/misremember.
3. **Cross-validate key claims against third-party aggregates** (Awesome lists, independent
   comparison docs, other surveys) — "关键点已交叉通过第三方".
4. **Forced sourcing directive on every research agent**: `"Return a dense, factual,
   structured report with verifiable claims and cited source URLs. Telegraphic style,
   no fluff."` + `"I need verifiable facts, not speculation."`
5. **Time-box + "no public evidence → say so"** for paper/vendor research
   (`~6–8 min actual fetching`; `If no verifiable public evidence, say "no public
   evidence" and move on — DO NOT loop`).
6. **User-correction loop** — on user pushback ("你没有遵循我的指令…请更新数据重新输出"),
   regenerate against the user-confirmed spec, never against memory.
7. **Neutral labeling** — flag same-family forks/ports as `⚠️ 同一家族` (honest distinction
   between a fork/port and a true rival), never omit for polish.

## 3.4 Comparative positioning — ONLY after bottom-level clarity

Order is strict: **clarify to bottom mechanism FIRST → only then compare**. Comparing
surface claims is how "都做 GraphRAG" nonsense arises.

### Horizontal vs vertical
- **横向** same-layer tools (current alternatives in the same niche).
- **纵向** upstream/downstream stack (predecessor / evolution / substitute).

### The fixed 10-dimension competitor profile template (use on EVERY competitor)
Bake seed data (star count + one-line positioning) into each prompt; hard-vary ONE
per-project comparative axis. Every prompt = same `[GOAL]/[DOWNSTREAM]/[REQUEST]` scaffold:
1. GitHub repo URL + owner
2. Star / fork / license / primary language (+ recent activity)
3. Core architecture (skill suite? SKILL.md structure? plugin?)
4. Skills included (ENUMERATE all)
5. Agent count / modes / model routing
6. Key features (HITL? citation verification? API integrations?)
7. Installation method
8. Recent activity / last commit / version
9. Unique strengths vs generic/niche peers
10. Documented limitations
→ `subagent_type: "librarian"`, `run_in_background: true`.

### The 8-dimension comparison matrix (deliberately NOT star-sorted)
Cells are **ground facts** (skill counts, gate counts, verified dates), not vibes:
1. 架构形态 (multi-skill suite / single-skill orchestration / library)
2. Agent 编排 (agent count / SKILL.md router / cross-model adversarial)
3. HITL 强度 (architecture-level / advisory / none)
4. 确定性工具 (deterministic gates vs pure prompt vs cross-model review)
5. 引用 / 文献验证 (citation-verification mechanism)
6. 写作定位 (AI 代写 vs copilot vs argument reconstruction)
7. 治理 / CI (version lockstep / drift detection vs hygiene vs none)
8. 多平台 / 生态

Expand as needed into explicit columns; the point is orthogonal dimensions that
cut across all projects so "the biggest stars" can't be the only narrative.

### 3.4.1 The GraphRAG-vs-LightRAG bar (辨识度 + 可搜性)
When two projects share a category label ("both are GraphRAG"), the deliverable
must NOT stop at "both do graph RAG". Dissect and name:
- construction method difference (global vs local index)
- retrieval mechanism difference (community detection vs hybrid retrieval)
- real scaling/update win (and why — the underlying mechanism)
- when to pick which (scenario → choice)
Phrase the differentiation with **tech keywords + paper titles** so a search/reader
can locate it. The output must survive being searched — distinguishability IS the bar.

## 3.5 Distill & reuse

Everything proven real promotes to reusable assets:
- **可复用原子能力** — a verified capability (backed by mechanism + paper) usable in other projects.
- **项目参考能力** — a project-to-project reference pattern (how one project solved a
  recurring problem) worth borrowing.

### Deliverables
- `COMPARISON.md` — the 8-dim matrix + per-competitor verdicts + 辨识度 statement.
- `ATOMIC-CAPABILITIES.md` — each proven capability: what it does + the bottom-layer
  mechanism + paper backing + the code path that proves it.
- **`LANDSCAPE.md`（生态地图 — 仅按需独立成文档）** — 该 paradigm 的**生态全景地图**，
  按层组织（基础设施 → 框架 → 应用 → 工具/数据集），每层列代表项目 + 职责。这是
  **生态级产物**（跨多个项目，不属于单个项目）。

### Atomic-capability evidence schema (graphify data model — anti-hypothesis)

Every row in `ATOMIC-CAPABILITIES.md` MUST carry the graphify evidence triple so a
claim without source backing is structurally impossible:

```
capability | mechanism (named bottom-layer) | source_file | source_location | confidence
```

- `source_file` — the file that implements it (relative to the analyzed repo).
- `source_location` — the `file:LINE` anchor (must resolve on disk).
- `confidence` — one of `EXTRACTED` (read from source), `INFERRED` (inferred from
  surrounding code, must be labeled as such), `AMBIGUOUS` (unclear, flag it).
- Anything below `EXTRACTED` is a **hypothesis, not a fact** — label it and do not
  count it as a verified atomic capability.

**Mechanical enforcement (Q3):** run the depth gate over `ATOMIC-CAPABILITIES.md`
after writing it:
```bash
python3 $HARNESS/depth_check.py --repo <repo> --out <out-dir> --min-anchors 3
```
This verifies every `file:LINE` anchor resolves and flags unanchored mechanism
claims. FAIL → rework (attempt budget 3). Run `citation_check.py` on any paper/vendor
URLs in the rows — a URL that does not resolve breaks the row.

### 生态地图落位（方案A：独立 landscape 文档，不夹在单项目文档）

生态地图是**生态级综述**，不是单项目属性，故独立存放，且**仅按需创建**以免每个项目
重复写一份生态全景：

- **触发条件（满足任一才新建 landscape 文档）**：
  1. 该 paradigm 尚无生态全景文档（work-log 里查不到 `*landscape*` / `*生态全景*` 先例）；
  2. 本 run 发现的生态信息**显著超越**现有 landscape 文档（新增了层级 / 代表项目 / 演化谱系）。
- **否则**（已有 landscape 文档且无显著新增）：**不新建**，在完成报告的生态地图要素里
  **引用已有文档路径**即可。
- **命名**（复用现有先例 `data-agent-landscape-数据智能体生态全景-2026.md`）：
  ```
  <domain>/<paradigm>-landscape-<paradigm>生态全景-<YYYY>.md
  ```
  例：`智能体框架/agent-harness-landscape-智能体编排生态全景-2026.md`
- **内容**：生态地图 = 分层全景（每层代表项目+职责）+ 演化谱系（谁继承谁）+ 各层成熟度。
  这是完成报告「应用建议·生态地图」要素的**完整载体**。
- **由 Op5 持久化**（放入匹配的 `<domain>` 主题目录）。

## Op3 exit loop recap
```
识别性质 → 分流(竞品/论文/领域综述+landscape)
  → 迭代2-3轮: 深挖新能力/缺口 → 防幻觉剥离广告 → 抠到底层机制/论文
  → [获得底层实现后] 横向+纵向对比 → 彻底搞清真优势/真区别
  → 辨识度输出(可搜) → 沉淀原子能力 + 项目参考
```
Stop when: gaps are filled, capabilities understood to mechanism, fluff stripped,
and differentiation is explicit — not before.