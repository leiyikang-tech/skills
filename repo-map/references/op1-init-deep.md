# Op1 — init-deep playbook (hierarchical AGENTS.md knowledge base)

The full mechanics for Operation 1: exhaustive structural mapping → scored
doc-location decision → generation → review. Read this file when Op1 starts.
Gated by the harness (G1–G5). This is the structcode base everything else builds on.

## Phase 1 — Discovery (parallel exploration)

Instantiate a Discovery checklist (mirrors how real sessions bootstrap):

```
- Plan: todowrite the 4 Op1 phases (discovery→scoring→generate→review)
- Fire parallel task(explore) agents (6-canonical set below)
- Dynamic agent scaling by project size/depth (table below)
- Direct bash structural census (parallel with the agents)
- Read root README/AGENTS/CLAUDE + root directory
- Read entrypoints + config + manifest
- LSP codemap (typed repos)
- Collect background_output; ctx_reduce consumed tool_results CONSTANTLY
```

### The 6 fixed explore agents (CANONICAL — the most reused structure in the corpus)

All `run_in_background=true`, `load_skills=[]`, end each prompt with:
"Return file paths with pattern descriptions. Skip node_modules/.git/dist. Be exhaustive."

| agent | prompt |
|-------|--------|
| structure | "Project structure: PREDICT standard patterns for detected language → REPORT deviations only + for the 2-3 most load-bearing modules NAME the mechanism with a `path:LINE` anchor" |
| entrypoints | "Entry points: FIND main files (server/client/CLI/bin/Vite/router) → REPORT non-standard organization + WALK the primary request/startup flow through real symbols (`file:LINE`)" |
| conventions | "Conventions: FIND config files (.eslintrc, pyproject.toml, tsconfig, .editorconfig, .prettierrc) → REPORT project-specific rules + package.json scripts" |
| anti-patterns | "Anti-patterns: FIND 'DO NOT', 'NEVER', 'ALWAYS', 'DEPRECATED', 'HACK', 'FIXME', 'TODO' comments → LIST forbidden patterns + the guard code that enforces them (`file:LINE`)" |
| build/CI | "Build/CI: FIND .github/workflows, Makefile, scripts/, Dockerfile; how it builds + deploys" |
| tests | "Test patterns: FIND test configs + structure + framework + how to run tests" |

### Dynamic agent scaling (DON'T use a static count — scale to the project)

| Factor | Threshold | Additional agents |
|--------|-----------|-------------------|
| Total files | >100 | +1 per 100 files |
| Total lines | >10k | +1 per 10k lines |
| Directory depth | ≥4 | +2 deep exploration |
| Large files (>500 lines) | >10 files | +1 complexity hotspots |
| Monorepo | detected | +1 per package/workspace |
| Multiple languages | >1 | +1 per language |

Scale first, then spawn:
```bash
total_files=$(find . -type f ! -path '*/node_modules/*' ! -path '*/.git/*' | wc -l)
large_files=$(find . -type f \( -name "*.ts" -o -name "*.py" \) -exec wc -l {} + 2>/dev/null | awk '$1>500{c++}END{print c+0}')
```

### Direct bash structural census (the repeatable scaffold — parallel with agents)

```bash
find . -type d -not -path '*/\.*' ! -path '*/node_modules/*' -not -path '*/dist/*' -not -path '*/build/*' | awk -F/ '{print NF-1}' | sort -n | uniq -c
find . -type f ! -path '*/\.*' ! -path '*/node_modules/*' | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn | head -30
find . -type f \( -name "*.py" -o -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.go" -o -name "*.rs" \) ! -path '*/node_modules/*' | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn | head -20
find . -type f \( -name "AGENTS.md" -o -name "CLAUDE.md" \) ! -path '*/node_modules/*' 2>/dev/null
```

### Read + LSP

- read root dir, then AGENTS.md/CLAUDE.md/README.md (prose intent + constraints)
- read entrypoint(s) + config + manifest (package.json/pyproject/Cargo.toml/go.mod/tsconfig)
- **symbol graph first** (build the deep-read substrate before any claim):
  ```bash
  codegraph index <repo>   # then query/callers/callees/impact for load-bearing units
  ```
- typed repos (TS/Go/Java): `lsp_symbols` scope=document on main entry; workspace
  symbols for class/interface/function; `lsp_find_references` on top exports for centrality
- **never grep-first**: prefer symbol graph + LSP; raw grep/read only to confirm a
  specific detail the graph didn't cover (codegraph's own "Read/Grep=0 target" rule)
- LSP + codegraph both unavailable → fall back to explore agents + ast_grep_search
- **Extract, don't inventory**: for the 2-3 most load-bearing units, capture the
  actual mechanism (how it works, control flow, data shape) with a `file:LINE`
  anchor — not just "there's an engine in engine/".

### Collect + merge

`background_output` each agent → merge bash + LSP + existing + explore findings.

### Gate G1

```bash
python3 $HARNESS/gates.py g1 --repo <repo>
```
PASS if any manifest/README/AGENTS OR ≥10 source files. FAIL → re-walk a DIFFERENT
wider set. Doc-only repo with no source → stop + tell user, no sham run.

## Phase 2 — Scoring (8-factor matrix → doc-decision list)

### Tech stack (G2 input)

Prefer manifest (package.json/pyproject/Cargo.toml/go.mod/Gemfile); fall back to
language census. `gates.py detect_stack` auto-detects both — trust it.

### Depth analysis — one level deeper (module-targeted second wave)

| agent | prompt |
|-------|--------|
| large files | "Find files >500 lines; flag complexity hot-spots" |
| deep modules | "Find modules at depth 4+; hidden package-layer boundaries" |
| shared utils | "Find cross-cutting shared utilities (shared-doc candidates)" |
| per-architecture | "Analyze <frontend/backend/server/client> architecture; map request flow" |

Typed repos, add directly: `ast_grep_search '<pattern>'`, `lsp_symbols <entry> --scope document`.
Mine the 2-3 most load-bearing symbol patterns, not a blanket sweep.

### The 8-factor scoring matrix (weighted, from real init-deep spec)

| Factor | Weight | High Threshold | Source |
|--------|--------|----------------|--------|
| File count | 3x | >20 | bash |
| Subdir count | 2x | >5 | bash |
| Code ratio | 2x | >70% | bash |
| Unique patterns | 1x | own config | explore |
| Module boundary | 2x | has index.ts/__init__.py | bash |
| Symbol density | 2x | >30 symbols | LSP |
| Export count | 2x | >10 exports | LSP |
| Reference centrality | 3x | >20 refs | LSP |

Decision: **Root (.) ALWAYS** / score >15 → create / 8–15 → create if distinct
domain / <8 → skip (parent covers). Collapse siblings into their parent unit
(~2–6 subdirs for a mid-size repo, don't doc 30 leaves).

Output:
```
root_kb: <repo>/AGENTS.md   (always)
dirs: [ <repo>/<subdir> -> AGENTS.md, ... ]
stack: <node|python|rust|go|...>
```

### Gate G2

```bash
python3 $HARNESS/gates.py g2 --repo <repo> --stack <name>
```
PASS if stack identified. Attempt 2 → `task(oracle)` for stack; max 3.

## Phase 3 — Generate

### Root doc (the ONE file the orchestrator writes)

Write `<repo>/AGENTS.md` — the real sessions' root shape:
```
# <PROJECT> KNOWLEDGE BASE
Generated | Commit (git short-sha) | Branch

## OVERVIEW        one-paragraph what + purpose
## STACK           language(s), frameworks, build, test, package manager
## ARCHITECTURE    layer boundaries + request/data flow across 2-3 load-bearing units
## CONVENTIONS     naming, config, idiomatic patterns, anti-patterns to avoid
## BUILD / TEST / RUN   exact commands (from build/CI + tests findings)
## KEY PATHS       entrypoints + unit structure map
```
Concrete, grounded, never speculative. 60–150 lines sweet spot.

### Per-subdir docs (delegate to writing agents, parallel)

Spawn `task(category="writing", run_in_background=true)`, ONE per scored subdir,
with a self-contained brief (stack + architecture + what this dir owns + key files
so it doesn't re-explore the whole repo). The orchestrator must NOT write these.

**File rule:** AGENTS.md already exists → `edit`; else `write`. NEVER overwrite an
existing file with Write. Always check existence first.

### Gate G3

```bash
python3 $HARNESS/gates.py g3 --repo <repo> --out <dest> --dirs <d1,d2,...>
```
PASS when root doc >1KB AND no empty per-dir doc. FAIL → regenerate only missing/empty.

## Phase 4 — Review (deduplicate, validate, trim)

Spawn a writing subagent for the pass (or do mechanical greps yourself):

- **Deduplicate**: repeated block across dirs → hoist to root, one-line pointer in subdirs.
- **Validate**: every `[text](/path)` / `(../x/y)` resolves to a real file; numbers/paths match discovery evidence.
- **Trim**: no doc >200KB; target <40–80 lines per subdir; apply the ponytail lens
  (delete reinvented-stdlib, dead flexibility, speculative abstraction, boilerplate).

### Gates G4 + G5

```bash
python3 $HARNESS/gates.py g4 --repo <repo> --out <dest> --dirs <d1,d2,...>
python3 $HARNESS/gates.py g5 --repo <repo> --stack <name>
```
G4 PASS: ≥1 doc, no zero-byte, no >200KB, internal .md/.py/.ts/.js/.rs/.go links resolve.
G5 PASS: per-stack build/lint/test clean. G5 `exit 3` (SKIP) acceptable ONLY with a
recorded reason in run.json (missing toolchain / no tests) — never silent, never false-pass.

FAIL loops: G3 regenerate missing only; G4 trim/fix refs; G5 delegate deep/quick to fix build.
Exhaustion: escalate to oracle once → `harness/ABORTED.md`.

## Op1 exit-code contract (gates.py)

`0` PASS / `1` FAIL / `2` BLOCKED / `3` SKIP(G5, must be recorded). Persist each
result via `refresh_state.py gate <g> --result ...`; a PASS advances atomically,
a crash resumes at the exact failed gate. See `harness/README.md` for run.json shape.

## Op1 core anti-patterns (from the /init-deep spec)

- **Static agent count** — MUST scale dynamically to project size/depth.
- **Sequential execution** — MUST parallelize (explore + LSP + census concurrent).
- **Ignoring existing** — ALWAYS read existing AGENTS/CLAUDE first, even on --create-new.
- **Over-documenting** — not every dir needs a doc.
- **Redundancy** — child never repeats parent.

---

## awesome-list mode — Op1 变体：列表解析 + 项目挑选

当检测到目标是一个 awesome 列表时，Op1 不生成 AGENTS.md，而是**解析列表 + 挑选项目**。

### 检测条件

README 包含 50+ 条 `- [Title](URL)` 子弹条目，按 `##`/`###` 分类锚分组，无代码 manifest（无 package.json/Cargo.toml/go.mod）。

### Phase 1 — 列表解析

```
读取 README → 提取所有条目 → 结构化列表
```

每个条目提取：
- **title**（markdown link text）
- **url**（`(…) ` 中的 URL）
- **category**（`##`/`###` 分类锚）
- **stars**（`![Stars](...github/stars/...)` badge 或 `Stars: N` 文本）
- **description**（`—` 分隔的 note 文本）
- **source_type**（github repo / arXiv / blog — 从 URL host 推断）
- **vendor**（从 `github.com/org/repo` URL 路径推断）

### Phase 2 — 分析价值评分（v2，可计算加权公式）

**目标**：找出**分析后能产生价值**的项目——补哪个缺口、沉淀哪个原子能力、
与已分析资产有什么**新**差异。**stars 是已知度信号，不是分析价值信号**。
stars 只做 tiebreaker，绝不做主排序键。

**评分公式**（每个项目算出 0..1 的分析价值分 `value_score`）：

```
value_score = 0.35*gap_fill      # 是否弥补未填缺口（用户价值第一）
            + 0.20*paradigm_relevance  # 是否落在高缺口范式 bin
            + 0.25*novelty       # 与已分析资产差异化（新机制/新领域）
            + 0.15*atomic_value  # 是否沉淀可复用原子能力（有实质底层机制）
            + 0.05*maintenance   # 维护/认可信号（stars 归一化）
```

**每个维度的可计算规则**：

1. **gap_fill（0.35）**：项目分类到 paradigm → 查该范式未填缺口数
   ```sql
   SELECT COUNT(*) FROM project_open_items
   WHERE domain = '<paradigm_id>' AND status IN ('discovered','analyzing');
   ```
   命中未填缺口越多分越高；若项目描述**明确命中某个具体缺口**（如"支持
   macOS/Linux 客户端"→ 补 client-portability），额外加分。数据源：
   `project_open_items`（当前 73 gap + 29 opp 未填，集中在 A1/A10/A12/A3/A7）。

2. **paradigm_relevance（0.20）**：项目 A-axis 分类是否落在**高缺口范式**。
   从 `project_open_items` 聚合每范式未填数，归一化到 0..1。高缺口范式
   （A1/A10/A12）→ 高分；无缺口范式 → 低分。

3. **novelty（0.25）**：与已分析资产对比——项目名/仓库模糊匹配
   `analysis_docs.title` + `topic`（当前 545 篇，覆盖 247 仓库/631 论文主题）。
   无匹配（全新领域/机制）→ 1.0；已分析过同类 → 0.2（除非有明显新机制）。
   数据源：`analysis_docs` 的 title/topic 分布（hermes-harness/智能体框架/
   semantica/WrenAI/3D重建 等已覆盖主题）。

4. **atomic_value（0.15）**：从 awesome 描述判断——含**实质底层机制关键词**
   （算法/API/框架/引擎/协议/内核/推理/检索/构造/优化…）→ 高分；纯链接收集/
   教程/营销文案 → 低分。这就是"广告语 vs 真能力"的判别。

5. **maintenance（0.05）**：stars 归一化（`log10(1+stars)` 缩放到 0..1），仅作
   次级参考。

**排序**：按 `value_score` DESC。**stars 只在 value_score 相同时作 tiebreaker**。

**已分析项目排除**：
```sql
SELECT project_path FROM analysis_index WHERE status = 'analyzed';
```

**waitlist 入库时记录 value_score**（Phase 3 的 UPSERT 一起写入），使 waitlist
查询能按分析价值排序，而非 stars。

### 一致性保证（排名可复现、不随顺序漂移）

排名必须满足：**同一批条目、同一输入，无论分析顺序如何，排名结果完全一致**。
四个机制保证：

1. **快照隔离（消除顺序依赖）**：排名阶段**只读**缺口板，**不写**。
   gap-paper 深挖（`UPDATE project_open_items SET fill_progress`）严格放到
   **排名之后**的阶段。否则先分析的条目填了缺口，会拉低后分析条目的
   `gap_fill` → 排名随分析顺序漂移。规则：**排名前固定一份缺口快照，全批用它算**；
   批内绝不在排名阶段改缺口板。

2. **novelty 基准静态**：novelty 查 `analysis_docs`（work-log 文档索引），
   awesome 分析**不写入**它 → 全批 novelty 用同一份已分析资产集合，稳定。

3. **确定性评分**：`atomic_value` 用**关键词规则**判断（含实质机制关键词 →
   高分；链接收集/营销 → 低分），**不用 LLM 自由判断**。全部 5 个维度都走规则
   计算 → 同一输入跑两次结果一致。

4. **输入版本记录**：每条目评分时记录输入快照（缺口板行数 + analysis_docs 计数
   + `scored_at` 时间戳），存 `last_updated`，供审计与复现。若缺口板/已分析资产
   在批后变化，重跑排名即可刷新（幂等 UPSERT，不产生重复行）。

### Phase 3 — 自动批量排名入库（全量，无需确认）

**不是手动单挑**——自动分析**所有**条目并排名入库。流程：

1. **阶段一（全量排名，只读）**：对 `analysis_index` 全部 `status='pending'`
   条目算 `value_score` + 5 分量（用一致性保证的静态快照），按 `value_score DESC`
   排名，统一写回（`status='waitlisted'`，含各分量）。**此阶段不写缺口板**。

2. **阶段二（逐条深挖，按排名）**：按排名从高到低自动分析：
   - `github` → clone → Op1-Op5（见下方分支 A）
   - `arxiv`/`blog` → gap-paper 判定 → 命中才深挖（见分支 B）
   - 每分析完一个：`UPDATE analysis_index SET status='analyzed', analyzed_at=now,
     analysis_path='<path>', n_gaps=?, n_opportunities=?`
   - **此阶段才允许写缺口板**（gap-paper 填缺口）

3. **阶段三（持久化）**：全部完成后 git push 到 work-log（Op5）。

**可选上限**：深挖条目过多时，按排名截取前 N 个（`LIMIT`），或设
`value_score < 阈值` 停止——避免低价值条目也全量深挖。默认**全量自动逐个**。

**执行语义总结**：
- 排名 = 全量自动（所有条目都算分排序）
- 深挖 = 自动逐个（按排名顺序，全量或截断）
- 一致性 = 快照隔离（排名阶段不写缺口板）+ 确定性规则评分 + 幂等 UPSERT

### Phase 3 — 自动批量排名入库（全量，无需确认）

> 阶段一（全量排名，只读）已在上面「一致性保证」后的流程说明。此处是
> 排名结果的**统一入库 SQL**——对 `analysis_index` 全部条目 UPSERT，
> `status` 置 `waitlisted`（尚未深挖）或保留 `analyzed`（已深挖过）。

**入库 SQL**（全量自动，幂等——重复跑只刷新 value_score，不产生重复行）：

```sql
INSERT INTO analysis_index
  (project_path, project_name, source_list, source_type, stars, category,
   paradigm_id, core_functions, why_worth, value_score,
   v_gap_fill, v_paradigm, v_novelty, v_atomic, v_maintenance, status)
VALUES
  ('<url>', '<name>', '<list>', '<github|arxiv|blog>', <stars>, '<cat>',
   '<paradigm>', '<核心功能介绍>', '<为什么值得分析>', <value_score>,
   <gap_fill>, <paradigm>, <novelty>, <atomic>, <maintenance>, 'waitlisted')
ON CONFLICT(project_path) DO UPDATE SET
  source_type    = excluded.source_type,
  core_functions = excluded.core_functions,
  why_worth      = excluded.why_worth,
  value_score    = excluded.value_score,
  v_gap_fill     = excluded.v_gap_fill,
  v_paradigm     = excluded.v_paradigm,
  v_novelty      = excluded.v_novelty,
  v_atomic       = excluded.v_atomic,
  v_maintenance  = excluded.v_maintenance,
  status         = CASE WHEN analysis_index.status='analyzed'
                        THEN 'analyzed' ELSE 'waitlisted' END;
```

- **status='waitlisted'**：已记录核心功能，等待被深度分析
- **source_type**：`github` / `arxiv` / `blog`（从 URL host 推断）——决定拉取时的
  分析分支：github → clone + Op1-Op5；arxiv/blog → 论文深挖流程（下方）
- **core_functions**：从 awesome 列表描述提取 + 可读 README 首页抓一句话补全
- **why_worth**：Phase 2 分析价值评分的一句话理由
- **value_score**：Phase 2 公式算出的分析价值分（0..1）
- 已分析过（status='analyzed'）的项目不降级，仅更新 source_type/core_functions/why_worth/value_score

**排名结果**：全部条目已入库（status='waitlisted'），可按 `value_score DESC`
查看全量排名；需要时按 Phase 4 排序参数拉取深挖。

### Phase 4 — 自动批量深挖（按排名逐个分析）

阶段二：按 `value_score DESC` 排名，从高到低**自动逐个分析**每个条目
（github → clone + Op1-Op5；arxiv/blog → gap-paper 深挖）。可选截断：
只分析前 N 个，或 `value_score < 阈值` 停止。

**查看排名/截断依据（排序参数）**：`<sort_key>` 决定"先分析哪些"，可取下列值
（默认 `value_score`）：

| 排序键 | 含义 | 查询列 |
|--------|------|--------|
| `value_score`（默认） | 综合分析价值 | `value_score DESC` |
| `gap_fill` | 缺口弥补价值最高优先 | `v_gap_fill DESC` |
| `novelty` | 差异化/新机制最高优先 | `v_novelty DESC` |
| `atomic` | 原子能力价值最高优先 | `v_atomic DESC` |
| `paradigm` | 范式相关性最高优先 | `v_paradigm DESC` |
| `stars` | 高 star（仅显式要求时） | `stars DESC` |
| `paradigm_group` | 按范式分组查看 | `paradigm_id, value_score DESC` |

```sql
-- 默认：按综合分析价值排序（推荐）
SELECT project_path, project_name, value_score,
       v_gap_fill, v_novelty, v_atomic, paradigm_id,
       core_functions, why_worth
FROM analysis_index WHERE status='waitlisted'
ORDER BY value_score DESC;

-- 例1：只看"缺口弥补价值"最高的（优先补短板）
SELECT project_path, project_name, v_gap_fill, core_functions, why_worth
FROM analysis_index WHERE status='waitlisted'
ORDER BY v_gap_fill DESC;

-- 例2：只看"差异化/新机制"最高的（避开已分析同类）
SELECT project_path, project_name, v_novelty, core_functions, why_worth
FROM analysis_index WHERE status='waitlisted'
ORDER BY v_novelty DESC;

-- 例3：按范式分组，看每组缺口弥补价值
SELECT paradigm_id, project_path, project_name, v_gap_fill, value_score
FROM analysis_index WHERE status='waitlisted'
ORDER BY paradigm_id, value_score DESC;
```

**自动循环**（按排名逐个，直到全量或到达截断条件），对每个条目**先按
`source_type` 分支**：

1. 更新状态：`UPDATE analysis_index SET status='in_progress' WHERE project_path='<url>'`
2. **`source_type='github'`（gitlab/bitbucket/.git）** → 下方 clone + 标准 Op1-Op5
3. **`source_type='arxiv'/'blog'`** → 走下方「论文深挖流程」（不 clone，webfetch）
4. 分析完成：`UPDATE analysis_index SET status='analyzed', analyzed_at=now,
   analysis_path='<path>', n_gaps=?, n_opportunities=? WHERE project_path='<url>'`

### 从 waitlist 拉取后如何分析

#### 分支 A — 代码仓库（source_type='github'）：URL → clone → analyze

repo-map 的 Op1 只接受**本地目录**（`refresh_state.py init --repo <path>`
检查 `os.path.isdir`；`gates.py` 用 `find` 检查本地文件），不接受 URL。
所以代码仓库项目必须先从远程 **clone 到本地**，再跑标准流程。

##### 1. URL 分类（决定 fetch 方式）

| URL host | 处理 |
|----------|------|
| `github.com` / `gitlab.com` / `bitbucket.org` / 以 `.git` 结尾 | `git clone`（有代码可分析） |

从 URL 提取 `<org>/<repo>`：`github.com/org/repo` → 斜杠拆分第 2、3 段。

#### 2. clone 缓存目录（持久化，支持 Refresh 增量）

```
{{REPOS_DIR}}/<org>/<repo>/
```

- **持久化**（不是 /tmp 临时）：awesome 项目长期存在，未来版本更新要复用
- 目录不存在 → 首次 clone
- 目录存在 → 增量 pull
- Refresh 增量依赖 `git diff <last_sha>..HEAD`，**必须完整 clone 含历史**，
  **不要 `--depth 1` 浅 clone**（会丢失历史、破坏增量能力）。

#### 3. clone 命令

```bash
# 首次（完整 clone，含历史；走系统 proxy，可能较慢，超时给足 180s+）
git clone https://github.com/<org>/<repo>.git {{REPOS_DIR}}/<org>/<repo>

# 已存在 → 增量更新
git -C {{REPOS_DIR}}/<org>/<repo> pull

# 记录当前 HEAD（供 Refresh 增量基线）
git -C {{REPOS_DIR}}/<org>/<repo> rev-parse HEAD
```

网络走 proxy（环境变量 `http_proxy=127.0.0.1:8118` 已设置，git 自动读取）。

#### 4. 执行分析（标准 repo-map 流程）

```bash
# 初始化 run（本地 clone 路径）
python3 $HARNESS/refresh_state.py init --repo {{REPOS_DIR}}/<org>/<repo> \
  --out {{REPO_MAP_HOME}}/runs/<name>

# Op1 门控
python3 $HARNESS/gates.py g1 --repo {{REPOS_DIR}}/<org>/<repo>
... g2..g5 ...

# Op2-Op5 按 playbook 逐个执行
```

#### 5. 记录映射（URL ↔ 本地 clone）

- `analysis_index.project_path` = **远程 URL**（统一标识，跨项目去重）
- `project_baselines.repo_path` = **本地 clone 路径**（Refresh 增量基线）
- 分析产物 `analysis_path` 写入 work-log

#### 6. 清理

- **不清理**（持久缓存，支持 Refresh 增量复用）
- 仅当磁盘紧张时才删 `{{REPOS_DIR}}/` 下已不再跟踪的项目

#### 分支 B — 论文条目（source_type='arxiv'/'blog'）：全部表面分析 + 高价值深挖

**所有论文都要"看"**——waitlist 只是中间登记态，**不是"没看过就跳过"的终点**。
但**不是全部深挖**——awesome 列表可能含几百篇论文，全量 webfetch 全文成本不可控。
分级：**每篇论文都做表面分析**（读摘要 → 提取核心机制 → 映射范式 → 判断价值 →
入库），其中**高价值 / 命中惊喜信号 / 命中缺口的升级为深挖**（webfetch 全文）。

> **waitlist ≠ 看过**。一篇论文只有在**表面分析完成**（core_functions 是真读摘要
> 提炼的机制描述，不是从 awesome 列表搬来的标题）后，才算"看过了"。停在 waitlist
> 而未做表面分析的，是**未处理项**，必须全部处理，不允许跳过。

##### 分层规则（全部论文都做第 1 层，命中的再升第 2 层）

| 层级 | 范围 | 动作 |
|------|------|------|
| **1. 表面分析**（每篇必做） | **全部论文** | webfetch 摘要 → 提取核心机制 → 映射 paradigm → 判断价值 → 写 core_functions/机制 + value_score 组件 + 惊喜扫描 |
| **2. 深挖**（第 1 层命中才升） | 高价值（value≥阈值）**或** 命中缺口（gap_paper）**或** 命中惊喜信号 | webfetch 全文 → 方法原理 → 差异对比 → 可复用原子能力 → 更新缺口闭环 |
| 不深挖但已看过 | 表面分析完成 + 未命中深挖条件 | core_functions 已记录机制，status 保持 'waitlisted'（登记态，可被未来惊喜扫描/缺口升级） |

**覆盖率要求**：**全部论文**必须完成第 1 层表面分析（每篇都真正读过摘要并提取机制
入库）。**只有第 2 层深挖是选择性的**（按价值/惊喜/缺口筛选）。绝不允许"一篇论文
停在 waitlist 而未做表面分析"。

##### 表面分析流程（每篇论文必做）

1. **webfetch 抓摘要**：`webfetch <arxiv_url>` → 读摘要全文
2. **提取核心机制**：从摘要提炼**底层机制**（算法/方法/框架/评测），这是"看过"的
   标志——`core_functions` 必须是机制描述，**不得**只是复制标题
3. **范式映射**：机制 → A-axis paradigm_id
4. **价值判断**：写入 5 个评分组件（gap_fill / paradigm_relevance / novelty /
   atomic_value / maintenance）→ 计算 `value_score`
5. **惊喜扫描**（见下）——命中则标记待深挖
6. **入库**：UPSERT `analysis_index`（core_functions=机制 + 组件 + status）

##### 惊喜扫描（表面分析时对每篇论文顺手做，成本低）

**惊喜 = 预判不到的意外价值**。深挖判定**不只看命中已知缺口**，还看 4 个惊喜信号：

1. **机制新颖性**：从摘要提取的核心机制，对比已分析资产（`analysis_docs` +
   `analysis_index`）——**该机制不存在/未分析过** → 惊喜（novelty 维度在论文层复用）
2. **跨范式跳跃**：论文机制横跨 ≥2 个 A-axis 范式（如 A2 RAG + A4 知识图谱）——
   **跨范式组合往往是惊喜来源**（新能力涌现处）
3. **影响力信号**：高引用 / 高 star / 出现在多个 awesome 列表重复收录——未被分析
   的高影响力论文 → 惊喜（"很多人关注，我们却没看过"）
4. **方法独特性**：标题含**具体方法词**（特定算法/架构/损失函数/评测名），非通用综述
   ——具体方法比泛泛综述更可能藏着可沉淀的原子能力

**判定**：命中**任一**信号 → 升级深挖。全未命中 → 保留表面分析结果。
惊喜扫描本身是**规则判断**（关键词 + 对比已分析），不触发深挖流程，成本 ≈ 表面分析。

##### 深挖判定（gap_paper 或 惊喜命中）

```sql
-- A. gap-paper：论文机制 → 映射 paradigm_id → 查未填缺口
SELECT item_id, kind, description, fill_progress
FROM project_open_items
WHERE domain='<paradigm_id>' AND status='discovered' AND fill_progress < 1;
-- 论文明确解决某缺口 → 判定 gap_paper，进入深挖

-- B. 惊喜命中：机制新颖（不在 analysis_docs/analysis_index）→ 跨范式 → 高影响力
--   → 方法独特 → 任一命中即深挖（见「惊喜扫描」规则）
```

##### 深挖流程（高价值 / gap-paper / 惊喜命中的论文）

1. **webfetch 抓全文**：`webfetch <arxiv_url>` → 提取方法/结果/贡献（表面分析已抓过
   摘要，深挖需更完整的方法与实验结果）
2. **提取机制**：从摘要提炼**底层机制**（算法/方法/框架），映射到 A-axis paradigm
3. **缺口映射**：查 `project_open_items` 该 paradigm 未填缺口，判断论文补了哪个
4. **深入分析**：方法原理 + 与已有方案的差异 + 可复用的原子能力 + 论文支撑
5. **更新缺口闭环**：命中缺口 → `UPDATE project_open_items SET
   status='analyzing'/'filled', fill_progress=?, filled_by_project='<paper>'`
6. **记录**：`analysis_index.status='analyzed', n_gaps=?, n_opportunities=?`

> **惊喜优先**：gap-paper 深挖推进缺口闭环；惊喜论文深挖则**优先沉淀为新原子能力
> / 新范式证据**（写入 work-log），二者都计入 novelty 去重基准。

##### 表面分析完成但未深挖的论文（已看过）

- `core_functions` 已记录表面分析提炼的机制（真读摘要产物），status 保持 'waitlisted'
- **这是"已看过"状态**：机制已入库、可被 novelty 去重、可被未来缺口出现时重新映射、
  可被未来惊喜扫描再次命中时升级深挖
- 与"未做表面分析"的论文**区分**——未处理的必须补做表面分析，不允许停在空 waitlist

##### 与既有论文综述资产的关系

- 已分析过的论文（analysis_docs 里 46 篇综述/浅析，如 Paperclip/Reverify/kagent）——
  作为 novelty 去重基准，避免重复深挖同类论文
- 深挖产出的论文综述写入 work-log（Op5 流程），与既有论文综述资产同目录

### Gates（awesome-list mode）

- **G1 (analyzable)**：README 存在 + 有内容 → PASS
- **G3/G4**：跳过（不是代码生成 AGENTS.md 的流程）
- **G5**：不适用
- **推荐门控**：确认点必须走——推荐清单未获用户确认前，不开始逐个分析

### 复用

- 条目解析复用 `verify_urls.py` 的正则模式
- 结构化 schema 参考 `external_agent_collections.json`
- 输出模板参考 `AWESOME_AI4S.md` 的 per-project 字段格式

- **Generic content** — remove anything that applies to ALL projects.
- **Verbose style** — telegraphic or die.