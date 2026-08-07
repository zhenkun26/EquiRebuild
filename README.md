# Hermes Agent Hardening

> 对 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的二次开发工作区：首个交付是可复用的 Hermes 用户技能 **hardening-review**，把「对抗性生产级审查」固化为标准流程，并用它完成了本仓库自身的加固闭环（dogfooding）。
>
> A secondary-development workspace on top of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent). Its first deliverable is **hardening-review**, a reusable Hermes user skill that turns adversarial production-grade review into a standard process — and the repo itself was hardened with it (dogfooding).

[![OpenSpec](https://img.shields.io/badge/OpenSpec-spec--driven-6f42c1)](openspec/specs)
[![Python](https://img.shields.io/badge/Python-stdlib%20only-3776AB)](hermes-skills/hardening-review/scripts/hardening_scan.py)
[![Tests](https://img.shields.io/badge/Tests-49%20passed-2ea44f)](docs/ACCEPTANCE_REPORT.md)
[![Coverage](https://img.shields.io/badge/Coverage-94%25-2ea44f)](docs/ACCEPTANCE_REPORT.md)
[![CI](https://github.com/zhenkun26/hermes-agent-hardening/actions/workflows/ci.yml/badge.svg)](https://github.com/zhenkun26/hermes-agent-hardening/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-green)](https://opensource.org/licenses/MIT)

---

## 一、项目定位 / Positioning

基于 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的二次开发工作区：

- 规划由 [OpenSpec](https://openspec.dev) 驱动，全程**不修改上游克隆** / Everything is OpenSpec-driven; the upstream clone is **never modified**
- 所有开发都落在本工作区，技能通过 Hermes 标准用户技能目录（`~/.hermes/skills/`）安装 / All development lives in this workspace; skills install into the Hermes user skills directory (`~/.hermes/skills/`)
- 交付即 dogfooding：技能先审查自身代码，再对外复用 / Shipped via dogfooding: the skill audits its own code before reuse

---

## 二、核心交付 / Core Deliverable

**`hardening-review`** 对目标代码库执行「即将部署到生产环境」级别的最终审查，输出按严重度分级的发现、修复 diff、测试与部署建议。

**`hardening-review`** performs an "about-to-deploy to production" final review of a target codebase, producing severity-graded findings, fix diffs, and testing/deployment advice.

> **核心标准 / Core standard**：穷尽手段寻找必现崩溃、数据丢失、安全入侵与性能雪崩隐患 / exhaustively hunt for guaranteed crashes, data loss, security intrusions, and performance-meltdown risks.

### 五个审查维度 / Five review dimensions

| 维度 / Dimension | 关注点 / Focus |
|:---|:---|
| D1 逻辑黑洞与竞态 / Logic holes & races | Check-Then-Act 竞态、缺少 Saga 补偿、`except Exception: pass` 吞异常 / check-then-act races, missing Saga compensation, swallowed exceptions |
| D2 隐性性能杀手 / Hidden performance killers | N+1 查询、阻塞事件循环、HTTP 客户端无超时/重试 / N+1 queries, event-loop blocking, HTTP clients without timeout/retry |
| D3 致命安全漏洞 / Critical security flaws | 注入、硬编码密钥（JWT Secret / AK/SK）、水平/垂直越权 / injection, hardcoded secrets, horizontal/vertical privilege escalation |
| D4 配置与环境幻觉 / Config & environment delusions | 本地绝对路径、未校验的环境变量静默失败 / local absolute paths, unvalidated env vars failing silently |
| D5 日志与可观测性 / Logging & observability | 敏感日志、关键链路缺少 TraceId 透传 / sensitive logs, missing TraceId propagation |

发现一律标注 `[严重][P0]` 或 `[中危][P1]`，并附具体文件位置与可复现的攻击/故障案例；某维度无发现时明确写 **clean**，不允许省略。

Findings are always labeled `[严重][P0]` or `[中危][P1]` with exact file locations and reproducible attack/failure cases; a dimension with no findings must explicitly state **clean**.

---

## 三、机械扫描器 / Mechanical Scanner

**`hardening_scan.py`**（纯 stdlib，无第三方依赖）自动检测 / A stdlib-only scanner that automatically detects:

- 裸 `except:` / `except X: pass` / bare `except:` and swallowed exceptions
- HTTP 客户端无显式 `timeout`（import 感知，避免误报同名 SDK 构造器）/ HTTP clients without explicit `timeout` (import-aware, avoiding false positives on same-named SDK constructors)
- 硬编码密钥（`sk-` / `AKIA` / `ghp_` / `glpat-` / `xox*-` / `AIza` 前缀、私钥块与常见键名赋值；`<YOUR_...>` / `REPLACE_WITH_*` 等占位符自动豁免）/ hardcoded secrets (`sk-`, `AKIA`, `ghp_`, `glpat-`, `xox*-`, `AIza` prefixes, private-key blocks and common key-name assignments; placeholders like `<YOUR_...>` are auto-exempted)
- 本地绝对路径 / local absolute paths
- 非 UTF-8 文件 / non-UTF-8 files

行级正则发现标记 `[manual]`，需人工确认 / line-level regex hits are tagged `[manual]` for human confirmation.

```bash
python3 hermes-skills/hardening-review/scripts/hardening_scan.py <target> \
  [--output report.md] [--exclude GLOB ...] [--config PATH] [--no-config]
```

或安装后用入口命令（见下文「开发环境」）/ or use the installed entry point (see "Development" below)：

```bash
hardening-scan <target> ...
```

退出码 / Exit codes：

| 退出码 / Code | 含义 / Meaning |
|:---:|:---|
| `0` | 无发现 / no findings |
| `1` | 有发现 / findings present |
| `2` | 用法或目标错误 / usage or target error |

缺失目标必报错，绝不静默通过 / a missing target always errors — never silently passes.

**抑制与配置 / Suppression & config**：

- 行内豁免：`# hardening-scan: ignore=RULE_ID`（或省略 `=RULE_ID` 豁免该行全部规则）/ inline suppression: `# hardening-scan: ignore=RULE_ID` (omit `=RULE_ID` to suppress all rules on that line)
- 仓级配置 `.hardening-scan.toml`（自动从目标目录或 CWD 发现）：`exclude = [...]` 与 `disable-rules = [...]` / repo-level `.hardening-scan.toml` (auto-discovered from the target dir or CWD) with `exclude` and `disable-rules`
- `hardening-scan --list-rules` 查看规则注册表（规则 ID、级别、维度）/ inspect the rule registry (IDs, severities, dimensions)

---

## 四、安装与使用 / Installation & Usage

安装为 Hermes 用户技能 / Install as a Hermes user skill：

```bash
cp -R hermes-skills/hardening-review ~/.hermes/skills/security/hardening-review
hermes skills reload   # 或重启会话 / or restart the session
```

然后在对话中直接使用 / Then use it directly in conversation：

```text
用 hardening-review 技能审查 <目标目录>，输出 P0/P1 发现与修复 diff
```

### 开发环境 / Development

```bash
uv venv && uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/python -m pytest tests/ -q        # 单元测试 / unit tests
.venv/bin/python -m ruff check hermes-skills tests
.venv/bin/hardening-scan .                  # dogfood 自扫 / self-scan
```

---

## 五、质量与验收 / Quality & Acceptance

详见 [docs/ACCEPTANCE_REPORT.md](docs/ACCEPTANCE_REPORT.md) / see the acceptance report for details：

| 指标 / Metric | 结果 / Result |
|:---|:---|
| 单元测试 / Unit tests | 49 个用例全绿（stdlib + pytest + `unittest.mock`，无网络调用；CI 矩阵 Python 3.11/3.12/3.13）/ 49 passing, offline; CI matrix across Python 3.11–3.13 |
| 覆盖率 / Coverage | `hardening_scan.py` 行覆盖率 **94%**（要求 ≥80%，pyproject 中 `fail_under = 80` 强制）/ 94% line coverage (threshold ≥80%, enforced via `fail_under = 80`) |
| 并发冒烟 / Concurrency smoke | 1000 次并发调用全部退出码符合预期（5.8s，无共享状态）/ 1000 concurrent calls, correct exit codes, no shared state |
| 上游零污染 / Upstream purity | `git -C hermes-agent status --porcelain` 恒为空 / always empty |
| 自审闭环 / Self-review loop | `hardening-scan .` 全仓扫描退出码 `0`（fixtures 经 `.hardening-scan.toml` 豁免，样本文本均用占位符）/ full-repo self-scan exits `0` (fixtures exempted via config, samples use placeholders) |

---

## 六、目录结构 / Project Structure

```
├── hermes-skills/hardening-review/   # 核心交付：Hermes 用户技能 / core deliverable
│   ├── SKILL.md                      # 5 维对抗审查程序（HARDLINE 合规）/ 5-dimension review procedure (HARDLINE compliant)
│   ├── scripts/hardening_scan.py     # 机械扫描器（纯 stdlib，退出码 0/1/2）/ mechanical scanner (stdlib-only)
│   └── templates/report_template.md  # 验收报告骨架（<YOUR_...> 占位符规范）/ acceptance report template
├── pyproject.toml                    # 打包与开发依赖（uv/pip 可复现安装）/ packaging & dev deps (reproducible install)
├── .hardening-scan.toml              # 扫描器仓级配置（豁免 fixtures 等）/ repo-level scanner config
├── .github/workflows/ci.yml          # CI：ruff + pytest + 覆盖率 + dogfood 扫描 / CI pipeline
├── tests/skills/                     # pytest 测试 + fixtures（无网络）/ offline tests & fixtures
├── deploy/                           # Kubernetes 清单（9 份，全部占位符）/ 9 K8s manifests (placeholders)
├── docs/ACCEPTANCE_REPORT.md         # 本次交付的综合验收报告 / comprehensive acceptance report
├── openspec/                         # OpenSpec 规格仓库 / OpenSpec spec repository
│   ├── specs/hardening-review/       # 主规格（已同步）/ main spec (synced)
│   └── changes/archive/              # 已归档变更 / archived changes
└── hermes-agent/                     # 上游只读克隆（参考，永不修改）/ upstream read-only clone (reference only)
```

---

## 七、开发流程（OpenSpec）/ Development Workflow

```text
$openspec-explore <想法>                          # 探索 / explore
$openspec-propose <change-name>                   # 立项（proposal/specs/design/tasks）/ propose
$openspec-apply-change                            # 实施 / implement
$openspec-sync-specs <change-name> && git commit specs   # 增量规格合并 / sync delta specs
$openspec-archive-change <change-name>            # 归档 / archive
```

项目上下文与约定（不修改上游、技能装 `~/.hermes/skills/`、交付模式）记录在 [openspec/config.yaml](openspec/config.yaml)。

Project context and conventions (no upstream changes, `~/.hermes/skills/` installs, delivery mode) live in [openspec/config.yaml](openspec/config.yaml).

---

## 八、部署 / Deployment

### Docker Compose（验证上游配置 / validate upstream config）

```bash
docker compose -f hermes-agent/docker-compose.yml config --quiet
HERMES_UID=$(id -u) HERMES_GID=$(id -g) docker compose -f hermes-agent/docker-compose.yml up -d
```

> 注意 / Note：dashboard 默认只绑定 `127.0.0.1`（存储 API 密钥），远程访问请走 SSH 隧道或反代认证 / the dashboard binds `127.0.0.1` by default (it stores API keys); use SSH tunneling or a reverse proxy with auth for remote access.

### Kubernetes（本仓库清单 / this repo's manifests）

```bash
kubectl apply -f deploy/            # namespace/configmap/secret/deployment/pdb/service/ingress/hpa/pvc
kubectl -n hermes get pods
```

使用前必须替换 / replace before use：

- `deploy/03-deployment.yaml` 中的 `<YOUR_REGISTRY>` 镜像地址（生产建议按 digest 固定）/ image registry (pin by digest in production)
- `deploy/02-secret.yaml` 中的占位 base64（`printf '<YOUR_VALUE>' | base64` 重新生成）/ placeholder base64 secrets
- `deploy/06-ingress.yaml` 中的 `<YOUR_DOMAIN>` / domain
- `deploy/08-pvc.yaml` 中的 `storageClassName`（RWX 存储类；单节点集群可改 `ReadWriteOnce`）/ storage class (RWX; use `ReadWriteOnce` on single-node clusters)

架构约束（有意为之）/ architectural constraints (intentional)：

- gateway 与 dashboard 共享同一个 PVC（挂载点 /opt/data，即 `~/.hermes` 状态）；不要用 `emptyDir`，它是 per-pod 的，会静默切断状态共享 / gateway and dashboard share one PVC mounted at /opt/data (`~/.hermes` state); do not use `emptyDir` — it is per-pod and silently breaks state sharing
- 会话状态在 pod 本地 SQLite，gateway 固定单副本 + `Recreate` 策略；`07-hpa.yaml` 的 `maxReplicas` 封顶为 1，状态外置前不要调大 / session state lives in pod-local SQLite, so the gateway is pinned to a single replica with `Recreate`; `07-hpa.yaml` caps `maxReplicas` at 1 — do not raise it before externalizing state
- Ingress 默认开启 basic-auth（fail-closed）：先 `htpasswd -c auth <YOUR_USERNAME> && kubectl -n hermes create secret generic hermes-dashboard-auth --from-file=auth`，否则 nginx 返回 503 / Ingress enables basic-auth by default (fail-closed): create the `hermes-dashboard-auth` secret first, or nginx returns 503

---

## 九、许可与致谢 / License & Acknowledgments

**MIT**。上游 Hermes Agent 版权归 [NousResearch](https://github.com/NousResearch) 所有，本仓库仅作学习与二次开发参考。

**MIT.** Upstream Hermes Agent is copyrighted by [NousResearch](https://github.com/NousResearch); this repository exists for learning and secondary development only.
