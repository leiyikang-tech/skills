# leiyikang-tech/skills

自建生成的 AI 编码技能，开源可用。每个技能一个目录，独立可安装，通过
`install.sh` 将模板中的 `{{PLACEHOLDER}}` 占位符替换为实际路径后，物化到本机
技能注册表（`~/.agents/skills/`）。GitHub 仓库保持纯净可移植，不包含任何本机
特定路径或私密数据。

## 技能清单

| 目录 | 技能 | 作用 |
|------|------|------|
| [`repo-map/`](repo-map/) | **repo-map** | 对一个新开源项目做端到端分析（5 步管线：init-deep → Profile → Comparative → Gap/Opportunity → Persist），含 harness 确定性质量门禁与深挖锚点机制 |
| [`awesome-map/`](awesome-map/) | **awesome-map** | 分析一个 awesome-list 的**成员项目与论文**——解析→按分析价值打分排序→纳入 waitlist→按序自动深挖。薄编排器，驱动 repo-map 的 awesome-list 模式 |

## 快速安装

### repo-map

```bash
cd repo-map
bash install.sh
```

默认安装到 `~/.agents/skills/repo-map`，并将 `{{PLACEHOLDER}}` 替换为
`~/.sisyphus/...` 下的默认路径。可用环境变量覆盖：

```bash
SKILL_DIR=~/.agents/skills \
REPO_MAP_HOME=~/.sisyphus/repo-map \
ANALYSIS_DB=~/.sisyphus/db/analysis.db \
REPOS_DIR=~/.sisyphus/repos \
KNOWLEDGE_REPO_URL=https://github.com/<you>/work-log.git \
KNOWLEDGE_REPO_DIR=~/.sisyphus/work-log \
  bash install.sh
```

### awesome-map

```bash
cd awesome-map
REPO_MAP_HOME=~/.sisyphus/repo-map bash install.sh
```

> awesome-map 依赖 **repo-map** 已安装（它驱动 repo-map 的 awesome-list 模式）。
> `REPO_MAP_HOME` 需指向已安装的 repo-map 技能目录。

## 占位符

安装器在安装时替换以下 `{{PLACEHOLDER}}` 令牌：

| 占位符 | 含义 |
|--------|------|
| `{{REPO_MAP_HOME}}` | repo-map 技能的安装目录 |
| `{{ANALYSIS_DB}}` | 共享分析数据库（SQLite）路径 |
| `{{REPOS_DIR}}` | 项目克隆目录 |
| `{{KNOWLEDGE_REPO_URL}}` | 知识库 git 仓库 URL（repo-map Op5 持久化目标） |
| `{{KNOWLEDGE_REPO_DIR}}` | 知识库本地克隆路径 |

## 隐私与脱敏

本仓库已对所有本机特定信息做脱敏处理：
- 所有 `/root/...` 机器路径 → `{{PLACEHOLDER}}` 令牌
- 所有 API 密钥 / PAT token / 网关地址 → 已移除
- 内部项目名与私有分析产物（`run.json`、`analysis.db`、`runs/` 等）→ 未打包

## License

MIT — see [LICENSE](LICENSE).