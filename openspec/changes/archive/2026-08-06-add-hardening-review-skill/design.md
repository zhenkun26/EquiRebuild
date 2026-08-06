## Context

目标代码库是 NousResearch/hermes-agent 的只读克隆（`hermes-agent/`，HEAD `8f27127`）。Hermes 的用户技能安装在 `~/.hermes/skills/`，技能编写须遵守 AGENTS.md 的 HARDLINE 标准（description ≤60 字符、现代章节顺序、工具名引用、`tests/skills/test_<skill>_skill.py` 测试约定）。上游已自带 `Dockerfile` 与 `docker-compose.yml`（gateway + dashboard，s6-overlay），但没有 Kubernetes 清单。动机见 proposal.md 的 Why；行为契约见 specs/hardening-review/spec.md。

## Goals / Non-Goals

**Goals:**
- 产出一个 HARDLINE 合规、可安装到 `~/.hermes/skills/security/hardening-review/` 的 Hermes 用户技能，包含 SKILL.md、stdlib-only 机械扫描脚本、报告模板。
- 用该技能对本次新增代码做对抗性自审并修复 P0/P1，测试覆盖 ≥80%，通过 1000 并发冒烟。
- 容器化：静态验证上游 `docker-compose.yml`；新增可静态校验的 `deploy/` K8s 清单（不含真实密钥）。
- 交付 `docs/ACCEPTANCE_REPORT.md` 综合验收报告。

**Non-Goals:**
- 不修改 `hermes-agent/` 上游克隆的任何文件。
- 不审查/重构 Hermes 全库（1116 个非测试 Python 文件）——那是后续独立变更。
- 不部署到真实 K8s 集群或实际启动完整 Hermes 容器（Docker Desktop 未运行）；以静态校验 + 文档化的可执行命令交付。
- 不把技能推送到上游 PR 或做成独立技能仓库——MVP 阶段先在工作区闭环。

## Decisions

### 1. 技能落盘位置与安装方式
技能开发在 `hermes-skills/hardening-review/`，安装即复制到 `~/.hermes/skills/security/hardening-review/`。
- 备选：放进上游 `optional-skills/` —— 拒绝，会污染只读克隆，且上游政策倾向独立仓库。
- 备选：单独技能仓库 —— 延后，MVP 先在工作区闭环。

### 2. 技能形态：SKILL.md + 机械扫描脚本 + 模板
- `SKILL.md` 承载 5 维审查程序（按 Hermes 现实适配：gateway 并发、SQLite/FTS5、插件信任、HTTP 超时、TraceId），引用 Hermes 原生工具名（`search_files`、`read_file`、`patch` 等）。
- `scripts/hardening_scan.py`：纯 stdlib（`ast`/`pathlib`/`re`/`sys`），对 Python 文件做 AST 扫描（裸 except、无超时 HTTP 客户端），对其他文件做行级正则扫描（硬编码密钥、绝对路径）。退出码：`0` 无发现 / `1` 有发现 / `2` 用法或目标错误，杜绝静默通过。
- 备选：纯提示词技能、无脚本 —— 拒绝：机械检查需要确定性输出、可测试性和并发冒烟对象。

### 3. 自审闭环（dogfood）
用本技能审查本次新增代码（`hermes-skills/`、`deploy/`、`tests/`），P0/P1 全部修复，修复 diff 与原因记录进验收报告。复用 auto-coding 仓库验证过的同一模式（其 `adversarial-hardening-review` 变更即此流程）。

### 4. 测试与验收
- 测试文件 `tests/skills/test_hardening_review_skill.py`：仅 stdlib + pytest + `unittest.mock`，用 `tmp_path` 构造夹具树，无网络。
- 覆盖率：`coverage run -m pytest tests/skills/test_hardening_review_skill.py` + `coverage report`，脚本行覆盖 ≥80%。
- 1000 并发冒烟：用 Python `concurrent.futures` 并发执行 1000 次 `hardening_scan.py`（与 auto-coding 先例一致），全部退出码符合预期。

### 5. 容器化与部署
- Compose：运行 `docker compose -f hermes-agent/docker-compose.yml config`（无需 daemon）做静态校验，并文档化 `HERMES_UID`/`HERMES_GID` 启动方式与 dashboard localhost 约束。
- K8s：按上游 compose 两个服务（gateway、dashboard）+ auto-coding 仓库的 00–07 清单模式，在 `deploy/` 新建 namespace/configmap/secret(占位)/deployment/pdb/service/ingress/hpa，镜像占位 `<YOUR_REGISTRY>/hermes-agent:v0.20.0`；用 Python `yaml.safe_load_all` 静态校验。
- 完整镜像构建与真实部署因 Docker Desktop 未运行而延后，命令写入报告。

## Risks / Trade-offs

- [正则扫描（密钥/绝对路径）会有误报] → 行级发现标记为"需人工确认"，并在 SKILL.md 的 Pitfalls 中说明；扫描目标默认排除 `tests/` 夹具中的刻意样本时在 CLI 中显式传入。
- [上游克隆是时间快照，未来上游会演进] → 在验收报告中固定参考 commit SHA（`8f27127`）。
- [Docker/K8s 只做静态校验，未真机验证] → 报告明确标注"待真机验证"并给出完整命令；用户启动 Docker Desktop 后可补跑。
- [1000 并发冒烟对象是扫描脚本而非网关服务] → 诚实适配：MVP 无运行中的服务，模板的并发验收目标映射为脚本并发调用；网关级压测列为后续变更。

## Migration Plan

1. 安装：`cp -R hermes-skills/hardening-review ~/.hermes/skills/security/hardening-review`，随后 `hermes skills reload`（或重启会话）。
2. 回滚：删除 `~/.hermes/skills/security/hardening-review/` 即可；部署侧 `docker compose down` / `kubectl rollout undo deployment/gateway`。
3. 对上游零影响：`git -C hermes-agent status --porcelain` 为空即证明未被污染。

## Open Questions

无——规格、方案与任务拆解不依赖任何未决问题；技能展示名暂用 `hardening-review`，后续可改。
