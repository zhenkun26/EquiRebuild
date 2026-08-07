# 重构进度交接（REFACTOR PROGRESS）

> 最后更新：2026-08-07。新对话中继续时，先读本文件，再跑一遍"当前基线验证"确认状态。

## 背景

本轮重构源于对仓库的审查报告（问题清单：无依赖清单/CI、扫描器无抑制机制、K8s 清单自相矛盾、规则误报等）。工作区路径：`/Users/yuzheng/My_Learning_For_AI/EquiRebuild/hermes-agent-hardening`。<!-- # hardening-scan: ignore=ABSOLUTE_PATH -->

## 已完成（①–⑨，全部本地验证通过）

| # | 事项 | 关键产物 |
|:--|:-----|:---------|
| ① | pyproject 打包 + 可复现测试环境 | `pyproject.toml`（entry point `hardening-scan`，dev extras），`.venv` |
| ② | GitHub Actions CI | `.github/workflows/ci.yml`（ruff/pytest/覆盖率/dogfood/kubeval，Python 3.11–3.13 矩阵） |
| ③ | 扫描器抑制机制 | 行内 `# hardening-scan: ignore=RULE_ID`；`.hardening-scan.toml`（`exclude`/`disable-rules`）；`--config`/`--no-config` |
| ④ | 退出码语义 + 去重 | BrokenPipe 保留判定码不再报用法错误；`_read_utf8` 去重 NON_UTF8；跳过 `.ruff_cache` 等缓存目录 |
| ⑤ | 误报修正 | HTTP 检查改为 import 感知（`HttpBindings`），`**kwargs` 放行；密钥规则加占位符白名单（`<YOUR_…>`/`REPLACE_WITH_*`/`${VAR}`）与新前缀（glpat-/xox*-/AIza/私钥块） |
| ⑥ | 规则注册表 | `Rule` dataclass + `RULES` 注册表 + `make_finding` 工厂；`KNOWN_RULES` 派生；`--list-rules` |
| ⑦ | 测试补强 | 30 → 49 用例；`run_cli` 加 `timeout=30`；测试改为正常 `import hardening_scan` |
| ⑧ | K8s 清单修正 | 新增 `08-pvc.yaml`（共享 RWX PVC）；emptyDir→PVC；PDB `maxUnavailable: 1`；HPA 封顶 1 副本；UID 统一 10001；secretRef 去 `optional`；Ingress 加 basic-auth（fail-closed）；gateway `strategy: Recreate` |
| ⑨ | 文档修正 | README/SKILL.md/ACCEPTANCE_REPORT 更新；样本文本改占位符 |

## 当前基线验证（新对话先跑这个）

```bash
cd /Users/yuzheng/My_Learning_For_AI/EquiRebuild/hermes-agent-hardening
uv venv .venv 2>/dev/null; uv pip install --python .venv/bin/python -e '.[dev]'  # 若 .venv 丢失
.venv/bin/python -m ruff check hermes-skills tests   # 应 All checks passed
.venv/bin/python -m pytest tests/ -q                 # 应 49 passed
.venv/bin/python -m coverage run -m pytest tests/ -q && .venv/bin/python -m coverage report  # 应 ≥80%（现 94%）
.venv/bin/hardening-scan .                           # 应 clean，退出码 0
```

## 待办（下一轮候选，按优先级）

1. ~~提交与推送~~ ✅ 2026-08-07 完成：合并远端双语 README（冲突已手工融合），修复 CI dogfood 步骤（`--no-config` 绕开仓级豁免），main 已推送，CI 四任务全绿（test 3.11/3.12/3.13 + k8s）。
2. ~~OpenSpec 同步~~ ✅ 2026-08-07 完成：主规格已更新，change 归档于 `openspec/changes/archive/2026-08-07-refactor-scanner-and-k8s/`（本机无 openspec CLI，未跑 `openspec validate`，格式对照既有归档手工核对）。
3. **密钥熵检测**：香农熵作为第二信号（注意控制误报，先只在 `needs_confirmation` 通道启用）。
4. **实例级 timeout 追踪**：`client = httpx.Client(timeout=30)` 后 `client.get(url)` 目前仍会标记；需做简单的赋值-属性数据流。
5. **SKILL.md 版本**：`version: 0.1.0` 可考虑升 0.2.0（抑制机制+注册表是行为变更）；`related_skills: [ponytail-review]` 指向不存在的技能，需确认。
6. **安装脚本**：目前技能安装仍是 `cp -R`，可加 `install.sh`（含 `~/.hermes/skills/` 目标与 reload 提示）。
7. **真机验证**：Docker 镜像构建受 Docker Desktop 代理 502 限制（见验收报告 §3.4），K8s 清单尚为静态校验，未上集群。

## 注意事项

- fixtures（`tests/skills/fixtures/`）是故意脏样本，永远会产生发现；改测试样本时不要把形似密钥的字符串内联进测试源码（dogfooding 教训，见验收报告 §2.1）。
- `.hardening-scan.toml` 的 `exclude` 与 CLI `--exclude` 是叠加关系，不是覆盖。
- 扫描器必须保持纯 stdlib（SKILL.md 前置条件承诺）；tomllib 要求 Python ≥3.11。
