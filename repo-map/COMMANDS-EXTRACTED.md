# 你的完整分析指令集（从 2000+ 会话穷尽提取）

**来源**: DB 全扫 — `[search-mode]`×4801, `[analyze-mode]`×1664, `<auto-slash-command>`:
`/init-deep`×4271, `/plan`×2347, `/handoff`×22, `/code-review`×15, `/refactor`×2。
**固定指令模板 — 全库语义唯一，无变体。**（提取于 2026-09-15）

---

## 三操作核心分析工作流

对一个**新开源项目**，你的完整分析 = 三种操作：

```
repo-map
├── 操作1  /init-deep         → 结构知识库（递归 AGENTS.md）  ✅ harness G1-G5 门控
├── 操作2  项目画像            → 核心功能清单 + 应用场景 + 核心亮点/优势
└── 操作3  迭代对比研究        → 性质分流(竞品/论文/领域综述)
                              → 2-3轮迭代 + 防幻觉剥离广告 + 抠底层机制/论文
                              → 横向+纵向对比 → 真优势/真区别(辨识度+可搜)
                              → 沉淀复用 (原子能力 + 项目参考)
```

## 操作1 · `/init-deep` — 层级知识库（×4271）

**4阶段，逐阶段 TodoWrite。** 已由 harness G1-G5 门控固化。

**Discovery**：6 固定 explore（structure/entrypoints/conventions/anti-patterns/build-CI/tests）
+ **动态扩展**（每100文件+1 / 每10k行+1 / 深度≥4 +2 / 大文件>10 +1 / monorepo +1/pkg / 多语言 +1/lang）
+ bash 结构普查 + 读现有 AGENTS + LSP codemap。→ **Gate G1 可分析**

**Scoring**：8 因子加权计分（文件数3x/子目录2x/代码比2x/独特模式1x/模块边界2x/符号密度2x/导出数2x/引用中枢3x）
→ Root恒建 / >15建 / 8-15独立域建 / <8跳过。→ **Gate G2 栈**

**Generate**：根 AGENTS.md 50-150行模板 + 子目录 task(category=writing) 30-80行、绝不重复父。
文件规则：存在→Edit，否则→Write。→ **Gate G3 产出 + G4 结构**

**Review**：去通用/去重复/裁剪/电报校验。→ **Gate G5 构建(SKIP可记录)**

## 操作2 · 项目画像（核心功能清单 + 应用场景 + 核心亮点）

用户原话（DB 实证）:
- 「这个项目的核心功能，到底解决了什么问题，有什么优势，和taster-skill做一个深度全的对比」
- 「优势是谁，应用场景是谁，核心解决的问题是啥，这些怎么都没有」← 用户会因缺失而斥责
- 「给出项目功能的完整介绍，包括核心应用场景和替代场景，核心优势，系统架构」
- 「给出本项目功能和核心架构的完整介绍，以及应用场景全集，特别是擅长的应用场景」

**必答维度契约**（缺一被拒）: `定位/解决的问题` + `核心功能清单(代码实证)` +
`核心优势(机械可验证)` + `应用场景全集(编号+擅长/最佳/替代/不适用)` +
`架构/技术栈` + `生态/成熟度` + `竞品对比(要结论)` + `一句话定位`

**过程**：并行 explore(代码实证) + librarian(外部/竞品) + 直接 codegrounding → 合成为
`<project>-功能分析.md`。**内容门控**：每功能须有 code 锚点（路径+计数），无锚点=广告剔除。

## 操作3 · 迭代对比研究（分化项）

**3.1 性质分流**：平台/架构 → 竞品深挖；能力/关键技术 → 竞品 + 论文深析；
领域知识高价值 → + 单点综述。用 Op1/Op2 实证判定，非 README 标签。

**3.2 多轮迭代（2-3轮到清晰）**：每轮只挖新缺口/新能力，不重读已定论。
librarian 超时 → 原样重发（"re-deliver complete structured markdown"），绝不凭记忆猜。
建矩阵前用 `question` 工具跟用户确认对比轴/场景分类，不臆断。

**3.3 防幻觉（核心纪律）**——每个功能宣称逐层追问:
```
1. 有无真实底层机制? (抠到 API/算法/协议/内核最底层)
2. 有无论文支撑?     (能引论文/公开推导)
3. 与竞品机制层面真不同?
   ─ 任一不过 = 广告语 → 剔除  ； 全部通过 = 真实能力 → 晋升原子能力
```
**机制**（real-session 实证）: self 用 `gh api` 拉权威数、合并后 `ctx_memory` 冻结、
关键点三方交叉验证、研究 agent 强制 `verifiable facts + cited URLs`、
"no public evidence → say so" 时限化、用户纠错→按用户确认规格重gener、
同族 fork/port 标 `⚠️ 同一家族`。

**3.4 对比定级（获得底层实现之后才做）**：先抠底层→再横向(同层) + 纵向(上下游)。
固定 10 维竞品画像模板 + 8 维对比矩阵（**刻意不按 star 排序**，正交维度）。
**GraphRAG vs LightRAG 标杆**：同标签项目不可停在"都做X"，须拆构图差异/检索机制/
真实增量/何时选谁，输出带技术关键词+论文标题 = 辨识度 + 可搜性。

**3.5 沉淀复用**：验证过的真实能力 → **可复用原子能力**；跨项目参考模式 →
**项目参考能力**。产出 `COMPARISON.md` + `ATOMIC-CAPABILITIES.md`。

---

## 探索编排（search-mode / analyze-mode，贯穿三操作）

### `[search-mode]`（×4801）—— 穷尽并行
```
并行多路后台 agent（explore 代码模式/结构 + librarian 远程文档/GitHub例子）
+ 直接工具（Grep/ripgrep/ast-grep）
铁律：NEVER stop at first result - be exhaustive
```

### `[analyze-mode]`（×1664）—— 深潜前聚境 + 复杂度升级
```
并行聚境（1-2 explore + 1-2 librarian[外部库] + Direct: Grep/AST-grep/LSP）
IF COMPLEX - DO NOT STRUGGLE ALONE → 常规Consult Oracle / 非常规Consult Artistry
SYNTHESIZE findings before proceeding
强制委托参数：delegate_task(..., run_in_background=true, load_skills=[])
```

### 确认交互编排 —— 自主性分级（贯穿所有操作）
```
遇确认点按此定则，不停在能自己定的、不自动定不能定的:
1. 有推荐默认 → 证据(代码锚/taxonomy bin/缺口库/先前分析)明确偏向某分支
   → 直接走推荐继续, 记录 decision+reason 供审计
   (e.g. `auto: paradigm A2 via WeKnora/bin reuse — continue`)
2. 无推荐/真歧义 → 两分支同等成立且证据不占优 → 停下问人工
   → 呈现选项+各自影响, 确认后继续剩余步骤(不重开不放弃)
3. 既定流程动作不是确认点 → Op5 持久化推送是【强制收尾】: 用户跑 /repo-map
   即已隐式授权 commit+push, 跑完 1-5 直接推, 绝不把"是否推送GitHub"当问题问。
   只有【计划外】不可逆动作才必问: 删不在本run产物清单里的已有文件、
   覆盖非本run产生的先前 paradigm/gap 记录
```

### 其他 @slash（低频）`/plan`×2347, `/handoff`×22, `/code-review`×15, `/refactor`×2

---

## 归并结论

`search-mode`（探索）→ `analyze-mode`（聚境升级）驱动 Op1/2/3 的每一步并行派发；
`/init-deep` 是 Op1 的生成规约；Op2/Op3 是你要的**产品级画像**与**对抗幻觉的迭代对比研究**。
你的完整分析工作流 = **这三操作 + 贯穿的 search/analyze 编排**。