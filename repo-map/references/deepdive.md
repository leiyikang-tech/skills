# deep-dive mode — 两本体 + 外部锚定的深入分析

**目的**：当看到高价值项目/方向时，做比标准 Op1-Op5 更深的分析。deep-dive
不是"再分析一次"，而是**把每个判定节点都锚定到现实依据**——概念必须
grounding 到 Wikidata QID、引用必须 URL 解析通过、原子价值必须从真实代码
符号计数、收敛必须 SQL 可查、自我改进必须有回归测量。**消灭所有依赖"LLM
主观判断"的节点**。

**核心转变**：deep-dive 的目标从"分析一个项目"升级为**构建并验证两本体**——
每层深挖都在往两本体的对应格子里填充**经外部锚定验证过**的知识。

---

## 两本体（落盘 board DB `{{ANALYSIS_DB}}`）

应用 schema（幂等，已应用过会安全跳过）：

```bash
sqlite3 {{ANALYSIS_DB}} ".read references/deepdive.sql"
```

| 表 | 归属 | 存什么 | grounding 字段 |
|----|------|--------|---------------|
| `deepdive_concepts` | **关键概念本体** | 概念名 + 底层机制 + paradigm + wiki 链接 | `wiki_qid` + `grounding_status`（`grounded`/`partial`/`not_found`/`hallucination`） |
| `deepdive_citations` | 引用层 | 每条断言引用的 URL + 校验结果 | `verify_status`（`unverified`/`resolves`/`broken`/`not_found`） |
| `deepdive_methods` | **思维本体** | 每次深挖的方法论（Mem0 procedural 结构：objective/actions/findings/errors） | `layer` |
| `deepdive_findings` | 思维本体 | 跨层累积的关键发现（可查询） | `citation` + `grounded_qid` + `verified` |
| `deepdive_errors` | 思维本体 | 错误模式（防复发） | `error_type` + `recurring` |
| `deepdive_runs` | 运行审计 | 每层运行的产出计数 + 收敛标记 | `layer` + `converged` |

**harness 脚本**（`{{REPO_MAP_HOME}}/harness/`，全部 stdlib-only 确定性）：

| 脚本 | 功能 | 对应节点 | 调用 |
|------|------|---------|------|
| `wikidata_ground.py` | 概念 → Wikidata QID（SPARQL） | 概念 grounding | `--concept <name> [--lang] [--db] [--project]` |
| `citation_check.py` | 引用 URL 解析校验 | 引用验证 | `--url <url> [--type] [--db] [--project] [--concept]` |
| `atomic_score.py` | 真实 clone 代码符号计数 | 原子价值 | `--repo <dir> [--db] [--project]` |
| `convergence.py` | SQL 收敛判定 | 停止条件 | `--project <path> [--db] [--update]` |
| `regression_check.py` | 自我改进回归测量 | 改进验证 | `--project <path> [--db] [--before-layer N]` |

---

## 触发

- 用户显式 `/deep-dive <项目|方向>`
- awesome-map 深挖阶段对 top 高价值项目自动升级
- 分析中发现值得深入的概念/方向（surprise 信号命中）

---

## 流程（逐层，每层内嵌外部锚定）

```
deep-dive <项目/方向>
  ↓
══ 阶段 0：基线（标准 repo-map + 两本体上下文）══
  · 标准 Op1-Op5 跑一遍，得到 paradigm (A-primary) + 生态位置 + 缺口
  · 加载两本体上下文：查 deepdive_concepts + deepdive_findings 已有概念/发现
    → 避免重复造、避免 novelty 误判
  · 记录 deepdive_runs 第 1 层基线
  ↓
══ 阶段 1：逐层深挖（每层四齿轮 + 外部锚定）══
Layer N:
 ① 关键概念探索（替换"理解了没?"）
    · 从代码/文本提取概念名
    · wikidata_ground.py --concept <name> → grounding 到 QID
    · grounding 判定：grounded/partial → 采纳；not_found → 标记待补；
      hallucination → 拒绝写入（概念名过短/通用词，如 <3 字符/abstract/framework）
    · 写入 deepdive_concepts（每条带 wiki_qid + grounding_status）
 ② 深度搜索补全（填知识缺口）
    · DISPATCH.md 按 paradigm 派发 · librarian/webfetch 深搜
    · anti-hallucination：每条结论必须能 cite 到底层机制 + 证据
 ③ 缺口分析确认（写缺口板）
    · CLAIM 已存在缺口（needer=本项目）· INSERT 新缺口（"可引用才落盘"）
 ④ 确认协议 + 思维本体累积
    · 规则1 有推荐自动采纳 / 规则2 无推荐问 / 规则3 计划内不问
    · 本层方法/发现/错误 → 写 deepdive_methods + deepdive_findings + deepdive_errors
    · 每条发现必须带 citation，且 citation 必须 citation_check.py 通过
  ↓
  收敛判定（SQL 可查）→ 未收敛 → Layer N+1
  ↓
══ 阶段 2：递归自我改进 ══
  · 本层学到的概念盲点/搜索盲点/缺口误判 → 更新思维本体（deepdive_errors.lesson）
  · 对"分析协议"（op playbook）提出改进 → 必须先通过 regression_check.py 验证
    （AFTER 复发率 < BEFORE 复发率才算改进）否则不采纳
  ↓
══ 阶段 3：完成报告（复用 repo-map ═══ 块 + Q-gate）══
  · 两本体增量：关键概念本体 +N 概念 / 思维本体 +M 方法论记录
  · 分类归属 + 应用建议(三要素) + 操作建议 + Q1-Q5 verdict
```

---

## 每齿轮的外部锚定规则（本模式的核心契约）

### ① 概念 grounding（消灭"我理解了"的自证）
- 判定"概念理解到位"**不是 LLM 自评**，而是：`wikidata_ground.py` 能否把概念
  解析到真实 Wikidata QID。
  - `grounded`（精确 label 匹配）→ 采纳，概念可进本体
  - `partial`（模糊/子串匹配）→ 采纳但标记待人工复核
  - `not_found`（无实体）→ 不删，标记待补（可能概念过新或拼写异）
  - `hallucination`（过短/通用词）→ **拒绝写入**（这是 LLM 幻觉的典型形态）
- **写入 deepdive_concepts 前必须有 grounding 结果**。无结果（网络错误）→ 本轮
  暂不写入，不猜。

### ② 引用验证（消灭"有论文/机制支撑"的断言）
- 每条"有支撑"的结论都必须先过 `citation_check.py --url <url>`。
  - `resolves`（最终 200）→ 信任
  - `broken`（4xx/5xx）→ 剔除该引用，标注
  - `not_found`（404/DNS）→ 剔除
  - `unverified`（超时/被 bot 挡）→ 保留但标记，不当作已核实
- **deepdive_findings 的 verified=1 仅当 citation 校验通过**。verified=0 的发现
  不进入"已确认知识"，只算"待核实假设"。

### ③ 原子价值（消灭"营销 vs 机制"的 LLM 判断）
- `atomic_score.py --repo <cloned_dir>` 从真实代码符号计数得出 `v_atomic`，
  替代 LLM 读描述主观判断。README 只提词不实现 → 低分；有真实 API/算法 →
  高分。

### ④ 收敛（消灭"差不多了"）
- `convergence.py --project <path>`：末层 n_concepts/n_findings/n_gaps_claimed/
  n_gaps_filled 全 0 = 收敛（复用 v_dd_convergence 视图）。单层不算（数据不足）。
- 不做"分数稳定/质量达标"这种无法核验的停止条件。

### ⑤ 自我改进（消灭"我改进了"的自夸）
- 任何对分析协议的改进，必须先过 `regression_check.py`：改进后（layer >
  before_layer）错误复发率必须**严格低于**改进前，否则 `NO_IMPROVEMENT` 不采纳。
- 无改进后数据 → `INSUFFICIENT_DATA`，不允许声称"已改进"。

---

## 数据流总结

```
外部世界 ──grounding──→ 两本体 ←──校验── 分析过程
  Wikidata  ──→ deepdive_concepts (wiki_qid)      ↑ 概念 grounding
  URL 解析  ──→ deepdive_citations (verify_status) ↑ 引用验证
  代码符号  ──→ analysis_index.v_atomic            ↑ 原子价值
  缺口板    ──→ project_open_items (gap_fill)      ↑ 缺口确认
  SQL 收敛  ──→ deepdive_runs.converged            ↑ 停止条件
  回归测量  ──→ deepdive_errors (recurring)        ↑ 自我改进
```

每一条写入本体的知识都必须有外部锚点（QID / resolves 的 URL / 真实代码符号 /
缺口板行）。**没有锚点的知识不进本体。**