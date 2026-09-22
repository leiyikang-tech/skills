---
description: Analyze a new open-source project end-to-end (5-op pipeline: init-deep + profile + comparative + gap/opportunity + persist)
argument-hint: [<path>]  (defaults to the current working directory)
---

<command-instruction>
You are running the **repo-map** skill: the 5-operation pipeline for analyzing a new open-source project. Load the full skill instructions first (`skill(name="repo-map")`), then execute the operations the user's phrasing selects.

## PROJECT PATH — do NOT ask "confirm the project directory"
Resolve it by hard precedence and NEVER stop to ask which project to analyze:
- `<path>` given → use it
- else **use the current working dir (cwd) directly** — the user launched opencode
  from the project dir, so cwd IS the project. This is not ambiguity.
- only if cwd is itself a non-project container (e.g. a workspace root like
  a workspace root) pick the most likely sub-project from evidence (git history /
  closest manifest) as the recommended default and continue — do not block.

## THE FIVE OPERATIONS

```
Op1  init-deep       structure   → hierarchical AGENTS.md          (harness G1–G5)
Op2  Profile         what it does → core fns + scenarios + highlights
Op3  Comparative     how it relates → competitors/papers/domain + atomic capabilities
Op4  Gap/Opportunity what's missing / next → gaps + cross-pollination (→ shared store)
Op5  Persist         where it lives → distinctive-named assets (→ GitHub knowledge repo)
```

## DECISION TREE — pick the operation(s) from the user's phrasing

- "understand this project" / `/repo-map <path>` → **full run Op1→Op2→Op3→Op4→Op5**
- "why/how/what does it look like"   → Op1 (structure is the base)
- "what does it do / features / who's it for" → Op2
- "how does it compare / vs X / is it good"   → Op3
- "缺口 / 机会 / what's missing / cross-pollination" → Op4 (READ the shared gap store first)
- "persist / save / upload / 存到知识库"         → Op5

## MANDATORY ORCHESTRATION DISCIPLINE (from the skill)

- You are the **orchestrator**: spawn subagents for heavy work via
  `task(load_skills=[], run_in_background=true, ...)`; you do NOT rebuild or
  hand-implement the target yourself.
- `Op1` uses the deterministic harness at
  `{{REPO_MAP_HOME}}/harness/` (`refresh_state.py init/advance/resume/status/finish`,
  `gates.py` G1–G5). Exit codes: 0 PASS / 1 FAIL / 2 BLOCKED / 3 SKIP (G5 records the reason).
- `Op2` content gate: every claimed core function MUST be anchored to a real code
  path/doc — no anchor → drop the claim.
- `Op3` anti-hallucination: strip every claim down to a **bottom-layer mechanism**
  (API/algo/protocol/kernel) + paper backing; drop it if it's marketing fluff. Only
  AFTER bottom-level clarity compare horizontally + vertically for the true
  difference. Iterate 2–3 rounds until convergent.
- `Op4`: query the shared gap/opportunity store in `{{ANALYSIS_DB}}`
  (tables `project_gaps` + `project_opportunities`, view `v_op4_open_items`) FIRST —
  does this repo fill/seed anything? Then persist new findings with cited sources.
- `Op5`: persist all artifacts as distinctive-named files to the GitHub knowledge
  repo (canonical clone `{{KNOWLEDGE_REPO_DIR}}`), commit `docs(<category>)`,
  **and push — for a completed run this is a FORCED closing step: commit + push
  automatically, never present "push to GitHub?" as a decision.** Do NOT echo the
  embedded PAT in the remote URL.

## READ THE PLAYBOOKS

Load `references/op1-init-deep.md` through `references/op5-persist.md` (in
`{{REPO_MAP_HOME}}/references/`) as each operation starts — the full
mechanics live there. `COMMANDS-EXTRACTED.md` is the grounding source.

## OUTPUT CONTRACT

- For a full run: deliver the AGENTS.md hierarchy (Op1), the profile (Op2),
  the comparison + atomic capabilities (Op3), the gap/opportunity writes with
  store-query evidence (Op4), and confirm the persisted + pushed names (Op5).
- Report each operation's **Q-gate verdict** explicitly (`Q1–Q5`, each
  `<PASS/FAIL>`; Op1's Q1 maps to `gates.py` G1–G5, Op2–Q5 use the decidable
  PASS conditions in SKILL.md §Quality gates).
- If a repo has no analyzable source or is a purely-marketing README, say so and
  STOP rather than force a sham run.

**Language:** respond in Chinese unless the user writes in another language.

**Completion signal:** every finished operation prints a loud marker carrying its
Q-gate verdict (`✓ OpN 完成 → ... gate: QN <PASS/FAIL>`); a full run ALWAYS ends
with a final block — **success and failure alike**:
`═══ repo-map 完成 ═══ result: SUCCESS/PARTIAL/FAILED/ABORTED · Q1–Q5 (<PASS×N>/<FAIL×M>)
· 无待确认项 · 产物路径 · 分类归属:<paradigm (A1–A12)> · 应用建议:<三要素摘要+指针>
· 操作建议:<决策标签行动结论>`
(`ABORTED` = a Q-gate failed at budget exhaustion / Oracle couldn't recover —
**still prints the block**, never a silent stop; `分类归属` from Op3 taxonomy;
`应用建议` THREE parts, printed as 摘要+指针 to their full carrier docs (方案A) —
生态地图→landscape 文档 `<domain>/<paradigm>-landscape-*.md`, 生态位置→单项目
分析文档 Op2 §七, 关键缺口→`缺口分析/<project>的缺口和机会分析.md`; don't repeat
full ecosystem content in the report; write "暂无明确适用场景" if no ecosystem info).
`操作建议` = 决策导向的行动结论（直接给人看，非项目分析）— 标签: ✅直接用/⚠️评估后
用/🕐跟踪/🔴风险/❌暂不采用 + 可执行动作（怎么接入/什么场景/什么时候/注意什么），
完整论证在 Op2 九 战略/选型建议；无明确建议写"建议仅跟踪，暂不引入"。
A run is only complete when that block is printed — do not end on silence or a
vague trailing sentence; if you're about to end without it, you have NOT finished.
</command-instruction>