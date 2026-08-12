# EquiRebuild

> 本项目是 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的二次开发工作区。首个交付为可复用的 Hermes 用户技能 **hardening-review**：将「对抗性生产级审查」固化为标准流程，并以该技能完成本仓库自身的加固（dogfooding）。
>
> A secondary-development workspace based on [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent). Its first deliverable is **hardening-review**, a reusable Hermes user skill that standardizes adversarial production-grade review. The repository itself was hardened with the same skill (dogfooding).

[![OpenSpec](https://img.shields.io/badge/OpenSpec-spec--driven-6f42c1)](openspec/specs)
[![Python](https://img.shields.io/badge/Python-stdlib%20only-3776AB)](hermes-skills/hardening-review/scripts/hardening_scan.py)
[![Tests](https://img.shields.io/badge/Tests-57%20passed-2ea44f)](docs/ACCEPTANCE_REPORT.md)
[![Coverage](https://img.shields.io/badge/Coverage-95%25-2ea44f)](docs/ACCEPTANCE_REPORT.md)
[![CI](https://github.com/zhenkun26/EquiRebuild/actions/workflows/ci.yml/badge.svg)](https://github.com/zhenkun26/EquiRebuild/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-green)](https://opensource.org/licenses/MIT)

---

## 一、项目定位 / Positioning

本工作区的三条基本约定：

- 规划由 [OpenSpec](https://openspec.dev) 驱动；上游克隆始终保持只读，不做任何修改。
- 所有开发成果均位于本工作区，技能通过 Hermes 标准用户技能目录（`~/.hermes/skills/`）安装。
- 交付遵循 dogfooding 原则：技能先用于审查自身代码，再对外复用。

English equivalent:

- Planning is driven by [OpenSpec](https://openspec.dev); the upstream clone is never modified.
- All development lives in this workspace; skills are installed into the Hermes user skills directory (`~/.hermes/skills/`).
- Delivery follows a dogfooding policy: the skill audits its own code before reuse.

---

## 二、核心交付 / Core Deliverable

**`hardening-review`** 对目标代码库执行面向生产部署的最终审查，输出按严重度分级的发现、修复差异（diff）以及测试与部署建议。

**`hardening-review`** performs a final pre-production review of a target codebase and produces severity-graded findings, fix diffs, and testing and deployment recommendations.

> **核心标准 / Core standard**：系统排查可能导致确定性崩溃、数据丢失、安全入侵与性能雪崩的风险点 / systematically identify risks that may lead to deterministic crashes, data loss, security intrusions, or performance meltdowns.

### 五个审查维度 / Five review dimensions

| 维度 / Dimension | 关注点 / Focus |
|:---|:---|
| D1 逻辑缺陷与竞态条件 / Logic defects & race conditions | Check-Then-Act 竞态、缺少 Saga 补偿、`except Exception: pass` 吞异常 / check-then-act races, missing Saga compensation, swallowed exceptions |
| D2 潜在性能瓶颈 / Potential performance bottlenecks | N+1 查询、阻塞事件循环、HTTP 客户端无超时/重试 / N+1 queries, event-loop blocking, HTTP clients without timeout/retry |
| D3 安全漏洞 / Security vulnerabilities | 注入、硬编码密钥（JWT Secret / AK/SK）、水平/垂直越权 / injection, hardcoded secrets, horizontal/vertical privilege escalation |
| D4 配置与环境假设 / Configuration & environment assumptions | 本地绝对路径、未校验的环境变量静默失败 / local absolute paths, unvalidated env vars failing silently |
| D5 日志与可观测性 / Logging & observability | 敏感日志、关键链路缺少 TraceId 透传 / sensitive logs, missing TraceId propagation |

所有发现均标注 `[严重][P0]` 或 `[中危][P1]`，并给出具体文件位置与可复现的攻击或故障场景；若某维度无发现，报告中须明确标注 **clean**，不得省略。

Every finding is labeled `[严重][P0]` or `[中危][P1]` with an exact file location and a reproducible attack or failure scenario. A dimension with no findings must be explicitly marked **clean**.

---

## 三、代码体检 / Code Health Check

**`hardening_scan.py`** 仅依赖 Python 标准库，自动检测以下问题：

- 裸 `except:` 与 `except X: pass` 等吞异常写法；
- HTTP 客户端未显式设置 `timeout`（import 感知，可避免同名 SDK 构造器的误报；实例级追踪——构造器已传入 `timeout=` 的实例，其后续方法调用不再标记，未设置超时的实例则会被标记）；
- 硬编码密钥（`sk-` / `AKIA` / `ghp_` / `glpat-` / `xox*-` / `AIza` 等前缀、私钥块与常见键名赋值；`<YOUR_...>`、`REPLACE_WITH_*` 等占位符自动豁免；高熵字符串作为辅助信号，标记 `[manual]` 待人工确认）；
- 本地绝对路径；
- 非 UTF-8 文件。

行级正则发现的条目会标记 `[manual]`，需人工确认后再处理。

**`hardening_scan.py`** is a stdlib-only scanner that automatically detects:

- bare `except:` clauses and swallowed exceptions (`except X: pass`);
- HTTP clients without an explicit `timeout` (import-aware, avoiding false positives on same-named SDK constructors; instance-level tracking — method calls on clients built with `timeout=` are cleared, while calls on timeout-less clients are flagged);
- hardcoded secrets (`sk-`, `AKIA`, `ghp_`, `glpat-`, `xox*-`, `AIza` prefixes, private-key blocks, and common key-name assignments; placeholders such as `<YOUR_...>` and `REPLACE_WITH_*` are auto-exempted; high-entropy strings serve as a secondary `[manual]` signal);
- local absolute paths;
- non-UTF-8 files.

Line-level regex hits are tagged `[manual]` for human confirmation.

```bash
python3 hermes-skills/hardening-review/scripts/hardening_scan.py <target> \
  [--output report.md] [--exclude GLOB ...] [--config PATH] [--no-config]
```

安装后也可使用入口命令（见「开发环境」）：

```bash
hardening-scan <target> ...
```

退出码约定：

| 退出码 / Code | 含义 / Meaning |
|:---:|:---|
| `0` | 无发现 / no findings |
| `1` | 有发现 / findings present |
| `2` | 用法或目标错误 / usage or target error |

目标路径缺失时直接报错，不会静默通过。

**抑制与配置 / Suppression & configuration**：

- 行内豁免：`# hardening-scan: ignore=RULE_ID`（省略 `=RULE_ID` 表示豁免该行全部规则）；
- 仓级配置 `.hardening-scan.toml`（自动从目标目录或当前工作目录发现）：支持 `exclude = [...]` 与 `disable-rules = [...]`；
- `hardening-scan --list-rules` 可查看规则注册表（规则 ID、级别、维度）。

---

## 四、安装与使用 / Installation & Usage

安装为 Hermes 用户技能：

```bash
./hermes-skills/hardening-review/install.sh          # 安装到 ~/.hermes/skills/security/hardening-review
./hermes-skills/hardening-review/install.sh --check  # 校验已安装副本与源码一致
hermes skills reload   # 或重启会话
```

（等价的手工方式：`cp -R hermes-skills/hardening-review ~/.hermes/skills/security/hardening-review`）

然后在对话中直接使用：

```text
用 hardening-review 技能审查 <目标目录>，输出 P0/P1 发现与修复 diff
```

### 开发环境 / Development

```bash
uv venv && uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/python -m pytest tests/ -q        # 单元测试
.venv/bin/python -m ruff check hermes-skills tests
.venv/bin/hardening-scan .                  # dogfood 自扫
```

---

## 五、质量与验收 / Quality & Acceptance

详细数据见 [docs/ACCEPTANCE_REPORT.md](docs/ACCEPTANCE_REPORT.md)：

| 指标 / Metric | 结果 / Result |
|:---|:---|
| 单元测试 / Unit tests | 57 个用例全部通过（stdlib + pytest + `unittest.mock`，无网络调用；CI 覆盖 Python 3.11/3.12/3.13）/ 57 passing, offline; CI matrix across Python 3.11–3.13 |
| 覆盖率 / Coverage | `hardening_scan.py` 行覆盖率 **95%**（阈值 ≥80%，由 `pyproject.toml` 中 `fail_under = 80` 强制）/ 95% line coverage (threshold ≥80%, enforced via `fail_under = 80`) |
| 并发冒烟 / Concurrency smoke | 1000 次并发调用，退出码全部符合预期（5.8s，无共享状态）/ 1000 concurrent calls with expected exit codes; no shared state |
| 上游零修改 / Upstream purity | `git -C hermes-agent status --porcelain` 始终为空 / always empty |
| 自审闭环 / Self-review loop | 对全仓库执行 `hardening-scan .` 退出码为 `0`（fixtures 经 `.hardening-scan.toml` 豁免，样本文本均使用占位符）/ full-repo `hardening-scan .` exits `0` (fixtures exempted via config; samples use placeholders) |

---

## 六、目录结构 / Project Structure

```
├── hermes-skills/hardening-review/   # 核心交付：Hermes 用户技能 / core deliverable
│   ├── SKILL.md                      # 5 维对抗审查程序（HARDLINE 合规）/ 5-dimension review procedure (HARDLINE compliant)
│   ├── install.sh                    # 安装与校验脚本（目标 ~/.hermes/skills/）/ install & verify script
│   ├── scripts/hardening_scan.py     # 代码体检（纯 stdlib，退出码 0/1/2）/ code health check (stdlib-only)
│   └── templates/report_template.md  # 验收报告骨架（<YOUR_...> 占位符规范）/ acceptance report template
├── pyproject.toml                    # 打包与开发依赖（uv/pip 可复现安装）/ packaging & dev dependencies (reproducible install)
├── .hardening-scan.toml              # 扫描器仓级配置（豁免 fixtures 等）/ repo-level scanner configuration
├── .github/workflows/ci.yml          # CI：ruff + pytest + 覆盖率 + dogfood 扫描 / CI pipeline
├── tests/skills/                     # pytest 测试与 fixtures（无网络）/ offline tests & fixtures
├── deploy/                           # Kubernetes 清单（9 份，全部占位符）/ 9 K8s manifests (placeholders)
├── docs/ACCEPTANCE_REPORT.md         # 综合验收报告 / comprehensive acceptance report
├── openspec/                         # OpenSpec 规格仓库 / OpenSpec spec repository
│   ├── specs/hardening-review/       # 主规格（已同步）/ main spec (synced)
│   └── changes/archive/              # 已归档变更 / archived changes
└── hermes-agent/                     # 上游只读克隆（仅作参考）/ upstream read-only clone (reference only)
```

---

## 七、开发流程 / Development Workflow

```text
$openspec-explore <想法>                          # 探索 / explore
$openspec-propose <change-name>                   # 立项（proposal/specs/design/tasks）/ propose
$openspec-apply-change                            # 实施 / implement
$openspec-sync-specs <change-name> && git commit specs   # 增量规格合并 / sync delta specs
$openspec-archive-change <change-name>            # 归档 / archive
```

项目上下文与约定（不修改上游、技能安装到 `~/.hermes/skills/`、交付模式）记录在 [openspec/config.yaml](openspec/config.yaml)。

Project context and conventions (no upstream changes, `~/.hermes/skills/` installation, delivery mode) are recorded in [openspec/config.yaml](openspec/config.yaml).

---

## 八、部署 / Deployment

### Docker Compose（验证上游配置 / validate upstream configuration）

```bash
docker compose -f hermes-agent/docker-compose.yml config --quiet
HERMES_UID=$(id -u) HERMES_GID=$(id -g) docker compose -f hermes-agent/docker-compose.yml up -d
```

> 注意 / Note：dashboard 默认只绑定 `127.0.0.1`（其存储 API 密钥），远程访问应使用 SSH 隧道或带认证的反向代理 / the dashboard binds `127.0.0.1` by default (it stores API keys); use SSH tunneling or an authenticated reverse proxy for remote access.

### Kubernetes（本仓库清单 / manifests in this repository）

```bash
kubectl apply -f deploy/            # namespace/configmap/secret/deployment/pdb/service/ingress/hpa/pvc
kubectl -n hermes get pods
```

应用前需要替换以下占位符：

- `deploy/03-deployment.yaml` 中的 `<YOUR_REGISTRY>` 镜像地址（生产环境建议固定镜像 digest 以保证可复现）；
- `deploy/02-secret.yaml` 中的占位 base64（用 `printf '<YOUR_VALUE>' | base64` 重新生成）；
- `deploy/06-ingress.yaml` 中的 `<YOUR_DOMAIN>`；
- `deploy/08-pvc.yaml` 中的 `storageClassName`（RWX 存储类；单节点集群可改用 `ReadWriteOnce`）。

设计约束：

- gateway 与 dashboard 共享同一 PVC（挂载点为 `/opt/data`，对应 `~/.hermes` 状态）。`emptyDir` 的生命周期与 Pod 绑定，无法跨 Pod 共享状态，不应使用；
- 会话状态存放于 Pod 本地 SQLite，因此 gateway 固定单副本并采用 `Recreate` 更新策略；`07-hpa.yaml` 将 `maxReplicas` 上限设为 1，状态外置之前不宜调整；
- Ingress 默认启用 basic-auth（fail-closed）：需先创建 `hermes-dashboard-auth` Secret（`htpasswd -c auth <YOUR_USERNAME> && kubectl -n hermes create secret generic hermes-dashboard-auth --from-file=auth`），否则 nginx 返回 503。

---

## 九、变更日志 / Changelog

### 2026-08-07 — 检测能力增强 / Detection enhancements（`1ecd0fe`）

- 实例级 timeout 追踪：构造器已传入 `timeout=` 的实例，其方法调用不再标记；未设置默认超时的实例（包括 `requests.Session`）的方法调用会被标记；
- 新增熵检测规则 `HIGH_ENTROPY_STRING`（P1，仅 `[manual]` 通道，Shannon 熵 ≥ 4.5）；
- SKILL.md 升至 `0.2.0`；新增 `install.sh`；测试 49 → 57，覆盖率 94% → 95%。

### 2026-08-07 — 工程化重构 / Engineering refactor（`f9e7e12`）

- 打包与 CI：新增 `pyproject.toml` 与 GitHub Actions（Python 3.11–3.13 矩阵）；
- 抑制机制：行内 `# hardening-scan: ignore=RULE_ID` 与仓级 `.hardening-scan.toml`；
- 误报优化：HTTP 检查改为 import 感知；密钥检测增加占位符白名单与新前缀；
- 规则注册表与 `--list-rules`；测试 30 → 49；
- K8s 修正：共享 PVC、与单副本策略一致的 PDB/HPA、Ingress basic-auth fail-closed。

### 2026-08-06 — 首次交付 / Initial delivery（`c2eb841`）

- 交付 `hardening-review` 技能、代码体检、报告模板、30 个测试用例、8 份 K8s 清单与综合验收报告。

---

## 十、许可与致谢 / License & Acknowledgments

本项目以 **MIT** 许可发布。上游 Hermes Agent 版权归 [NousResearch](https://github.com/NousResearch) 所有，本仓库仅用于学习与二次开发。

This project is released under the **MIT** license. Upstream Hermes Agent is copyrighted by [NousResearch](https://github.com/NousResearch); this repository exists for learning and secondary development only.

> 本项目由 Vibe Coding 辅助实现落地。Built with Vibe Coding.
