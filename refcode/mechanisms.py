#!/usr/bin/env python3
"""mechanisms - the design/mechanism-level knowledge system for the agent/LLM ecosystem.

This is the *mechanism-centric* layer that sits ON TOP of refcode's symbol index.
Where refcode answers "which file has symbol X", mechanisms answers:

    "AI 之间通讯都有哪些机制？"  ->  A2A / MCP / ACP / FIPA-ACL / event bus / ...
    "我该用哪个机制做多agent协作？" ->  scene -> ranked mechanisms
    "A2A 具体怎么实现？"          ->  mechanism -> real code/module anchors

Three layers (all in one self-contained mechanisms.db):

  mechanisms      the abstract concept ("what is it, how does it work") — the
                  retrieval subject, tagged by paradigm domain (A1..A29).
  implementations real code/module/symbol anchors from the refcode corpus that
                  instantiate the mechanism (slug + module + symbol + file:line).
  scenes          the recommendation entry points ("I want to do X") that map
                  to a ranked list of mechanisms via a fit-maturity-domain score.

Storage: mechanisms.db is INDEPENDENT of refcode.db on purpose — mechanism
knowledge and scene-recommendation are a different granularity than symbol
retrieval, and mixing them would make both worse. refcode.db is read-only
input here (symbol anchors). Run via ``refcode mechanisms ...``.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
MECH_DB = Path(os.environ.get(
    "MECHANISMS_DB", str(Path.home() / ".refcode" / "mechanisms.db")))
REFCODE_DB = Path(os.environ.get(
    "REFCODE_DB", str(Path.home() / ".refcode" / "refcode.db")))
ANALYSIS_DB = Path(os.environ.get(
    "ANALYSIS_DB", "{{ANALYSIS_DB}}"))
WORKLOG = Path(os.environ.get(
    "WORKLOG", str(Path.home() / "work-log")))

# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #
MECH_SCHEMA = """
CREATE TABLE IF NOT EXISTS mechanisms (
  id          TEXT PRIMARY KEY,      -- slug e.g. 'a2a-protocol'
  name        TEXT NOT NULL,
  domain      TEXT NOT NULL,         -- A1..A29 paradigm id
  domain_name TEXT DEFAULT '',       -- human name of the domain
  definition  TEXT NOT NULL,         -- mechanism-level "what/how" description
  scenes      TEXT DEFAULT '[]',     -- JSON list of applicable scene keywords
  pros        TEXT DEFAULT '[]',
  cons        TEXT DEFAULT '[]',
  maturity    REAL DEFAULT 0,        -- 0..1 (impl count / corpus size blend)
  source_docs TEXT DEFAULT '[]',     -- JSON list of work-log doc paths
  created_at  TEXT
);

CREATE TABLE IF NOT EXISTS implementations (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  mechanism_id TEXT NOT NULL REFERENCES mechanisms(id) ON DELETE CASCADE,
  slug         TEXT NOT NULL,        -- refcode corpus project
  module       TEXT NOT NULL,        -- module / top-level dir or key path
sym         TEXT NOT NULL DEFAULT '',   -- anchor symbol
  line        INTEGER,              -- file:line of sym
  impl_note   TEXT,                 -- how this implementation instantiates it
  UNIQUE(mechanism_id, slug, module, sym)
);

CREATE TABLE IF NOT EXISTS scenes (
  id          TEXT PRIMARY KEY,
  description TEXT NOT NULL,
  domain      TEXT DEFAULT '',       -- preferred paradigm
  keywords    TEXT DEFAULT '[]'      -- JSON keyword list for semantic match
);

-- Fused real-world instances from analysis.db. Each row is one analyzed
-- project (repo-map Op2/Op3/Op4 output): a concrete implementation that
-- instantiates a mechanism, with the work-log analysis doc as the source.
CREATE TABLE IF NOT EXISTS project_instances (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  mechanism_id TEXT NOT NULL REFERENCES mechanisms(id) ON DELETE CASCADE,
  project_name TEXT NOT NULL,
  domain       TEXT NOT NULL,         -- paradigm_id (A1..A29)
  why_worth    TEXT,                  -- mechanism summary from analysis.db
  analysis_path TEXT,                 -- work-log doc path (source)
  source_type  TEXT DEFAULT '',
  UNIQUE(mechanism_id, project_name)
);

CREATE VIRTUAL TABLE IF NOT EXISTS mechanism_fts USING fts5(
  id UNINDEXED, name, domain, definition, scenes,
  tokenize = 'unicode61'
);
"""

# Curated scene library — the recommendation entry points ("I want to do X").
CURATED_SCENES = [
    ("multiagent-collab", "我要让多个 agent 协作解决一个复杂任务", "A8",
     "多agent,协作,协同,合作,分工"),
    ("agent-comm", "两个 agent 之间怎么通讯/传消息", "A8", "通讯,通信,消息,传,互操作"),
    ("agent-discovery", "如何让 agent 发现其他 agent / 服务", "A8", "发现,注册,目录,服务"),
    ("agent-secure-comm", "agent 之间安全传输上下文/凭证", "A8", "安全,凭证,认证,传输,上下文"),
    ("agent-memory", "怎么让 agent 记住之前的对话/知识", "A3", "记忆,回忆,长期,历史,存储"),
    ("agent-tools", "如何让 agent 调用外部工具/API", "A10", "工具,调用,函数,api,连接"),
    ("agent-reasoning", "让 agent 能深入推理/规划", "A5", "推理,规划,思考,反思"),
    ("agent-sandbox", "安全地执行 agent 生成的代码", "A18", "沙箱,执行,隔离,安全,代码"),
    ("agent-gui", "让 agent 操作图形界面/浏览器", "A12", "gui,界面,浏览器,点击,桌面"),
    ("agent-decentralized", "去中心化/无中心编排的多 agent 通信", "A8",
     "去中心化,点对点,p2p,无中心,网络"),
    ("agent-eval", "如何评估 agent 的表现", "A9", "评估,评测,基准,测试,指标"),
    ("agent-framework", "选一个 agent 框架/运行时", "A1", "框架,运行时,选择,搭建,base"),
    ("agent-rag", "给 agent 接入知识库检索", "A2", "检索,知识库,rag,文档,增强"),
]


def _seed_scenes(conn: sqlite3.Connection) -> int:
    before = set(r["id"] for r in conn.execute("SELECT id FROM scenes"))
    for sid, desc, dom, kw in CURATED_SCENES:
        conn.execute(
            "INSERT OR IGNORE INTO scenes (id,description,domain,keywords) "
            "VALUES (?,?,?,?)", (sid, desc, dom, kw))
    conn.commit()
    after = set(r["id"] for r in conn.execute("SELECT id FROM scenes"))
    return len(after - before)


# --------------------------------------------------------------------------- #
# DB access
# --------------------------------------------------------------------------- #
def open_mech_db(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or MECH_DB), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(MECH_SCHEMA)
    return conn


def mech_db_exists(path: Path | None = None) -> bool:
    return (path or MECH_DB).exists()


# --------------------------------------------------------------------------- #
# Domain taxonomy (from analysis.db project_paradigms)
# --------------------------------------------------------------------------- #
_PARADIGM_NAMES = {
    "A1": "Agent 框架与编排", "A2": "检索增强 / RAG", "A3": "记忆与进化",
    "A4": "本体与知识图谱", "A5": "推理与推理优化", "A6": "NL2SQL / 数据智能体",
    "A7": "安全与合规", "A8": "协作与多智能体", "A9": "评估与评测",
    "A10": "工具与执行层", "A11": "深度研究 / AI4S", "A12": "前端 / UI 呈现",
    "A13": "空间智能 / 3D", "A14": "生成式媒体", "A15": "视觉控制 / 游戏",
    "A16": "SASE / 零信任", "A17": "OS / 微内核", "A18": "运行时复用 / 沙箱",
    "A24": "GPU/张量内核", "A25": "逆向工程", "A26": "数据查询治理网关",
    "A27": "像素空间图像扩散", "A28": "时序基础模型", "A29": "文档智能 / OCR",
}


def domain_name(pid: str) -> str:
    return _PARADIGM_NAMES.get(pid, pid)


# --------------------------------------------------------------------------- #
# Curated mechanism seed — the abstract mechanisms (what "AI间通讯有哪些机制"
# returns). Each entry: id, name, domain (A1..A29), definition, scenes, pros,
# cons. Implementations are auto-attached from analysis.db + refcode on build.
# --------------------------------------------------------------------------- #
CURATED_MECHANISMS = [
    # --- 通讯 / 多智能体协作 (A8) ---
    dict(id="a2a-protocol", name="Agent-to-Agent (A2A) 互操作协议", domain="A8",
         definition="Linux Foundation 的 agent 间互操作标准 (v1.0, 150+ org)。有状态 Task 状态机 + 企业级认证 (SecurityScheme) + agent-card 发现机制。三大传输：JSON-RPC over HTTP/SSE、以及 push (webhook) 推送。contextId 串联多 agent 协作的共享上下文。解决跨厂商 agent 互操作。",
         scenes=["agent 间通讯", "agent 互操作协议", "agent 发现", "跨厂商 agent 协作", "agent 状态机"],
         pros=["开放标准多组织背书", "状态机明确可审计", "企业级认证", "发现机制成熟"],
         cons=["较重", "需双方实现协议", "实时性依赖传输"]),
    dict(id="mcp-tool-layer", name="MCP 工具层协议", domain="A8",
         definition="Model Context Protocol：把工具/资源/提示词暴露给 agent 的统一协议层。agent 通过 MCP 客户端发现并调用远端工具 (tools)、读资源 (resources)、加载提示 (prompts)，JSON-RPC 2.0 传输。是 agent 与工具生态解耦的标准。",
         scenes=["工具调用", "工具层协议", "agent 连接工具", "MCP", "工具发现"],
         pros=["生态最大", "工具/资源/提示统一", "Server 一次实现多处复用"],
         cons=["单 agent-工具 范式，非 agent-agent", "工具发现是拉取非推"],
         ),
    dict(id="fipa-acl", name="FIPA-ACL 智能体通信语言", domain="A8",
         definition="FIPA 标准智能体通信语言：基于 speech-act (告知/请求/承诺) 的消息封装 + 内容语言 (SL/FIPA-SL) + 本体。消息有 performative、sender/receiver、ontology、protocol 字段。经典多智能体系统的通信语言标准。",
         scenes=["智能体通信语言", "speech-act", "FIPA", "多智能体标准通信"],
         pros=["语义丰富的消息结构", "标准化", "本体支持"],
         cons=["沉重", "较少现代 AI agent 采用"]),
    dict(id="role-play-communication", name="角色扮演多智能体通信 (CAMEL)", domain="A8",
         definition="inception prompting 让 AI 扮演不同角色 (如用户/AI 助手) 自主对话完成任务。CAMEL 提出用角色扮演框架让 agent 间通过自然语言对话协作，实现任务求解与跨领域知识探索。",
         scenes=["角色扮演通信", "CAMEL", "agent 对话", "双 agent 协作"],
         pros=["简单", "自然语言表达力强", "角色分工清晰"],
         cons=["易跑题/发散", "无结构化协议", "难保证收敛"]),
    dict(id="conversational-multiagent", name="会话驱动多智能体 (AutoGen)", domain="A8",
         definition="AutoGen 多智能体对话框架：可编程会话驱动方式组合多个 LLM/工具/人类，用自动化对话让 agent 协作解决任务。agent 间通过消息传递 (Message) 在会话图上流转，支持群聊 (GroupChat) 与说话者选择。",
         scenes=["多 agent 对话", "AutoGen", "群聊协作", "agent 编排"],
         pros=["编程式灵活", "人机混合", "会话图清晰"],
         cons=["对话可能低效", "收敛性依赖说话者选择策略"]),
    dict(id="graph-orchestration", name="图拓扑多智能体编排 (GPTSwarm)", domain="A8",
         definition="把多语言智能体建模为可优化的图结构 (Graph)，智能体间通信通过图拓扑 (边) 定义，图参数可优化以改进协作性能。Agent 网络 (communication graph) 用强化/进化优化边的权重与结构。",
         scenes=["图编排", "GPTSwarm", "agent 网络优化", "协作拓扑"],
         pros=["拓扑可优化", "形式化图模型", "可扩展"],
         cons=["抽象度高", "需定义图结构"]),
    dict(id="chain-of-agents", name="链式多智能体协作 (Chain-of-Agents)", domain="A8",
         definition="端到端多 agent 链式协作：前序 agent 将推理摘要传给下一个 agent，逐个传递直到最后输出。用于超长上下文任务，把多 agent 的 chain-of-thought 协作蒸馏进单模型或链式传播。",
         scenes=["链式 agent", "长上下文", "多 agent 传递", "蒸馏协作"],
         pros=["突破上下文窗口", "信息逐级压缩", "可端到端"],
         cons=["错误沿链累积", "顺序延迟"]),
    dict(id="sop-multiagent", name="SOP 标准化流程多智能体 (MetaGPT)", domain="A8",
         definition="用标准化操作流程 (SOP) 给多智能体赋能：把成熟软件开发流程编码为智能体分工 (产品/架构/开发/测试)，多角色智能体像软件公司一样协作。角色间通过结构化输出/文档传递。",
         scenes=["SOP 协作", "MetaGPT", "软件公司 agent", "角色分工"],
         pros=["流程规范化", "角色产出可对齐", "适合软件工程"],
         cons=["流程僵化", "角色间冗余通信"]),
    dict(id="evolving-orchestration", name="演化式多智能体编排", domain="A8",
         definition="编排机制可随任务/经验演化：动态调整智能体协作模式以提升性能。EvoMAC 用文本反向传播更新协作网络，验证输出与目标对比获得文本反馈，据此更新 agent 网络。",
         scenes=["演化编排", "EvoMAC", "自适应协作", "agent 网络进化"],
         pros=["自适应", "文本反馈驱动", "网络可演化"],
         cons=["不稳定", "需反馈信号"]),
    dict(id="theory-of-mind-collab", name="心智理论 (ToM) 协作", domain="A8",
         definition="利用 LLM 在 agent 间显式建模彼此心智状态 (Theory of Mind)，让智能体推理同伴的信念与意图以改进协作决策。在协作/竞争场景中预测对方行为。",
         scenes=["ToM", "心智理论", "agent 意图推断", "协作决策"],
         pros=["增强协作预测", "处理不确定性"],
         cons=["LLM 心智建模不准", "计算开销"]),
    dict(id="ai-communication-attack-defense", name="agent 通信安全 (中间人攻击防护)", domain="A8",
         definition="Agent-in-the-Middle (AiTM) 攻击：拦截并操纵 agent 间通信消息。防护涉及消息完整性/来源认证/防篡改。Colosseum 审计多智能体共谋。通信安全是多 agent 系统的关键约束。",
         scenes=["agent 通信安全", "AiTM", "共谋审计", "消息完整性"],
         pros=["识别通信风险", "完整性防护"],
         cons=["防护尚未标准化", "开销"]),
    # --- Agent 框架与编排 (A1) ---
    dict(id="agent-framework-loop", name="Agent 主循环框架", domain="A1",
         definition="通用 agent 运行时框架：感知-规划-行动-反思 (perceive-plan-act-reflect) 主循环，含工具调用、记忆注入、多 agent 运行时。LangGraph/AutoGen/ClawTeam 等实现。",
         scenes=["agent 框架", "主循环", "运行时", "agent 编排"],
         pros=["通用", "生态成熟"],
         cons=["抽象层次高", "性能开销"]),
    dict(id="subagent-spawn", name="子 Agent 生成 (Subagent Spawn)", domain="A1",
         definition="主 agent 动态生成子 agent 并行处理子任务并汇总结果的机制。Agent-as-Tool 把子 agent 作为可调用工具，实现层级分解与并行。",
         scenes=["子 agent", "任务分解", "并行子任务", "Agent-as-Tool"],
         pros=["并行加速", "模块化", "可扩展"],
         cons=["编排复杂", "上下文开销"]),
    # --- 记忆 (A3) ---
    dict(id="vector-memory", name="向量语义记忆", domain="A3",
         definition="把 agent 历史/知识嵌入向量库，按语义相似度检索注入上下文。mem0/chroma/hindsight 等实现，含写入-索引-检索-遗忘 生命周期。",
         scenes=["向量记忆", "语义检索", "agent 长期记忆", "记忆注入"],
         pros=["语义检索", "可扩展", "成熟生态"],
         cons=["嵌入成本", "相关性与时效性"]),
    dict(id="hierarchical-memory", name="分层智能体记忆 (G-Memory)", domain="A3",
         definition="面向多智能体系统的组织记忆启发式层级记忆：按组织层级 (组织/团队/个人) 分层存储与检索，让 agent 记忆与其角色对齐且内在演化。",
         scenes=["分层记忆", "多 agent 记忆", "组织记忆", "角色对齐记忆"],
         pros=["层级清晰", "角色对齐", "组织可扩展"],
         cons=["层级维护开销"]),
    dict(id="latent-internalized-memory", name="隐式内化记忆 (Latent Agents)", domain="A3",
         definition="通过 post-training (activation steering) 把多智能体显式协作/记忆内化为单模型内部机制。Latent Agents 把多 agent 辩论蒸馏进单个 LLM。",
         scenes=["内化记忆", "activation steering", "蒸馏协作", "隐式 agent"],
         pros=["推理开销低", "无显式多 agent"],
         cons=["不可解释", "需 post-training"]),
    # --- 推理 (A5) ---
    dict(id="reasoning-chain", name="链式推理 (CoT/ReAct)", domain="A5",
         definition="让 LLM 逐步推理 (chain-of-thought) 或推理+行动交替 (ReAct) 的机制，提升复杂任务正确率。",
         scenes=["链式推理", "CoT", "ReAct", "逐步推理"],
         pros=["简单有效", "可解释"],
         cons=["长度限制", "长链错误累积"]),
    dict(id="mcts-reasoning", name="蒙特卡洛树搜索推理 (MCTS)", domain="A5",
         definition="用 MCTS 在推理/工作流空间中搜索 (ADAS/AFlow)，探索-利用权衡优化 agent 工作流生成。AFlow 用蒙特卡洛树搜索生成最优工作流。",
         scenes=["MCTS", "搜索推理", "工作流搜索", "AFlow"],
         pros=["系统性搜索", "可优化"],
         cons=["计算昂贵"]),
    dict(id="self-evolution", name="自进化 / 自动设计 (ADAS)", domain="A3",
         definition="Agent 系统自动设计与自进化：元智能体自动设计/改进 agent 系统本身。ADAS 从 prompt/code 搜索 agent 设计空间。",
         scenes=["自进化", "ADAS", "agent 自动设计", "元编程"],
         pros=["自动改进", "搜索设计空间"],
         cons=["不稳定", "成本高"]),
    # --- 工具调用 (A10) ---
    dict(id="tool-calling", name="函数/工具调用", domain="A10",
         definition="LLM 声明式调用外部函数的机制：模型输出结构化函数调用参数，运行时执行并返回结果。OpenAI 函数调用、smolagents tool、MCP 均基于此。",
         scenes=["工具调用", "函数调用", "tool use", "外部函数"],
         pros=["声明式", "生态成熟", "可组合"],
         cons=["需 schema", "结果需校验"]),
    dict(id="dynamic-tool-gen", name="动态工具生成 (ATLASS)", domain="A10",
         definition="按需动态生成工具代码的机制：ATLASS 在推理时生成工具定义与实现，让 agent 能处理未见过的工具需求。",
         scenes=["动态工具", "ATLASS", "按需工具", "工具生成"],
         pros=["覆盖未见工具", "灵活"],
         cons=["生成质量风险", "安全"]),
    dict(id="tool-orchestration", name="工具编排调度 (ToolOrchestra)", domain="A10",
         definition="高效调度模型与工具资源的编排机制：决策何时调用工具、调用哪个，优化成本与效果。",
         scenes=["工具编排", "工具调度", "ToolOrchestra", "成本优化"],
         pros=["成本/效果优化", "调度智能"],
         cons=["决策模型开销"]),
    # --- 检索增强 (A2) ---
    dict(id="rag", name="检索增强生成 (RAG)", domain="A2",
         definition="先检索相关文档再生成的机制：把外部知识/语料嵌入索引，查询时检索 top-k 上下文注入 LLM，缓解幻觉、引入领域知识。",
         scenes=["RAG", "检索增强", "知识注入", "文档问答"],
         pros=["知识时效性", "可溯源", "缓解幻觉"],
         cons=["检索质量关键", "上下文膨胀"]),
    # --- 评估 (A9) ---
    dict(id="agent-eval-bench", name="Agent 评估基准", domain="A9",
         definition="评估 agent 能力/安全的基准与评测框架：定义任务集、度量、runner。SafeGenBench 评测代码安全，Harness-Bench 评测 harness。",
         scenes=["agent 评估", "基准", "评测框架", "安全评测"],
         pros=["可量化", "回归检测"],
         cons=["基准偏差", "构建成本"]),
    # --- 执行/沙箱 (A18) ---
    dict(id="sandbox-exec", name="沙箱代码执行", domain="A18",
         definition="在隔离沙箱中执行 agent 生成的代码/工具调用，控制权限与副作用。swe-agent/browser-harness/代码解释器实现。",
         scenes=["沙箱执行", "代码解释器", "安全执行", "隔离"],
         pros=["隔离安全", "副作用控制"],
         cons=["性能开销", "权限配置"]),
    # --- 前端/UI (A12) ---
    dict(id="gui-agent", name="GUI 操作智能体", domain="A12",
         definition="agent 像人一样操作 GUI 的机制：截屏/像素感知 + 规划 + 点击输入 grounding。Agent S/计算机操作框架。",
         scenes=["GUI 操作", "计算机操作", "视觉 agent", "桌面自动化"],
         pros=["通用界面", "无需 API"],
         cons=["像素误差", "慢"]),
    # --- 推理/意图沟通 (A8) ---
    dict(id="intent-communication", name="意图驱动沟通设计", domain="A8",
         definition="设计 agent 间意图驱动的沟通方式：明确 agent 想表达/需要什么 (意图)，而非只传递数据。意图沟通设计提升协作效率。",
         scenes=["意图沟通", "agent 意图", "沟通设计", "协作语义"],
         pros=["语义明确", "减少歧义"],
         cons=["需意图建模"]),
]


def _seed_mechanisms(conn: sqlite3.Connection) -> int:
    now = _now()
    n = 0
    before = set(r["id"] for r in conn.execute("SELECT id FROM mechanisms"))
    for m in CURATED_MECHANISMS:
        conn.execute(
            "INSERT OR IGNORE INTO mechanisms "
            "(id,name,domain,domain_name,definition,scenes,pros,cons,maturity,source_docs,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (m["id"], m["name"], m["domain"], domain_name(m["domain"]),
             m["definition"], json.dumps(m["scenes"]), json.dumps(m["pros"]),
             json.dumps(m["cons"]), 0.3, json.dumps([]), now))
    conn.commit()
    after = set(r["id"] for r in conn.execute("SELECT id FROM mechanisms"))
    return len(after - before)


# Curated project -> mechanism attachments (real code anchors for the
# communication mechanisms the user asks about). slug must exist in refcode.
# Values are (slug, [module-hint substrings]) — the module hints keep anchors
# to the protocol-relevant code, not arbitrary first symbols in the project.
SLUG_ATTACHMENTS = {
    "a2a-protocol": [("a2a", ["tasks", "types", "client", "server", "agent", "operations"]),
                     ("ag2", ["a2a"])],
    "mcp-tool-layer": [("ag2", ["mcp", "tool"]), ("a2a", []), ("clawteam", ["mcp"]),
                       ("openhands", ["mcp", "tool"])],
    "fipa-acl": [],
    "role-play-communication": [("ag2", ["convers", "agent"]), ("a2a", [])],
    "conversational-multiagent": [("ag2", ["convers", "chat", "group", "agent"]),
                                  ("clawteam", ["claw"]), ("avernet", ["claw"]),
                                  ("firstmate", [])],
    "graph-orchestration": [("avernet", ["workflow", "graph", "edge", "node"]),
                            ("multica", []), ("macro", [])],
    "chain-of-agents": [("ag2", ["chain", "agent"])],
    "sop-multiagent": [("ag2", ["agent", "role"]), ("clawteam", ["claw"]),
                       ("dsh-agent-teams", [])],
    "evolving-orchestration": [("ag2", [])],
    "theory-of-mind-collab": [("ag2", [])],
    "ai-communication-attack-defense": [("a2a", ["security", "auth", "signature"])],
    "agent-framework-loop": [("ag2", ["agent", "runtime", "client", "chat"]),
                             ("clawteam", ["claw"]), ("avernet", ["claw"]),
                             ("openhands", ["runtime", "agent"]),
                             ("swe-agent", ["agent", "runtime"]),
                             ("deepseek-harness", ["agent", "harness"]),
                             ("paperclip", []), ("herdr", []), ("vibe-kanban", [])],
    "subagent-spawn": [("avernet", ["subagent", "agent"]), ("clawteam", ["claw"]),
                       ("openhands", ["agent"]), ("ag2", ["agent"])],
    "vector-memory": [("openhands", ["memory", "store"]), ("clawteam", ["memory"])],
    "hierarchical-memory": [("avernet", ["memory"])],
    "latent-internalized-memory": [],
    "reasoning-chain": [("ag2", ["agent", "reason"]), ("openhands", ["agent"]),
                        ("deepseek-harness", [])],
    "mcts-reasoning": [],
    "self-evolution": [("ag2", []), ("clawteam", [])],
    "tool-calling": [("ag2", ["tool", "function"]), ("openhands", ["tool", "action"]),
                     ("clawteam", ["tool"]), ("swe-agent", ["tool"]),
                     ("deepseek-harness", ["tool"])],
    "dynamic-tool-gen": [],
    "tool-orchestration": [("openhands", ["tool", "action"]), ("ag2", ["tool"]),
                           ("clawteam", ["tool"])],
    "rag": [("openhands", ["retriev", "store", "memory"])],
    "agent-eval-bench": [("harness2", ["bench", "eval", "harness"]),
                         ("agent-standup", [])],
    "sandbox-exec": [("swe-agent", ["sandbox", "docker", "runtime"]),
                     ("openhands", ["runtime", "sandbox"]),
                     ("deepseek-harness", ["sandbox", "runtime"])],
    "gui-agent": [("tutti", ["gui", "screen", "click"]), ("openhands", ["browser", "gui"])],
    "intent-communication": [("a2a", ["task", "message"]), ("macro", [])],
}


def _anchor_from_slugs(conn: sqlite3.Connection, mechanism_id: str,
                       slug_hints: list[tuple[str, list[str]]]) -> int:
    """Attach real code anchors for a mechanism from refcode corpus slugs.

    module-hint filtering keeps the anchor to protocol-relevant modules instead
    of the first symbols in the project (which are often docs/scripts).
    """
    if not REFCODE_DB.exists() or not slug_hints:
        return 0
    rc = sqlite3.connect(f"file:{REFCODE_DB}?mode=ro", uri=True, timeout=30)
    rc.row_factory = sqlite3.Row
    n = 0
    try:
        for slug, hints in slug_hints:
            if not hints:
                continue  # no module hints -> would only grab noise anchors; skip
            base = "SELECT file_path, name, start_line FROM ref_symbols WHERE project=?"
            conds, params = [f"project=?"], [slug]
            for h in hints:
                conds.append("file_path LIKE ?")
                params.append(f"%{h}%")
            sql = (base + " AND (" + " OR ".join(conds[1:]) + ") "
                   "AND kind IN ('class','function') ORDER BY start_line LIMIT 4")
            rows = rc.execute(sql, params).fetchall()
            for r in rows:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO implementations "
                        "(mechanism_id,slug,module,sym,line,impl_note) "
                        "VALUES (?,?,?,?,?,?)",
                        (mechanism_id, slug,
                         str(Path(r["file_path"]).parent),
                         r["name"] or "", r["start_line"] or 0,
                         f"[{slug}] {r['file_path']}:{r['start_line']}"))
                    n += 1
                except sqlite3.Error:
                    pass
    finally:
        rc.close()
    conn.commit()
    return n


def _anchor_all(conn: sqlite3.Connection) -> int:
    n = 0
    for mech_id, slug_hints in SLUG_ATTACHMENTS.items():
        n += _anchor_from_slugs(conn, mech_id, slug_hints)
    return n


def _extract_mechs_from_worklog() -> list[dict]:
    """Pull mechanism candidates from analysis.db's analyzed projects.

    analysis.db.analysis_index holds ~1781 analyzed projects, each with a
    ``why_worth`` field that literally contains the mechanism summary
    ("[全量摘要确认] 机制: ..."), a ``paradigm_id`` domain (A1..A29), and an
    ``analysis_path`` pointing at the work-log analysis doc. That is far
    cleaner than parsing work-log filenames, which mix repo-map product docs
    with mechanism analyses and carry boilerplate ("生成日期", ...).

    Each analyzed project becomes a mechanism candidate:
      id        = slugified project_name
      name      = project_name
      domain    = paradigm_id
      definition= why_worth (mechanism summary, boilerplate stripped)
      source_docs = [analysis_path]
    """
    out = []
    idx = _load_analysis_index()
    for r in idx:
        name = r.get("project_name") or ""
        if not name:
            continue
        why = r.get("why_worth") or ""
        mech = _strip_mechanism_prefix(why) or name
        domain = r.get("paradigm_id") or "A1"
        out.append({
            "id": _slugify(name),
            "name": name,
            "domain": domain,
            "definition": mech[:600],
            "source_docs": [r["analysis_path"]] if r.get("analysis_path") else [],
        })
    return out


def _strip_mechanism_prefix(text: str) -> str:
    """'[全量摘要确认] 机制: X' / '机制: X' / '[LL2]...' -> clean mechanism text."""
    t = re.sub(r"^\[[^\]]*\]\s*", "", text)
    t = re.sub(r"^机制[:：]\s*", "", t)
    t = re.sub(r"\s*\|\s*类[:：].*$", "", t)
    return t.strip()


def _first_meaningful(text: str, limit: int = 400) -> str:
    """First non-heading, non-empty line of a doc, trimmed, as a short def."""
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or ln.startswith("---"):
            continue
        # skip TOC/table lines
        if ln.startswith(("|", "```", "- [", "1. ", "## ")):
            continue
        ln = re.sub(r"\s+", " ", ln)
        return ln[:limit]
    return ""


def _slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return s or "mech"


def _load_analysis_index() -> list[dict]:
    """Read analysis.db analysis_index rows we can mine for definitions/domains."""
    if not ANALYSIS_DB.exists():
        return []
    conn = sqlite3.connect(str(ANALYSIS_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT project_name, paradigm_id, core_functions, why_worth, "
            "analysis_path FROM analysis_index WHERE status='analyzed'"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Refcode symbol anchors
# --------------------------------------------------------------------------- #
def _refcode_impls_for(mech_id: str, mech_name: str) -> list[dict]:
    """Find real code anchors for a mechanism in the refcode corpus.

    Heuristic: query refcode symbols whose project slug or symbol name overlaps
    the mechanism name/domain. Returns up to N (slug, module, sym, line) rows.
    """
    if not REFCODE_DB.exists():
        return []
    conn = sqlite3.connect(f"file:{REFCODE_DB}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        # best-effort: symbols whose name contains a token of the mech name
        toks = [t for t in re.split(r"[\s_\-/]+", mech_name.lower()) if len(t) >= 3]
        if not toks:
            return []
        cols = "project, file_path, name AS sym, start_line AS line"
        rows = []
        seen = set()
        for t in toks[:4]:
            pat = f"%{t}%"
            for r in conn.execute(
                f"SELECT {cols} FROM ref_symbols WHERE LOWER(name) LIKE ? "
                f"AND project NOT IN ('opencode') LIMIT 40", (pat,)):
                key = (r["project"], r["file_path"], r["line"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(dict(r))
                if len(rows) >= 20:
                    break
            if len(rows) >= 20:
                break
        return rows
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------------- #
# generic tokens that carry no discriminating signal for scene->mechanism fit;
# they appear in nearly every mechanism definition and would drown real terms.
_STOP = {
    "agent", "agents", "llm", "ai", "智能体", "多", "的", "间", "做", "进行",
    "使用", "基于", "一个", "方法", "可以", "如何", "怎么", "两个", "之间",
    "这个", "这些", "那么", "还有", "以及",
}


# CJK synonyms — user queries use 通讯/通信/语境 interchangeably with the
# wording in mechanism definitions; normalize both sides so they intersect.
_SYNONYMS = {
    "通讯": "通信", "通信": "通信", "通讯机制": "通信",
    "上下文": "语境", "语境": "语境",
    "记忆": "记忆", "回忆": "记忆",
    "工具": "工具", "调用": "调用",
    "推理": "推理", "思考": "推理",
    "协作": "协作", "合作": "协作", "协同": "协作",
    "安全": "安全", "凭证": "认证",
}


def _norm_cjk(words: set[str]) -> set[str]:
    return {_SYNONYMS.get(w, w) for w in words}


def _tokenize(text: str) -> set[str]:
    toks = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return {t for t in toks if len(t) >= 2 and t not in _STOP}


def _cjk_words(text: str) -> set[str]:
    """Extract meaningful 2-char CJK words (not overlapping substrings)."""
    runs = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    out = set()
    for run in runs:
        for i in range(0, len(run) - 1):
            w = run[i:i + 2]
            if w not in _STOP and w not in ("智能", "优化", "实现",
                                            "能力", "多智", "两个"):
                out.add(w)
    return out


def _score_mechanism(m: sqlite3.Row, scene_text: str) -> float:
    """rank(M,S): fit dominates; maturity only boosts among mechanisms that fit.

    fit is Jaccard overlap of scene terms vs mechanism terms on stopword-
    filtered tokens (generic words like agent/机制 don't dominate). Maturity
    (popularity) is gated on a real term match — a mature mechanism that does
    not touch the scene's vocabulary must not surface ahead of a fitting one.
    """
    scene_ascii = _tokenize(scene_text)
    scene_cjk = _norm_cjk(_cjk_words(scene_text))
    mech_text = f"{m['name']} {m['definition']} {m['scenes']}"
    mech_ascii = _tokenize(mech_text)
    mech_cjk = _norm_cjk(_cjk_words(mech_text))

    ascii_inter = scene_ascii & mech_ascii
    cjk_inter = scene_cjk & mech_cjk

    union_a = scene_ascii | mech_ascii
    union_c = scene_cjk | mech_cjk
    fit_a = len(ascii_inter) / max(len(union_a), 1) if union_a else 0.0
    fit_c = len(cjk_inter) / max(len(union_c), 1) if union_c else 0.0
    has_cjk = bool(scene_cjk)
    fit = (fit_c * 0.65 + fit_a * 0.35) if has_cjk else fit_a

    if fit <= 0.0:
        return 0.0
    maturity = float(m["maturity"] or 0)
    return round(fit * 0.85 + maturity * 0.15, 4)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_mechanisms(args, refcode_conn: sqlite3.Connection | None = None) -> int:
    action = args.action
    conn = open_mech_db(Path(args.mech_db) if getattr(args, "mech_db", None) else None)

    if action == "build":
        return _cmd_build(conn, args)
    if action == "list":
        return _cmd_list(conn, args)
    if action == "show":
        return _cmd_show(conn, args)
    if action == "recommend":
        return _cmd_recommend(conn, args)
    if action == "impl":
        return _cmd_impl(conn, args)
    if action == "scene":
        if getattr(args, "subaction", None) == "add":
            return _cmd_scene(conn, args, add=True)
        return _cmd_scene(conn, args, add=False)
    print(f"usage: refcode mechanisms {{build|list|show|recommend|impl|scene}}",
          file=sys.stderr)
    return 2


def _cmd_build(conn: sqlite3.Connection, args) -> int:
    """Seed curated mechanisms + anchor real code impls from refcode corpus.

    This is the intended build path: CURATED_MECHANISMS holds the abstract
    mechanisms (what `recommend`/`show` answer); SLUG_ATTACHMENTS maps each to
    real refcode corpus projects so `show` can list concrete code anchors.
    analysis_index is used only to enrich maturity/domain when available.
    """
    seeded = _seed_mechanisms(conn)
    print(f"seeded {seeded} curated mechanisms")
    scenes = _seed_scenes(conn)
    print(f"seeded {scenes} curated scenes")

    # estimate maturity per mechanism from its attached projects' symbol counts
    _refresh_maturity(conn)

    # anchor real code implementations
    anchored = _anchor_all(conn)
    _sync_fts(conn)
    print(f"anchored {anchored} code implementations")

    # fuse every analyzed project from analysis.db into the mechanisms by domain
    fused = _fuse_analysis(conn)
    print(f"fused {fused} analyzed projects into mechanisms")

    print(f"done: mechanisms={_count(conn, 'mechanisms')} "
          f"impls={_count(conn, 'implementations')} "
          f"instances={_count(conn, 'project_instances')} "
          f"scenes={_count(conn, 'scenes')}")
    return 0


def _fuse_analysis(conn: sqlite3.Connection) -> int:
    """Bridge every analyzed project from analysis.db into project_instances.

    Each analyzed project (repo-map Op2/Op3/Op4 output) is a real-world
    instance of a mechanism. It is attached to every curated mechanism in the
    same paradigm (domain) — so ``show <mechanism>`` lists the concrete
    projects + their mechanism summaries + work-log doc paths, and
    ``recommend`` counts real-instance support behind each mechanism.
    """
    if not ANALYSIS_DB.exists():
        print(f"  (analysis.db not found at {ANALYSIS_DB}; skip fusion)",
              file=sys.stderr)
        return 0
    adb = sqlite3.connect(str(ANALYSIS_DB))
    adb.row_factory = sqlite3.Row
    try:
        rows = adb.execute(
            "SELECT project_name, paradigm_id, why_worth, analysis_path, "
            "       source_type FROM analysis_index "
            "WHERE paradigm_id IS NOT NULL AND paradigm_id != '' "
            "  AND project_name IS NOT NULL AND project_name != '' "
            "  AND (status='analyzed' OR status='completed')").fetchall()
    except sqlite3.Error as e:
        print(f"  (analysis.db read failed: {e})", file=sys.stderr)
        return 0
    finally:
        adb.close()

    # curated mechanisms by domain
    mechs_by_domain = {}
    for m in conn.execute("SELECT id, domain FROM mechanisms"):
        mechs_by_domain.setdefault(m["domain"], []).append(m["id"])

    inserted = 0
    for r in rows:
        dom = r["paradigm_id"]
        for mech_id in mechs_by_domain.get(dom, []):
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO project_instances "
                    "(mechanism_id, project_name, domain, why_worth, "
                    " analysis_path, source_type) VALUES (?,?,?,?,?,?)",
                    (mech_id, r["project_name"], dom,
                     r["why_worth"] or "", r["analysis_path"] or "",
                     r["source_type"] or ""))
                inserted += 1
            except sqlite3.Error:
                pass
    conn.commit()
    return inserted


def _refresh_maturity(conn: sqlite3.Connection) -> None:
    """Set maturity = mean of attached corpus symbol counts (normalized)."""
    if not REFCODE_DB.exists():
        return
    try:
        rc = sqlite3.connect(f"file:{REFCODE_DB}?mode=ro", uri=True, timeout=30)
        for mech_id, slug_hints in SLUG_ATTACHMENTS.items():
            counts = []
            for slug, _hints in slug_hints:
                c = rc.execute("SELECT COUNT(*) FROM ref_symbols WHERE project=?",
                               (slug,))
                counts.append(c.fetchone()[0])
            if counts:
                avg = sum(counts) / len(counts)
                # log-scale so maturity differentiates across projects (16K vs
                # 170K symbols) instead of saturating every big corpus at 1.0
                mat = min(1.0, math.log10(avg + 1) / math.log10(200_000))
                conn.execute("UPDATE mechanisms SET maturity=? WHERE id=?",
                             (mat, mech_id))
        conn.commit()
        rc.close()
    except Exception:
        pass


def _maturity_for(name: str) -> float:
    if not REFCODE_DB.exists():
        return 0.0
    try:
        conn = sqlite3.connect(f"file:{REFCODE_DB}?mode=ro", uri=True, timeout=20)
        c = conn.execute("SELECT COUNT(*) FROM ref_symbols WHERE project LIKE ?",
                         (f"%{name.lower()}%",))
        n = c.fetchone()[0]
        conn.close()
        return min(1.0, n / 5000)
    except Exception:
        return 0.0


def _sync_fts(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM mechanism_fts")
    for m in conn.execute("SELECT id,name,domain,definition,scenes FROM mechanisms"):
        conn.execute(
            "INSERT INTO mechanism_fts(id,name,domain,definition,scenes) "
            "VALUES (?,?,?,?,?)",
            (m["id"], m["name"], m["domain"], m["definition"], m["scenes"]))
    conn.commit()


def _count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _cmd_list(conn: sqlite3.Connection, args) -> int:
    dom = args.domain
    q = "SELECT id,name,domain,maturity,(SELECT COUNT(*) FROM implementations i WHERE i.mechanism_id=m.id) n_impl FROM mechanisms m"
    rows = list(conn.execute(q))
    if dom:
        rows = [r for r in rows if r["domain"] == dom]
    rows.sort(key=lambda r: r["n_impl"], reverse=True)
    for r in rows:
        print(f"[{r['id']}] {r['name']:40} {r['domain']:4} "
              f"maturity={r['maturity']:.2f} impls={r['n_impl']}")
    print(f"({len(rows)} mechanisms)")
    return 0


def _cmd_show(conn: sqlite3.Connection, args) -> int:
    m = conn.execute("SELECT * FROM mechanisms WHERE id=? OR name=?", (args.id, args.id)).fetchone()
    if not m:
        print(f"no mechanism '{args.id}'", file=sys.stderr)
        return 1
    print(f"== {m['name']}  [{m['domain']} {m['domain_name']}] ==")
    print(f"id: {m['id']}  maturity={m['maturity']:.2f}")
    print(f"\ndefinition:\n  {m['definition']}")
    if m["scenes"]:
        print(f"\nscenes: {m['scenes']}")
    if m["pros"]:
        print(f"\npros: {m['pros']}")
    if m["cons"]:
        print(f"\ncons: {m['cons']}")
    impls = conn.execute(
        "SELECT slug,module,sym,line,impl_note FROM implementations "
        "WHERE mechanism_id=? ORDER BY slug LIMIT 15", (m["id"],)).fetchall()
    print(f"\nimplementations ({len(impls)}):")
    for i in impls:
        loc = f" @{i['line']}" if i["line"] else ""
        print(f"  [{i['slug']}] {i['module']}/{i['sym']}{loc}")
        if i["impl_note"] and i["impl_note"] != f"symbol {i['sym']} at ...":
            print(f"      {i['impl_note']}")
    docs = json.loads(m["source_docs"] or "[]")
    if docs:
        print(f"\nsource docs: {len(docs)}")
        for d in docs[:5]:
            print(f"  {Path(d).name}")

    insts = conn.execute(
        "SELECT project_name, why_worth, analysis_path FROM project_instances "
        "WHERE mechanism_id=? ORDER BY project_name LIMIT 12", (m["id"],)).fetchall()
    n_inst = conn.execute(
        "SELECT COUNT(*) FROM project_instances WHERE mechanism_id=?",
        (m["id"],)).fetchone()[0]
    if n_inst:
        print(f"\nreal-world projects ({n_inst}):")
        for i in insts:
            tag = f" ({Path(i['analysis_path']).name})" if i["analysis_path"] else ""
            summary = (i["why_worth"] or "")[:90]
            print(f"  • {i['project_name']}{tag}")
            if summary:
                print(f"      {summary}")
        if n_inst > len(insts):
            print(f"  … +{n_inst - len(insts)} more")
    return 0


def _cmd_recommend(conn: sqlite3.Connection, args) -> int:
    """Scene -> ranked mechanisms. rank = fit*0.45 + maturity*0.35 + domain*0.2."""
    scene_text = args.text
    rows = list(conn.execute(
        "SELECT id,name,domain,domain_name,definition,scenes,maturity FROM mechanisms"))
    scored = []
    for r in rows:
        s = _score_mechanism(r, scene_text)
        if s > 0:
            n_inst = conn.execute(
                "SELECT COUNT(*) FROM project_instances WHERE mechanism_id=?",
                (r["id"],)).fetchone()[0]
            scored.append((s, r["id"], r["name"], r["domain"],
                           r["maturity"], n_inst))
    scored.sort(reverse=True, key=lambda x: x[0])
    if not scored:
        print(f"(no mechanism scored >0 for '{scene_text}')")
        return 1
    print(f"Top {args.k} mechanisms for: {scene_text}\n")
    for s, mid, name, dom, mat, n_inst in scored[: args.k]:
        n_impl = conn.execute(
            "SELECT COUNT(*) FROM implementations WHERE mechanism_id=?",
            (mid,)).fetchone()[0]
        print(f"{s:5.3f}  [{mid}] {name}  ({dom})  maturity={mat:.2f} "
              f"impls={n_impl} projects={n_inst}")
    return 0


def _cmd_impl(conn: sqlite3.Connection, args) -> int:
    """Manually attach a code implementation anchor to a mechanism."""
    if not (args.mechanism and args.slug and args.module):
        print("usage: refcode mechanisms impl <mech> --slug P --module M [--sym S --line N --note T]",
              file=sys.stderr)
        return 2
    m = conn.execute("SELECT id FROM mechanisms WHERE id=? OR name=?", (args.mechanism, args.mechanism)).fetchone()
    if not m:
        print(f"no mechanism '{args.mechanism}'", file=sys.stderr)
        return 1
    conn.execute(
        "INSERT OR REPLACE INTO implementations "
        "(mechanism_id,slug,module,sym,line,impl_note) VALUES (?,?,?,?,?,?)",
        (m["id"], args.slug, args.module, args.sym, args.line, args.note or ""))
    conn.commit()
    print(f"anchored [{m['id']}] <- {args.slug}/{args.module}{f'@{args.line}' if args.line else ''}")
    return 0


def _cmd_scene(conn: sqlite3.Connection, args, add: bool = False) -> int:
    if add:
        conn.execute("INSERT OR REPLACE INTO scenes (id,description,domain,keywords) VALUES (?,?,?,?)",
                     (args.id, args.desc or "", args.domain or "",
                      json.dumps(args.keywords.split(",") if args.keywords else [])))
        conn.commit()
        print(f"scene {args.id} added")
        return 0
    rows = list(conn.execute("SELECT id,description,domain FROM scenes"))
    for r in rows:
        print(f"[{r['id']}] ({r['domain'] or '-'}) {r['description']}")
    return 0


def _now() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_mech_parser(sub) -> None:
    pm = sub.add_parser("mechanisms", help="mechanism-level knowledge system "
                        "(design answers + scene recommendation)")
    pm.add_argument("--mech-db", default=None, help="override mechanisms.db path")
    pms = pm.add_subparsers(dest="action", required=True)
    pms.add_parser("build", help="auto-extract mechanisms from work-log + analysis.db").set_defaults(func=cmd_mechanisms)
    pml = pms.add_parser("list", help="list mechanisms")
    pml.add_argument("--domain", default=None)
    pml.set_defaults(func=cmd_mechanisms)
    pmsh = pms.add_parser("show", help="show a mechanism's full profile")
    pmsh.add_argument("id")
    pmsh.set_defaults(func=cmd_mechanisms)
    pmr = pms.add_parser("recommend", help="scene -> ranked mechanisms")
    pmr.add_argument("text")
    pmr.add_argument("-k", type=int, default=5)
    pmr.set_defaults(func=cmd_mechanisms)
    pmi = pms.add_parser("impl", help="attach a code implementation anchor to a mechanism")
    pmi.add_argument("mechanism")
    pmi.add_argument("--slug", required=True)
    pmi.add_argument("--module", required=True)
    pmi.add_argument("--sym", default=None)
    pmi.add_argument("--line", type=int, default=None)
    pmi.add_argument("--note", default=None)
    pmi.set_defaults(func=cmd_mechanisms)
    pmsc = pms.add_parser("scene", help="list/add scenes")
    pmsc.add_argument("subaction", nargs="?", default="list", choices=["list", "add"])
    pmsc.add_argument("id", nargs="?")
    pmsc.add_argument("--desc", default=None)
    pmsc.add_argument("--domain", default=None)
    pmsc.add_argument("--keywords", default=None)
    pmsc.set_defaults(func=cmd_mechanisms)


if __name__ == "__main__":
    p = argparse.ArgumentParser(prog="mechanisms")
    p.add_argument("--mech-db", default=None)
    sub = p.add_subparsers(dest="action", required=True)
    build_mech_parser(sub)
    args = p.parse_args()
    raise SystemExit(cmd_mechanisms(args))