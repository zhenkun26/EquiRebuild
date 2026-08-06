## Why

用户要对 NousResearch 的 Hermes Agent 做二次开发。首个落地功能是一个可复用的新技能 `hardening-review`：把"对抗性生产级审查"方法论（5 维度扫描、P0/P1 分级、修复、测试、验收）固化为 Hermes 原生技能，作为以后所有二次开发的质量基线。本次交付本身即按"审查 → 修复 → 测试 → 容器化 → 验收报告"闭环完成，为后续功能开发跑通范式。

## What Changes

- 新增 Hermes 用户技能 `hardening-review`（category: `security`），开发于 `hermes-skills/hardening-review/`，按 Hermes HARDLINE 标准编写，可安装到 `~/.hermes/skills/security/hardening-review/`；**不修改上游克隆**。
- 技能内容：`SKILL.md`（5 维对抗审查程序，适配 Hermes 现实：gateway 并发、SQLite/FTS5、插件信任边界、HTTP 客户端超时、TraceId 透传）+ `scripts/hardening_scan.py`（机械扫描：裸 `except`、硬编码密钥、绝对路径、HTTP 客户端无超时等，仅 stdlib）+ `templates/report_template.md`（验收报告骨架）。
- 新增测试 `tests/skills/test_hardening_review_skill.py`（stdlib + pytest + `unittest.mock`，无网络调用），脚本覆盖率 ≥80%。
- 自审（dogfood）：应用该技能对自身脚本与工作区制品做对抗性审查，修复全部 P0/P1 并记录修复 diff。
- 容器化：验证上游 `docker-compose.yml`（gateway + dashboard）在本机构建/静态校验通过；新增工作区 `deploy/` K8s 清单（namespace / deployment / service / configmap / secret 占位 / ingress / hpa / pdb），YAML 静态校验。
- 交付 `docs/ACCEPTANCE_REPORT.md` 综合验收报告（项目概述、对抗性审查报告、验收测试、回滚预案），含 1000 并发冒烟结果。

## Capabilities

### New Capabilities
- `hardening-review`: hardening-review 技能的行为契约——5 维度扫描范围、P0/P1 分级规则、报告输出结构、验证要求、安装方式（用户技能目录，不触碰上游）。

### Modified Capabilities

（无——上游 hermes-agent 不被修改，工作区无既有 specs。）

## Impact

- 新增（工作区 EquiRebuild）：`hermes-skills/hardening-review/`（SKILL.md、`scripts/`、`templates/`）、`tests/skills/test_hardening_review_skill.py`、`deploy/*.yaml`、`docs/ACCEPTANCE_REPORT.md`、`openspec/changes/add-hardening-review-skill/*`。
- 不改动：`hermes-agent/` 上游克隆（只读参考）、上游 `Dockerfile` / `docker-compose.yml`。
- 运行依赖：Python 3.11+；本地验证用 uv/pytest；Docker 用于 Compose 校验；技能脚本仅依赖 Python stdlib，无新增第三方依赖。
