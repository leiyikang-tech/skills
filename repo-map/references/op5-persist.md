# Op5 — Knowledge Asset Persistence playbook

Goal: turn every analysis operation's output (Op1 knowledge base, Op2 profile,
Op3 comparison/atomic capabilities, Op4 gaps/opportunities) into **durable,
indexable knowledge assets** — distinctive named files, persisted to the shared
GitHub knowledge repository. This is how analysis becomes a reusable library,
not a pile of finished-and-forgotten runs.

Grounded in real sessions: file naming patterns and the `git add / commit /
push origin main` chain observed across the work-log knowledge repo.

Read this file when Op5 starts.

---

## The shared knowledge repository (target)

- **GitHub:** `{{KNOWLEDGE_REPO_URL}}`
- **Canonical local clone:** `{{KNOWLEDGE_REPO_DIR}}` (most current; the
  source of truth for new writes before push)
- **Also mirrored at:** `{{KNOWLEDGE_REPO_DIR}}`, `{{KNOWLEDGE_REPO_DIR}}`
  (separate clones of the same remote)
- ⚠️ The remote URL contains an **embedded PAT token — never echo it**
  in output, prompts, or logs.
- Push flow: work in `{{KNOWLEDGE_REPO_DIR}}` (or a temp clone like
  `/tmp/work-log-clone` / `/tmp/work-log`), then `git push origin main`.

## Domain taxonomy (top-level dirs in the knowledge repo)

File into the matching topic dir from the existing structure:
```
安全 / 本体工程 / 记忆和进化 / 具身智能 / 前端框架 / 软件工程 / 深度研究 /
数据和知识清洗 / 推理优化 / 信息源 / 智能体框架 / 资源和数据源 / agentos /
AI功能分析 / AI协作分析 / aiapp / cangjie-skill / channel / coding / data /
demo / devops / hermes-mastered / hermes-harness / mcp / office / skills /
skillsos / text2sql / tools
```
New analysis → create a topic dir if none fits, else reuse an existing one.

## 专用目录 — 缺口分析统一观察点

**缺口分析文档**（文件名含"缺口和机会分析"或"缺口分析"）不放主题目录，
统一写入 **`缺口分析/`** 专用目录。这是跨项目统一观察和对比的入口：

- `缺口分析/clodds的缺口和机会分析.md`
- `缺口分析/WorldSculpt的缺口和机会分析.md`
- `缺口分析/rune作为开发环境工具的缺口和机会分析.md`

**为什么需要专用目录**：散落在各主题目录（`智能体框架/`、`3D重建/`、`tools/`）
的缺口分析无法统一观察和对比。集中到 `缺口分析/` 后：
- 一目了然所有项目的缺口全貌
- 新技术来了扫描此目录 → 跟踪缺口是否被填充（与 Op4 的 `project_open_items` 闭环）
- 跨项目对比同类缺口（如多个项目的"推理能力不足"缺口）

**识别规则**：文件名匹配 `*缺口*` 或 `*缺口和机会*` → 写到 `缺口分析/`。
其他分析文档仍按主题域散落存放。

## Naming — distinctive + searchable (the core demand)

A filename must encode enough to be located by a later search, with the analysis
type and the subject clearly named. Real examples:

```
<domain>/<project>作为<capability>的<分析类型>.md
```
- `推理优化/幻觉/Reverify阻止AI自说自话地的过度自信的综述分析.md`
  (project=ReasonVerify, capability=提示词防御, type=综述)
- `本体工程/semantica/okf-rs作为代码到本体的竞品分析.md`
  (project=okf-rs, type=竞品)
- `agentos/kagent功能分析和agent工程完整功能清单和论文浅析.md`
  (project=kagent, type=功能清单+论文)
- `推理优化/distillation/distilly作为个人心智模式和行为蒸馏的分析.md`
- `本体工程/数据库/ontop应用与数据库到语义和知识图谱的转换全景分析.md`

Pattern rule: **`<subject>作为<role>的<analysis-type>`** or
**`<subject>的<analysis-type>`** — always name the subject + the analysis kind
(分析/综述/竞品/对比/全景/清单/缺口), never a bare "analysis.md".

**缺口分析文档**（写入 `缺口分析/` 专用目录）的命名：
```
缺口分析/<project>的缺口和机会分析.md
```
- `缺口分析/clodds的缺口和机会分析.md`
- `缺口分析/WorldSculpt的缺口和机会分析.md`
- `缺口分析/rune作为开发环境工具的缺口和机会分析.md`

**生态全景文档（生态地图 — 独立 landscape）**的命名（仅按需创建，见 op3）：
```
<domain>/<paradigm>-landscape-<paradigm>生态全景-<YYYY>.md
```
- `text2sql/data-formulator/data-agent-landscape-数据智能体生态全景-2026.md`（现有先例）
- `智能体框架/agent-harness-landscape-智能体编排生态全景-2026.md`（示例）
属于生态级综述，放入匹配的 `<domain>` 主题目录（不是 `缺口分析/`，也不是单项目文档）。
完成报告「应用建议·生态地图」要素引用此文档路径。

## Persistence workflow (real command chain)

For each deliverable produced by Op1–Op4:

```bash
export GIT_EDITOR=: EDITOR=: VISUAL='' GIT_SEQUENCE_EDITOR=: GIT_MERGE_AUTOEDIT=no
export GIT_TERMINAL_PROMPT=0 CI=true GIT_PAGER=cat PAGER=cat
W={{KNOWLEDGE_REPO_DIR}}

# 1. copy the deliverable into the matched topic dir under a distinctive name
cp "<deliverable>" "$W/<topic>/<project>作为<role>的<analysis-type>.md"

# 2. stage + show what will commit
cd "$W" && git add -A && git status --short      # verify only intended files staged

# 3. commit with a scoped message
git commit -m "docs(<category>): <what + project>"   # e.g. "docs(本体工程): okf-rs 竞品分析"

# 4. push with a real exit-code check (don't swallow failure)
git push origin main 2>&1 | tail -8
echo "PUSH_EXIT=${PIPESTATUS[0]}"    # reuse the pattern: capture the chain's real code
```

Commit style observed: `docs(<topics>/<subcat>): 主题短语` — terse, scoped, descriptive.

## Operational rules

- **Work in a single canonical clone** (`office/work-log`) to avoid divergent
  histories across the mirrored clones. Commit + push from one place.
- **Index alongside**: if the store is the shared DB, also record the asset in
  the analysis registry so it's discoverable by field — name the file in the
  gap/opportunity `suggested_sources` or as the source of an atomic capability.
- **Git hygiene**: never push secrets (the embedded PAT is already a known
  concern; don't add more). Don't commit `__pycache__`, temp clones, run.json.
- **One distinctive file per deliverable**, not a mega-dump — indexable ==
  one-subject-per-file with a searchable name.

## Deliverables (Op5 gateway)

- Every Op1–Op4 artifact written into the work-log knowledge repo under a
  distinct, subject+analysis-type name.
- Committed with a scoped `docs(<category>): ...` message and pushed, with the
  real push exit code verified.
- Cross-indexed: cap types nameable from the store (e.g. the atomic-capability
  register's source = this file).

## Execution summary (MUST output after every Op5 run)

Every Op5 run ends by printing a structured summary covering three items.
**Do not skip or compress this** — it is the user-facing proof of the run.

```
═══ repo-map Op5 完成 ═══

生成文件：
  - <domain>/<project>作为<role>的<analysis-type>.md
  - <domain>/<project>的<analysis-type>.md
  - ...

上传位置：
  - {{KNOWLEDGE_REPO_URL}}/<domain>/<filename>
  - ...

项目核心亮点：
  - <核心亮点 1>（来自 Op2 profile 的 highlights）
  - <核心亮点 2>
  - ...

═══ 完成 ═══
```

Rules for the summary:
- **生成文件** = every distinctive `.md` produced by this Op5 run, named with
  the `subject+analysis-type` convention above.
- **上传位置** = the work-log repo path (`<domain>/<filename>`) + the remote
  URL prefix (`{{KNOWLEDGE_REPO_URL}}/`). Do NOT echo the PAT.
- **项目核心亮点** = the 2-4 most distinctive findings from Op2 profile
  (core functions, key advantages, what makes this project stand out).
  If Op2 was not run in this session, derive highlights from Op3 comparison
  (what makes this project different from competitors).
- **应用建议三要素指针（方案A：三要素拆开落位）** = 完成报告里的「应用建议」三要素
  各自引用其**完整载体文档**，而非在报告内重复全文：
  ```
  应用建议（摘要 + 指针）:
   生态地图 → <domain>/<paradigm>-landscape-<paradigm>生态全景-<YYYY>.md   （完整生态地图在此）
   生态位置 → <domain>/<project>的<分析类型>.md §七 生态位置             （单项目定位在此）
   关键缺口 → 缺口分析/<project>的缺口和机会分析.md                        （完整缺口分析在此）
  ```
  - **生态地图**：如本 run 新建了 landscape 文档则指向它；否则指向该 paradigm 已有的
    landscape 文档（不重复写）。
  - **生态位置**：指向本项目的单项目分析文档（Op2 §七）。
  - **关键缺口**：指向 `缺口分析/<project>的缺口和机会分析.md`（Op4 已写入的专用目录）。
- **No pending confirmations** must be printed (if any, report them instead).

## Analysis index sync (awesome-list mode)

For every project analyzed in awesome-list mode, **UPSERT `analysis_index`**
and push the index to the work-log repo. This makes the analysis board
durable and discoverable across sessions.

### Per-project UPSERT

After each project analysis completes, execute via Python
(busy_timeout + BEGIN IMMEDIATE protect against concurrent writes):
```python
import sqlite3, datetime
DB = "{{ANALYSIS_DB}}"
con = sqlite3.connect(DB, timeout=10)
con.execute("PRAGMA busy_timeout = 10000")   # wait up to 10s on lock
con.execute("BEGIN IMMEDIATE")               # acquire write lock now
try:
    con.execute(
        """INSERT INTO analysis_index
           (project_path, project_name, source_list, stars, category,
            analyzed_at, analysis_path, status, n_gaps, n_opportunities)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(project_path) DO UPDATE SET
             analyzed_at=EXCLUDED.analyzed_at, status=EXCLUDED.status,
             analysis_path=EXCLUDED.analysis_path,
             n_gaps=EXCLUDED.n_gaps, n_opportunities=EXCLUDED.n_opportunities,
             last_updated=datetime('now')""",
        (project_url, name, list_name, stars, category, now, path, "analyzed", n_gaps, n_opportunities))
    con.commit()
except sqlite3.OperationalError as e:
    con.rollback()
    if "locked" in str(e):
        # retry once after brief sleep
        import time; time.sleep(1)
        # ... retry logic ...
        raise
finally:
    con.close()
```
`BEGIN IMMEDIATE` acquires the write lock up-front — other writers block
instead of getting `database is locked`. `busy_timeout=10000` means a
waiting writer waits up to 10s rather than failing immediately.

### Commit + push the index

After all projects in the run are indexed:
```bash
cd {{KNOWLEDGE_REPO_DIR}}
git add -A
git status --short
git commit -m "docs(analysis-index): 更新分析索引 (<N> projects)"
git push origin main 2>&1 | tail -5
echo "PUSH_EXIT=${PIPESTATUS[0]}"
```

The `analysis_index` table is the **master analysis board** — it tracks
which projects are pending/analyzed/failed, their star ranking, associated
gaps/opportunities (n_gaps/n_opportunities), and links to analysis artifacts.
New awesome-list runs start by querying `v_analysis_pending` to find what's left.

## Guardrails

- Don't upload without the analysis being **gated** (Op2 content gate + Op3
  anti-hallucination + Op4 citation rule must have passed first — uploading a
  fluff-free asset is the whole point).
- Don't commit locally and forget to push; the asset doesn't exist until it's
  on the shared remote.
- Don't create a new topic dir for a one-off when an existing dir fits.