# Op3 Search Dispatch Table (per A-paradigm)

Deterministic search plan selected by the **Axis A primary paradigm** from
`KNOWLEDGE-TAXONOMY.md`. Every dispatch column referenced there is expanded
here. This is the precision multiplier: a project classified A5 (推理优化) goes
straight to the distillation/hallucination paper + competitor sweep instead of
a vague "is it a competitor of X" blind search.

**Format:** `A#` | dispatch targets (competitors to sweep · papers to hunt ·
standards/domain surveys to check · work-log bins to mine for prior atomics).

|| A-paradigm | Competitor sweep | Paper hunt | Standards / domain survey | Prior work-log bins |
|--|-----------|------------------|------------|---------------------------|---------------------|
| A1 | Agent 框架与编排 | LangGraph, AutoGen, CrewAI, OpenAI Agents, Claude Agent SDK, Semaphore, OpenHands, n8n | autonomous agents, self-improvement, tool-using agents, agent orchestration | OpenAPI/Agent protocols (if platform) | 智能体框架, agentos, hermes-harness, skillsos |
| A2 | 检索增强 / RAG | LangChain, llama-index, Dify, WeKnora, DataFlow, LightRAG, GraphRAG, FlexRAG, R2R | chunking, embedding, hybrid retrieval, rerank, graph-rag, medical RAG | BEIR/RAGAS benchmarks; MSMARCO tracks | 数据和知识清洗, 本体工程/rag, cangjie-skill |
| A3 | 记忆与进化 | Mem0, MemGPT/Letta, Zep, MemOS, mempalace, gbrain, EverOS | memory consolidation, episodic/semantic memory, agent self-evolution | MemGPT paper lineage | 记忆和进化 |
| A4 | 本体与知识图谱 | semantica (tier-*), okf-rs, Protégé, Stardog, Ontotext, Neo4j, RDFLib | ontology learning, knowledge-graph embedding, SHACL validation, semantic matching | OWL/RDF/SPARQL/SHACL specs; Schema.org | 本体工程 |
| A5 | 推理与推理优化 | vLLM, SGLang, LMDeploy, TGI, ollama, DSPy, ReVerity, hallucination tools | reasoning distillation, CoT, inference scaling, quantization, hallucination mitigation, ICL | MLPerf inference; GSM8K/MATH/EvalPlus | 推理优化, coding/幻觉 |
| A6 | NL2SQL / 数据智能体 | WrenAI, Vanna, TextSQL, DataFormulator, Databricks AI/Genie, Snowflake Arctic-Copilot, Claude data tools | text-to-SQL, cross-domain NL2SQL, data-agent pipelines, semantic layer | Spider/BIRD//Spider-X, NL2SQL benchmarks | text2sql, data |
| A7 | 安全与合规 | promptfoo, AI-Infra-Guard, SkillSpector, Llama Guard, Garak, OWASP LLM | prompt injection, guardrails, agent security, red-teaming | TC260-GB, EU-AI-Act, US-ISS, ISO 42001, OWASP LLM Top10 | 安全, 企业一站式AI/参考规范 |
| A8 | 协作与多智能体 (human-AI) | clay, team-collab, multi-agent chat, deeper share models, AI teammates | human-AI collaboration, shared-context multi-agent, delegation | (thin standards) | AI协作分析 |
| A9 | 评估与评测 | OpenAI Evals, LangSmith, DeepEval, Ragas, Prometheus, EvalPlus | LLM-as-judge, benchmark construction, rubric scoring | HELM, MMLU, AgentBench, SWE-bench | agentos/评估工程, 评测基准 |
| A10 | 工具与执行层 | n8n, Make, Browser-use, Playwright-mcp, RPA, media tools, CodeRunner | (lite paper; study sys-design) | MCP protocol; web-standards | tools, devops, aiapp, office |
| A11 | 深度研究 / 科学知识 | research-kb (Polaris), RaW-apex, firecrawl, LitMan, scholar tools | AI4S, literature-mining, autonomous research, paper-graph | arXiv trend mapping | 深度研究, research-kb |
| A12 | 前端 / UI 呈现 | canvas tools, presentation engines, agent-UI shells, visualization libs | (lite paper; study UX/AB) | open-design, OD system | 前端框架, office, demo/需求到原型 |
| A13 | 空间智能 / 3D 重建 | MASt3R, DUSt3R, CroCo, Spann3R, MASt3R-SLAM, DPVO, CoSLAM, ACE0, Niantic/DeepMind depth models, SfM (COLMAP), Gaussian-SLAM (SplaTAM, GS-SLAM), Metric3D, UniDepth, SLAM engines (ORB-SLAM, DROID-SLAM, DROID-Diffusion) | monocular depth, camera pose estimation, dense SLAM, streaming/SLAM-online reconstruction, MVS, 3DGS, neural depth, pose graph optimization, RoPE, cross-view attention | KITTI/Oxford Spires/ScanNet/7Scenes/TUM benchmarks; GLUE-of-monocular-depth; DPVO eval | 空间智能/3D重建, 视觉SLAM |
| A14 | 生成式视频 / Diffusion Forcing | Wan2.1, HunyuanVideo, Open-Sora, CogVideoX, Kling, Runway-Gen3, Pika, LTX-Video, Mochi, Hailuo, Sora, SkyReels-A1/A2/A3 | diffusion-forcing, autoregressive video, long-video generation, T2V/I2V, flow-matching video, video captioning, TeaCache | SkyReels-Bench, VBench, V-Bench; EvalCrafter; VBench-Long | 视频生成, 生成式视频 |

---

## Cross-cutting rules

1. **Mine prior atomics first**: before sweeping new competitors, query the bin's
   prior work-log/analysis.db entries — the taxonomy's whole point is you already
   have most context; search the *delta*, not the full landscape.
2. **Papers only where the mechanism is research-fronting** (A3/A5/A11 heavy;
   A1/A2/A4 mid; A10/A12 lite) — don't spend paper time on pure tooling.
3. **Depth by B-nature**: A-primary picks *which* rows; B-nature picks *how deep*
   within them (platform → 10-dim competitor template; capability → paper-backed;
   domain → + survey).
4. **Extend this table, not the playbook**: new paradigm → add a row here + the
   registry, keep `op3-research.md` stable.