## 1. 打包与 CI

- [x] 1.1 新增 `pyproject.toml`（`hardening-scan` 入口、dev extras、coverage `fail_under = 80`），uv 可复现安装
- [x] 1.2 新增 `.github/workflows/ci.yml`（ruff/pytest/覆盖率/dogfood/kubeval，Python 3.11–3.13 矩阵）
- [x] 1.3 CI 首次运行修复：dogfood 步骤加 `--no-config` 绕开仓级豁免（fixtures 必须产生发现）

## 2. 扫描器抑制与配置

- [x] 2.1 行内抑制 `# hardening-scan: ignore[=RULE_IDS]`（`SUPPRESSION_RE` + `is_suppressed`）
- [x] 2.2 仓级 `.hardening-scan.toml`（`exclude`/`disable-rules`，目标目录或 CWD 自动发现）
- [x] 2.3 `--config PATH` / `--no-config`；配置 exclude 与 CLI `--exclude` 叠加
- [x] 2.4 跳过 `.ruff_cache` 等缓存目录；NON_UTF8 按文件去重；BrokenPipe 保留判定码

## 3. 误报修正与规则注册表

- [x] 3.1 HTTP 检查 import 感知（`HttpBindings`），`**kwargs` 放行
- [x] 3.2 密钥规则占位符白名单（`<YOUR_…>`/`REPLACE_WITH_*`/`${VAR}`）与新前缀（`glpat-`/`xox*-`/`AIza`/私钥块）
- [x] 3.3 `Rule` dataclass + `RULES` 注册表 + `make_finding` 工厂；`KNOWN_RULES` 派生；`--list-rules`

## 4. 测试

- [x] 4.1 用例 30 → 49（抑制、配置、注册表、误报修正、退出码语义）
- [x] 4.2 测试改正常 `import hardening_scan`；`run_cli` 加 `timeout=30`
- [x] 4.3 本地基线：ruff clean、49 passed、覆盖率 94%、`hardening-scan .` 退出码 0

## 5. K8s 清单修正

- [x] 5.1 新增 `08-pvc.yaml`（共享 RWX PVC）；deployment emptyDir→PVC
- [x] 5.2 PDB `maxUnavailable: 1`；HPA `maxReplicas` 封顶 1；UID 统一 10001；secretRef 去 `optional`
- [x] 5.3 Ingress basic-auth fail-closed；gateway `strategy: Recreate`

## 6. 文档与规格

- [x] 6.1 README 双语合并（远端双语骨架 + 本轮重构事实：49 测试/94%/CI badge/9 清单/PVC 约束）
- [x] 6.2 SKILL.md / ACCEPTANCE_REPORT 同步；样本文本改占位符
- [x] 6.3 主规格同步（`openspec/specs/hardening-review/spec.md`）并归档本 change
- [x] 6.4 提交推送远端，CI 全绿（test 3.11/3.12/3.13 + k8s）
