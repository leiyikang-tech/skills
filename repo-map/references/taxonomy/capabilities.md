# Capability Index (Axis C — Reusable Atomic Capabilities)

**Status:** seeding from existing work-log competitive analyses.
**Precedent:** research-kb `by-capability.md` (988 capabilities) — but that was
scientific-agent-specific; this index is the **cross-project** atomic-ability
register for the repo-map skill.

Each promoted Op3.5 capability is registered here. Tag format:
`{verb}-{object}-{mechanism}` — the *mechanism* is mandatory (it is the
anti-hallucination discipline: a capability without a named bottom-layer
mechanism is not a capability, it is a label).

---

## Register

| Capability tag | Paradigm (axis A) | Mechanism (bottom layer) | Paper / code anchor | First proven in |
|----------------|-------------------|--------------------------|---------------------|-----------------|
| merge-config-multifile-inherit-default | A1/A3 | three-state merge (absent→inherit, null→reset, value→override; objects recurse, arrays replace, "" is a value) | RSI-Harness src/harness/genome.ts mergeHarnessGenomeOverrides(152) | RSI-Harness |
| mutate-config-patch-operator | A1 | 28-arm patch switch, each op in validate+apply, output re-validated, auto re-stamp parent/genome_id from content hash | RSI-Harness genome.ts AGENT_HARNESS_PATCH_OPERATIONS(61)/applyHarnessPatch(818) | RSI-Harness |
| guard-config-surface-routing | A9/A1 | exhaustive routing guard test parses host .d.ts, any unrouted key fails red; host upgrade breaks first | RSI-Harness pi-surface.ts + test/pi-surface.test.ts | RSI-Harness |
| config-component-field-ownership | A1 | mutually-exclusive per-component field sets; out-of-bounds write fails at load | RSI-Harness genome-bundle.ts componentConfig | RSI-Harness |
| seed-never-overwrite | A7/A1 | content-hash + genome_id dual guard, all writes/refusals announced, never silent | RSI-Harness genome-loader.ts | RSI-Harness |
| project-settings-managed-keys-reset | A1/A7 | write only managed keys, precise clear on switch, "never clobber what we cannot read" | RSI-Harness settings-layer.ts | RSI-Harness |
| bundle-harness-portable-contract-seed | A1 | portable self-contained whole-dir bundle + load-time component-contract validation + user-edit-preserving seed lifecycle (three-pillar combo); 2026 framework survey confirms nobody else has all three (smolagents=bundle only, AutoGen=contract only, OpenHands=skills dirs+precedence) | RSI-Harness genome-bundle.ts + genome-loader.ts + genome.ts; cross-checked vs openai-agents-sdk/LangGraph/smolagents/OpenHands/AutoGen | RSI-Harness (independent 4-lens corrobation) |
| inspect-no-side-effect | A9/A1 | show/validate pass seedBuiltins:false, name lookup never triggers seed copy | RSI-Harness genome-command.ts | RSI-Harness |
| aggregate-session-to-config-evidence | A1/A3 | read multi-store, group by cwd, aggregate tool-call histograms, head-bounded reads, original-only-excerpt, never whole JSONL; return facts+keyword score | RSI-Harness session-sources.ts/harness-rsi.ts scanWorkspaces; near: Trace2Skill 2603.25158 | RSI-Harness |
| config-reuse-safe-via-guard-invariants | A1/A9 | two guard tests: default overrides nothing; full-surface routing reds on upgrade | RSI-Harness test/core-harness + test/pi-surface | RSI-Harness |
| self-config-approval-gate | A1 | nothing written until user approves full config as text; evidence bar; no-evidence keeps default | RSI-Harness genome-authoring instructions step6; near: SkillSmith 2606.01314 | RSI-Harness |
| materialize-config-multiformat-synced | A10 | unified profile → synced() wrapper rewrites multi-CLI native formats (settings.json/config.toml+auth.json/opencode.json/models.json/config.yaml/.env) on every change; hasNativeConfig(id) gates env-only vs file | agent-launcher src/main/ipc.ts synced() + native-config.ts; competitor survey: 6-CLI×5-format combo rare | agent-launcher |
| read-live-sqlite-wal-snapshot-merge | A10 | copy .db+-wal+-shm trio, parse WAL frames in commit order, feed sql.js/WASM — read another process's live SQLite session DB | agent-launcher src/main/sqlite.ts; forensics precedent: sqlite.org/wal.html + Hindsight | agent-launcher |
| install-only-if-missing-link-existing | A10 | re-detect first; binPath exists → linkExistingSystemCli; installStepsFor pure ordered fallback; zero update/repair/reinstall paths pinned by install-policy.test.ts | agent-launcher src/main/install/installer.ts installMissingCli + tests/main/install-policy.test.ts | agent-launcher |
| guard-launch-macos-codex-xprotect | A10/A7 | assertCliLaunchAllowed hard-fails any spawn/read of XProtect-flagged Codex (first spawn triggers false-positive dialog); reason derived from macosSecurityRisk, not persisted | agent-launcher src/main/cli-launch-safety.ts + install/codex-safety.ts + detect.ts | agent-launcher |
| generate-per-tool-adapter | A8/A1 | one core command surface → per-tool SKILL.md/command files via a factory, 30+ tool adapters from a single registry | OpenSpec src/core/command-generation/adapters/factory.ts + adapters/*.ts (30) | OpenSpec |
| order-artifact-dag-kahn | A8/A1 | Kahn topological sort over an artifact dependency DAG, ties broken by declaration order | OpenSpec src/core/artifact-graph/graph.ts | OpenSpec |
| detect-completion-by-file-existence | A8/A1 | task completion inferred from artifact file existence, not a state bit | OpenSpec src/core/artifact-graph/state.ts | OpenSpec |
| validate-spec-contract-rules | A9/A8 | rule set (Purpose non-placeholder, SHALL/MUST, Scenario, delta structure, task numbering) machine-checks spec quality at ERROR/WARNING/INFO | OpenSpec src/core/validation/validator.ts + task-checkboxes.ts/task-numbering.ts/purpose-placeholder.ts | OpenSpec |
| fold-change-delta-into-living-spec | A8 | git-tracked change → archive merges delta specs back into main specs, keeping specs living | OpenSpec src/core/archive.ts (~90KB) | OpenSpec |
| sync-tool-registry-multi-source | A1/A8 | one tool list kept in sync across 4+ places (config.ts/adapters/registry + command-references.ts) as a named maintenance hotspot | OpenSpec src/core/config.ts + registry.ts | OpenSpec |
| delta-only-spec-evolution | A8/A1 | describe only the change delta (ADDED/MODIFIED/REMOVED/RENAMED), not a full rewrite; brownfield-friendly | OpenSpec schemas/spec-driven/schema.yaml | OpenSpec |
| share-plan-via-git-store | A8/A10 | carry a shared openspec/ shape via plain git (registry + git mechanics), no dedicated server | OpenSpec src/core/store/git.ts + registry.ts | OpenSpec |
| select-query-by-judge-not-generate | A2 | deterministic regex groups (TIME/SOURCE/FILLER_PHRASES/FUNCTION_WORDS) pre-build candidates; LLM only CHOOSES query/entity/window/source among them, never free-generates → selection stays in rule bounds, testable, anti-hallucination | jev-search src/lib/candidates.ts buildCandidates + typesafe.ts inferIntent; near 2305.14283 | jev-search |
| merge-by-url-with-agreement-bonus | A2 | fold same canonical-URL results from multiple engines into one row (union engines, keep higher relevance + better position); engines.length as ranking tiebreak → cross-engine agreement = evidence | jev-search src/lib/merge.ts + rank.ts compareItems; near CombMNZ Fox&Shaw, Borda/Condorcet, RRF | jev-search |
| rerank-by-batched-llm-judge | A2/A9 | RERANK_BATCH=40 per SystemOne call via Promise.all; each result is a boolean "noul" question returning a probability (pointwise zero-shot LLM-as-judge) | jev-search src/lib/typesafe.ts rerank(); near RankGPT 2304.09542 | jev-search |
| stable-order-incremental-placement | A9/A12 | place() keeps already-placed items' positions fixed while inserting new rows into best gap; React useStableOrder wrapper → rows on screen never reorder mid-stream | jev-search src/lib/stable-order.ts + use-stable-order.ts + test/stable-order.test.ts | jev-search |
| filter-stale-by-freshness-decay | A2 | structured published_date preferred, snippet-date fallback; freshnessScore linear decay 1.0→0 at window edge; isPublicationStale accounts day-precision uncertainty (24h); window tolerance 1.5x | jev-search src/lib/freshness.ts; near Diaz 2009, Li&Croft 2003 | jev-search |
| cache-never-break-search | A2/A10 | cachedSearch() get/put both try/catch swallow; a broken cache never interrupts a search; TTL by window (10min-6h) | jev-search src/lib/cache.ts cachedSearch() | jev-search |
| cluster-near-duplicate-title | A2/A9 | titleKey() strips platform noise + canonicalUrl() strips tracking params (utm_/fbclid/gclid) → group lead+others, dedupe near-duplicates | jev-search src/lib/rank.ts clusterItems/clusterInOrder | jev-search |
| time-window-inference-discriminated-question | A2 | one systemOne call constructs a discriminated-union question set (window/source_*/query/entity) → single round-trip yields all intent | jev-search src/lib/typesafe.ts inferIntent() | jev-search |
| federated-multi-engine-source-resilience | A2 | all source lanes run concurrently (inFlight Map + Promise.race streaming yield); one engine 502 never kills the source/search | jev-search src/lib/pipeline.ts + test/pipeline.test.ts | jev-search |
| provider-chain-failover-on-outage-status | A2/A10 | retry next provider only on HTTP 402/429/5xx (isProviderOutage()); client errors (400/401) not retried; cancellation not retried | jev-search src/lib/typesafe.ts systemOne() | jev-search |
| score-coherence-self-disagreement | A9 | 23 ordered readings compare a browser's declared identity (UA/platform/userAgentData) against its own exposed surfaces; disagreement per class weighted (findingWeight) and summed to a 10-step score; no signature list | anti-mage internal/scan/scan.go order L60-82 + band.go + sec_audiobuf.go; near WebCrowd 2019 (crowd consistency) | Anti-Mage |
| enforce-server-issued-inputs | A9/A7 | challenge-response anti-tamper: 128-bit nonce + 6 invented font-family controls + 8 randomized time-offset dates issued server-side (TTL 30min/4096); client echoes nonce only; Decode never takes caller-chosen fields | anti-mage server/bootstrap.go issue() + assess/decode.go + assess_test.go:641 | Anti-Mage |
| abstention-neutral-scoring | A9 | probe absent/unsupported returns `unverified` (abstain, never a verdict); withdrawing a section never raises score (monotone); five-state determination model | anti-mage internal/scan/scan.go:14-22 + abstention_test.go + band_calibration_test.go:119 | Anti-Mage |
| provenance-flagged-tables | A9/A7 | reference tables carry Source{Origin,Checked} + Verified flag; Verified:false carries no evidentiary weight, enforced at every read site | anti-mage reference/reference.go + osfont/floor_test.go TestUnverifiedTableNeverPresentEvenWhenFullyMatched | Anti-Mage |
| declared-modification-downgrade | A9 | self-reported modified accessor scores strictly below a contradiction and explains its own downstream damage (honest tool not over-convicted) | anti-mage internal/scan/explained.go + band_calibration_test.go | Anti-Mage |
| opaque-anti-reverse-engineering-output | A9/A7 | verdict output = 5 fixed fields only, never which reading moved the score (info-minimization against gaming/reverse-engineering) | anti-mage server/server.go + server_test.go:145 TestScanReturnsOneAssessmentAndNoBreakdown | Anti-Mage |

---

## Registration rules

1. Only **Op3.5-verified** capabilities (mechanism named + paper/code backed)
   enter this table. Marketing fluff never does (§3.3 anti-hallucination).
2. A capability may cross paradigms (multi-axis tag) — record the primary.
3. When a later project **re-uses** a registered capability, append to its
   "First proven in" → a row accumulating ≥3 independent origins becomes an
   **Op4 opportunity seed** (§2 in `op4-gap-opportunity.md`).

## Seed sources (pending backfill)
- 本体工程/semantica tier-* analyses (ontology tooling capabilities)
- 数据和知识清洗/WeKnora, DataFlow (RAG/data-cleaning capabilities)
- agentos/评估工程 (evaluation capabilities)
- text2sql (NL2SQL / data-agent capabilities)
- 深度研究/research-kb (research/paper capabilities)| classify-logits-restricted-softmax | A5 | map each answer label to a single-token verbalizer, read next-token logits at last real token, filter to label-token set, restricted softmax → class probs, argmax predict; no autoregressive/no JSON gen | SALSA arXiv:2510.22691; ProbeLogits arXiv:2604.11943; Simple Jev hf_server.py HFBackend._score + common/response_scoring.py | Simple Jev (open ref); SALSA/ProbeLogits (papers) |
| reuse-kv-single-prefill-branch | A5 | multi-question shared context prefix: prefill ONCE (use_cache=True save KV) → deepcopy+reorder KV per branch → batched suffixes single forward read last-token logits; one engine call vs N+1 HTTP; KV reuse valid since cache depends only on prior tokens | LitJev backend.py TransformersScorer._score (two-forward+reorder_cache); SGLang RadixAttention arXiv:2312.07104; Simple Jev hf_server.py common_prefix | Simple Jev/LitJev (impl); SGLang (infra) |
| train-decision-allowed-label-softce | A5 | at last real token, soft cross-entropy over ALLOWED answer labels only: loss=-(labels*selected.log_softmax(-1)).sum(-1).mean(); no full-vocab LM loss, no JSON scaffolding loss, targets never tokenizer-specific | SALSA arXiv:2510.22691 (identical obj); Simple Jev RFDT/train.py:138 + metric train.py:322 | RFDT (=SALSA obj, source) |
| contract-versioned-language-agnostic | A5/A9 | prompt-structure+label-assign+scoring rules as plain-Python language-agnostic contract, versioned at builder boundary prepare_prompt(request,version=v1); version not a request field; new rules need new version; training reuses same PromptCompiler → train=infer isomorphic | Simple Jev common/prompt_builder.py + PROMPT_STRUCTURE_V1.md + RFDT/train.py compile_rows | Simple Jev (unique, no competitor) |
| verify-label-single-token | A5 | each answer label must extend rendered prompt by exactly ONE stable token; multi-token label rejected, never silently truncated / first-token-of-multitoken; distinguish tokenizer boundary (≠ char boundary) | Simple Jev hf_server.py PromptCompiler.compile 200-212; PROMPT_STRUCTURE_V1.md:392-395; near: ProbeLogits Token Fertility check | Simple Jev |
| benchmark-agreement-multimetric | A9 | endpoint answer-quality bench: serial HTTP POSTs to any Jev-shaped endpoint; metrics accuracy / mean_family_balanced_accuracy (per-family per-class recall then equal-mean) / equal_case_modal_agreement (per-group row acc then cross-case mean); 3-class retry, no redirect-with-bearer, validate-before-HTTP, run dir never overwritten | Simple Jev eval/run.py + eval/adapters/choice.py + eval/suites/; datasets SemIf TheoLeeCJ/SemIf(706) + TypeSafe-102(20/711) | Simple Jev eval/ |
| score-options-attention-shared-table | A15 | QKV attention head: each option is a learned embedding → query (`bnr`); context patches → key/value (`blr`); `scores=einsum("bnr,blr->bnl")/√rank` → softmax over patches → `logits=(query·attended)/√rank`; ALL options scored in one pass against one shared option-embedding table, so a changing candidate list is handled without a head rewrite | jevlike model.py AttentionHead:12-43; near DETR 2005.12872, AQT 2306.13879 | jevlike |
| position-in-keys-fixed-separable-2d | A15 | fixed separable 2D sinusoidal positions (`position_2d`: Vaswani freq, applied to rows & columns separately) added DIRECTLY into attention keys AFTER the learned projection: `key = head.key(context) + positions`; deliberate comment says post-projection placement cannot be washed out by context norm or routed only into V | jevlike vision.py position_2d:20-30 + DoomScorerV2._forward:105-107; near DETR spatial PE in Q+K, SaPE² 2505.09466 (Q vs K vs both) | jevlike |
| audit-screen-use-shuffled-patch-kl | A15/A9 | screen-dependence audit: compare policy on real / blank / averaged / shuffled-patch frames, per-button prob ranges, attention entropy; a near-zero KL(real_vs_shuffled_patches) + enemy-conditioned margins ≈ 0 means policy is NOT using the screen — reward-above-random does not count as visual control | jevlike examples/doom/audit.py | jevlike |
| ablate-head-bottleneck-flat-control | A15/A9 | architecture-control ablation: same conv stem followed by a flat MLP (`PlainConvPolicy`) vs the one-read-per-option attention head, trained on identical DAgger data, to isolate whether the option head is a capacity bottleneck or a data/navigation problem | jevlike vision.py PlainConvPolicy:130-173 | jevlike |

| ground-context-graph-retrieval-deterministic | A2 | AST+依赖图确定性检索供代理（图式表示>词嵌入分块），零 LLM 检索 | Repowise core/generation/context_assembler.py; Hydra FSE 2026, Repoformer ICML 2024 | Repowise |
| detect-health-crossfile-callgraph | A2 | 通过调用图追踪跨文件健康发现，文件级 linter 抓不到 | Repowise analysis/health/engine.py; Tufano ICSE 2015 | Repowise |
| predict-test-impact-static-nocoverage | A2 | 静态调用图+git 共变推断受影响测试，无需覆盖率报告 | Repowise analysis/test_impact.py; CEMENT arXiv:2203.11343, Spieker ISSTA 2017 | Repowise |
| score-change-risk-git-dependency-dual-signal | A2 | git 共变+静态依赖图双信号变更风险（两信号~22%重叠互补） | Repowise analysis/change_risk/; Tavakoli arXiv:2606.21187, Zimmermann ICSE 2004 | Repowise |
| mine-decisions-git-structural-signals | A1 | 从 git 历史/结构信号确定性挖掘架构决策（非显式 ADR 文本） | Repowise analysis/decision_extractor.py; ADR analysis arXiv:2609.07375 互补 | Repowise |
| score-gated-detectors-fixed-weight | A9 | 51 检测器但仅 26 个允许移动缺陷数字的克制计分（防噪） | Repowise analysis/health/grading.py; Ghost Echoes ICSME 2024 | Repowise |
| serve-mcp-lazy-tool-surface | A2/A1 | 惰性注册完整 MCP 工具面（ensure_full_surface）避免启动延迟 | Repowise server/mcp_server/ (10 广告/18 总) | Repowise |
| budget-mcp-response-per-tool | A2 | 每 MCP 工具独立响应预算契约（ResponseBudgetContract）防超长输出 | Repowise server/mcp_server/_budget/contracts.py | Repowise |
| index-repo-once-serve-many-clients | A2 | 一次全量索引，CLI/Web/MCP/VS Code/插件五路消费同一 core 索引 | Repowise core/pipeline/orchestrator.py | Repowise |
