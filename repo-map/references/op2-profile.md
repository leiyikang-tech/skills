# Op2 — Project Profile playbook (product-level view)

Goal: answer "what does this project honestly DO, for whom, and why is it
better" — a product-level profile of **core functions + application scenarios +
core highlights/advantages**. This is the lens AGENTS.md (structure) omits. The
user reaches for this with phrasings like:
「核心功能」「解决什么问题」「核心优势」「应用场景」「优势/应用场景/核心解决的问题怎么都没有」

Read this file when Op2 starts. Grounded in real profile sessions: Impeccable
vs taster-skill, Ante (8-section), Skillsmith (8-section), HelixDB (9-section).

## The non-negotiable dimension contract

Every profile MUST resolve all of these (a profile missing them gets rejected —
the user literally complained "优势是谁，应用场景是谁，核心解决的问题是啥，这些
怎么都没有").

| Dim | What it answers | Grounded evidence required |
|-----|-----------------|-----|
| 定位 / 解决的问题 | one-line thesis of what it is + the exact problem it claims to solve | from README + analysis, not tagline |
| 核心功能清单 | each capability enumerated | code-verified capacity counts (rules/engines/commands/skills), NOT adjectives |
| 核心优势 / 独特差异化 | what is genuinely unique | mechanically verifiable claim per point |
| 应用场景全集 | all scenarios, numbered; mark 擅长/最佳/替代/不适用 | a scenario list, not one vague "is used for" |
| 架构 / 技术栈 | layers, engines, pipeline, deps | code paths |
| 生态 / 成熟度 | version, providers/platforms, stars, tests, CI | public facts |
| 竞品对比 | feature-matrix comparison → concluded verdict | required when user asked 优势/对比/深度 |
| 一句话定位 | how you'd sum it up for a search | every profile gets one |

## Process (how real sessions actually did it)

### 1. Fire parallel background research agents
- `task(explore)` — codebase grounding: patterns, file structure, ast-grep on engine/registry/rule dirs.
- `task(librarian)` + `agent-reach` — external grounding: remote repos, official docs, GitHub, competitors.
- All `run_in_background=true`, `load_skills=[]`.

### 1.5 Read the source FIRST (the anti-fluff substrate)
Before ANY claim, build a symbol graph of the analyzed repo and read real bodies:
```bash
codegraph index <repo>          # build symbol graph (if not already indexed)
codegraph query <symbol>        # find a symbol + its body
codegraph callers <sym> / callees <sym>   # call-graph traversal (who calls / what it calls)
codegraph impact <sym>          # blast radius of a change
codegraph context "<task>"      # build code context for a task (markdown)
```
`codegraph` returns **verbatim symbol source grouped by file** — it is Read-equivalent,
so there is no excuse to fall back to README-level summaries. Adoption rule (from
codegraph's own contract): *"reach for raw grep/read only to confirm a specific
detail the symbol graph did not cover — don't grep first."* If codegraph is
unavailable for the language, fall back to `lsp_symbols`/`ast_grep_search` on the
2–3 most load-bearing units.

### 2. Direct codegrounding (verify every claim with file evidence)
`glob` / `grep` / `read` on: README.md, registry files, engine code, command dirs,
package.json, AGENTS.md. Count REAL capacities — e.g. "59 rules / 4 engines /
23 commands" (Impeccable), "~97 check_*.py" — never "a rich set of features".
Every capacity count must name its source file + line (see content gate below).

### 3. Synthesize into one standalone markdown deliverable
Filename pattern: `<project>-功能分析.md` | `<project>-应用分析.md` |
`<project>-深度分析.md`. Usually saved into a work-log/docs repo so it's reusable.

### 4. Content gate (anti-marketing) — THIS IS THE PASS/FAIL
Every claimed core function must be anchored to a real code path with a **`file:LINE`
proof** (path + line + capacity count). A bare `file + count` is not enough — the
line proves you actually read the mechanism, not just that the file exists.
No anchor → the claim is marketing → drop it.
"Clarify to bottom mechanism" applies when a claim is vague.

**Mechanical enforcement (Q2):** run the deterministic depth gate after writing
PROFILE.md:
```bash
python3 $HARNESS/depth_check.py --repo <repo> --out <out-dir> --min-anchors 5
```
This verifies every `path:LINE` anchor in PROFILE.md resolves on disk and flags
any mechanism-claim line with no anchor. FAIL → rework the profile (attempt budget
3), do not ship unanchored claims. `--min-anchors` scales with project size (≥5
for mid-size, ≥10 for large).

---

## Deliverable structure (use the richest 8-section model)

```
# <PROJECT> 功能 / 应用 / 深度分析
生成日期 + 基于提交(repo@commit)   ← always stamp provenance

一、项目总览
   定位(一句话) + 形态 + 模型支持 + 仓库/状态 + 设计哲学

二、核心功能清单                    ← CODE-VERIFIED
   · 功能1 —— 它做什么，干净表述
             证明: 代码路径/文件 + 能力计数 (rules/engines/commands/skills)
   · 功能2 —— …                             (每个都必须有锚点，无锚点=剔除)

三、解决什么问题                        ← pain → solution mapping
   [痛点] → [方案] 逐条对照，附机制证据

四、核心优势 / 独特差异化              ← mechanically verifiable claims ONLY
   · 优势1 —— 相对泛用替代的差异点（"零LLM确定性检测"，"17 provider pipeline"）
   · 每个优势都能用脚本/命令/code 复现验证，拒绝形容词

五、应用场景全集                       ← numbered, with 擅长/最佳/替代/不适用
   场景1 …… 最佳
   场景2 …… 用 / 替代 (此处 competitors 更合适)
   场景N …… 不适用 (诚实边界)
   加一个"最佳适用场景"一句话总结

六、架构 / 技术栈                      ← layers, engines, pipeline, deps

七、生态 / 成熟度 + 生态位置            ← version, providers/platforms, stars, tests, CI
   · 生态/成熟度：版本、平台、star、测试、CI（公共事实）
   · 生态位置：本项目在 paradigm 生态中处于哪一层（基础设施/框架/应用/工具-数据集）、
     它的上下游 / 替代 / 互补项目是谁、相对生态的成熟度与差异化（来自 Op3 对比）
     —— 这是完成报告「应用建议·生态位置」要素的**完整载体**

八、竞品对比（当用户要了 优势/深度/对比 时必须）→ feature-matrix 表，且给结论
   用 feature-matrix 表(维度在不同项目间对齐)，不是罗列。
   收尾必须是一个判定: "是/不是 真竞品" + 谁在哪个维度赢

九、诚实短板 + 战略 / 选型建议        ← obligatory: 优势诚实版 / 短板诚实版 + 一句话总结
   战略/选型建议即**操作建议的完整载体**，结构化给出给决策者的行动结论（完成报告
   的操作建议 = 本节的精炼行动版）。按决策标签组织：
   ✅ 直接用    —— 最佳适用场景（来自五 应用场景·最佳）+ 成熟度证据（版本/stars/测试/CI）
   ⚠️ 评估后用  —— 需先评估的点（license/集成成本/依赖稳定性/某项能力是否够）
   🕐 跟踪      —— 等什么时机或哪类缺口补上后再用（引用 Op4 project_open_items 未填项）
   🔴 风险      —— 短板/license 限制/维护风险/被更优替代的可能（来自九 短板诚实版 + Op3 对比）
   ❌ 暂不采用  —— 明确判死的情况（无真实机制/广告吹嘘/license 不可用）
```

Optional (for a deep profile): 学术论文索引 (papers backing the design), 工作流/应用能/不能评估, 适配工作量评估.

## Quality self-check before delivering
- [ ] every core function has a file-path + capacity-count anchor (no unanchored "advanced feature")
- [ ] 应用场景 is a **全集** (≥3, numbered), not a single sentence
- [ ] 优势 are mechanically verifiable, zero adjectives
- [ ] provenance stamped (date + commit)
- [ ] 短板 honest (the user distrusts hype — demonstrating honesty IS the credibility signal)
- [ ] one-line positioning present (satisfies "辨识度")