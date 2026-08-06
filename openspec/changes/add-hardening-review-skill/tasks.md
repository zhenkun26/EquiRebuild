## 1. 技能骨架与 SKILL.md

- [x] 1.1 创建 `hermes-skills/hardening-review/` 目录结构与 frontmatter（name / description 单句 ≤60 字符 / version / author / license / platforms / metadata.hermes.category=security）
- [x] 1.2 编写 `SKILL.md` 现代章节（When to Use / Prerequisites / How to Run / Quick Reference / Procedure / Pitfalls / Verification），5 维审查程序引用 Hermes 原生工具名
- [x] 1.3 编写 `templates/report_template.md`（项目概述 / 对抗性审查报告 / 验收测试 / 回滚预案四节 + `<YOUR_...>` 占位符规范）

## 2. 机械扫描脚本

- [x] 2.1 实现 `scripts/hardening_scan.py` CLI（目标路径、`--output`、退出码 0/1/2、缺失或非法参数快速失败）
- [x] 2.2 实现 AST 扫描：裸 `except`、HTTP 客户端无显式 timeout
- [x] 2.3 实现行级扫描：硬编码密钥、绝对路径；按 5 维度分组输出 P0/P1 与文件行号

## 3. 测试与覆盖率

- [x] 3.1 编写 `tests/skills/test_hardening_review_skill.py`：AST 发现、行级发现、无效参数、缺失目标、干净树无发现
- [x] 3.2 pytest 全绿（stdlib + pytest + mock，无网络）
- [x] 3.3 覆盖率 ≥80% 验证（coverage 报告）
- [x] 3.4 1000 并发冒烟通过（`concurrent.futures` 并发调用脚本，全部退出码符合预期）

## 4. 对抗性自审与修复

- [x] 4.1 用本技能对 `hermes-skills/`、`tests/`、`deploy/` 做 5 维对抗性审查，输出发现清单
- [x] 4.2 修复全部 P0/P1（异常处理、边界、编码、密钥、可观测性），记录修复 diff
- [x] 4.3 复查无新增 P0/P1；`git -C hermes-agent status --porcelain` 为空（上游未被污染）

## 5. 容器化与 K8s 清单

- [x] 5.1 `docker compose -f hermes-agent/docker-compose.yml config` 静态校验通过并记录
- [x] 5.2 编写 `deploy/00-namespace.yaml` 与 `deploy/01-configmap.yaml`
- [x] 5.3 编写 `deploy/02-secret.yaml`（全部占位符，无真实密钥）
- [x] 5.4 编写 `deploy/03-deployment.yaml`（gateway + dashboard，镜像占位 `<YOUR_REGISTRY>/hermes-agent:v0.20.0`，非 root）
- [x] 5.5 编写 `deploy/04-pdb.yaml`、`deploy/05-service.yaml`、`deploy/06-ingress.yaml`、`deploy/07-hpa.yaml`
- [x] 5.6 全部 manifest YAML 静态校验通过且不含真实密钥

## 6. 验收报告与收尾

- [x] 6.1 生成 `docs/ACCEPTANCE_REPORT.md`（项目概述 / 对抗性审查报告含修复 diff / 验收测试含并发与 curl / 回滚预案）
- [x] 6.2 安装技能到 `~/.hermes/skills/security/hardening-review/` 并验证可加载
- [x] 6.3 `openspec validate` 通过，提交变更制品与实现
