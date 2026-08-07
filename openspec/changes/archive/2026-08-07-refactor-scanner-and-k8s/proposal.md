## Why

仓库审查发现一批工程化缺陷：无依赖清单与 CI、扫描器无抑制机制（fixtures 脏样本导致全仓自扫无法闭环）、K8s 清单自相矛盾（emptyDir 切断状态共享、PDB 与单副本冲突、HPA 可扩崩状态）、密钥与 HTTP 检查存在误报。本变更对扫描器与部署清单做一轮规格外重构补齐，并保持"纯 stdlib"承诺不变。

## What Changes

- **打包与 CI**：新增 `pyproject.toml`（`hardening-scan` 入口、dev extras、`fail_under = 80`）与 `.github/workflows/ci.yml`（ruff + pytest + 覆盖率 + dogfood + kubeval，Python 3.11–3.13 矩阵）。
- **抑制机制**：行内 `# hardening-scan: ignore=RULE_ID`；仓级 `.hardening-scan.toml`（`exclude`/`disable-rules`，自动发现）；`--config`/`--no-config`；配置 exclude 与 CLI `--exclude` 叠加。
- **退出码与去重**：BrokenPipe 保留判定码；NON_UTF8 按文件去重；跳过 `.ruff_cache` 等缓存目录。
- **误报修正**：HTTP 检查改为 import 感知（`HttpBindings`），`**kwargs` 放行；密钥规则加占位符白名单与新前缀（`glpat-`/`xox*-`/`AIza`/私钥块）。
- **规则注册表**：`Rule` dataclass + `RULES` + `make_finding` 工厂；`--list-rules` 自省。
- **测试补强**：30 → 49 用例；正常 `import hardening_scan`；`run_cli` 加 timeout。
- **K8s 清单修正**：新增 `08-pvc.yaml`（共享 RWX PVC）；emptyDir→PVC；PDB `maxUnavailable: 1`；HPA 封顶 1 副本；UID 统一 10001；Ingress basic-auth fail-closed；gateway `Recreate` 策略。
- **文档**：README（双语合并）、SKILL.md、ACCEPTANCE_REPORT 同步更新。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `hardening-review`: 扫描器行为契约扩展——抑制与配置、规则注册表、误报修正后的检测集、退出码语义细化；部署指引更新为 9 份内部一致的 K8s 清单；验收门槛增加 CI 与打包要求。

## Impact

- 新增：`pyproject.toml`、`.hardening-scan.toml`、`.github/workflows/ci.yml`、`deploy/08-pvc.yaml`、`docs/REFACTOR_PROGRESS.md`。
- 修改：`hermes-skills/hardening-review/scripts/hardening_scan.py`（规则注册表化 + 抑制/配置 + 误报修正）、`tests/skills/test_hardening_review_skill.py`（49 用例）、`deploy/01/03/04/06/07*.yaml`、`README.md`、`SKILL.md`、`docs/ACCEPTANCE_REPORT.md`。
- 不改动：`hermes-agent/` 上游克隆；扫描器仍纯 stdlib（tomllib 要求 Python ≥3.11）。
- fixtures（`tests/skills/fixtures/`）仍是故意脏样本；CI dogfood 步骤用 `--no-config` 绕开仓级豁免以验证扫描器有效。
