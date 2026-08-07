## Context

上一轮交付（`2026-08-06-add-hardening-review-skill`）跑通了"审查→修复→测试→容器化→验收"闭环，但事后审查暴露工程化短板：无 `pyproject.toml`/CI，扫描器没有抑制机制导致 fixtures 脏样本使全仓 dogfood 扫描永远非零，K8s 清单在状态共享与副本数上自相矛盾，HTTP 与密钥规则存在已知误报。本变更不改审查方法论（5 维、P0/P1），只重构机械层与部署层。

## Goals / Non-Goals

**Goals:**
- 可复现开发环境（uv/pip `-e '.[dev]'`）+ GitHub Actions CI（3.11–3.13 矩阵，覆盖率 `fail_under = 80`）。
- 扫描器支持行内抑制与仓级 TOML 配置，使全仓自扫可以合法地达到 clean（退出码 0）。
- 消除已知误报：同名 SDK 构造器、`**kwargs` 透传、占位符密钥。
- K8s 清单内部一致：共享 PVC、单副本 gateway、fail-closed Ingress。

**Non-Goals:**
- 不引入第三方运行时依赖（扫描器保持纯 stdlib；tomllib 限 Python ≥3.11）。
- 不做密钥香农熵检测、实例级 timeout 数据流追踪（列入后续候选）。
- 不上真实集群验证；K8s 仍为静态校验。

## Decisions

- **抑制语法用行内注释而非配置文件逐行豁免**：`# hardening-scan: ignore=RULE_ID` 与发现同行，审查时可见、随代码移动；markdown 等非代码文件可用 HTML 注释包裹。
- **配置自动发现 + 显式开关**：`.hardening-scan.toml` 从目标目录或 CWD 发现；`--no-config` 供 dogfood 等场景绕开豁免；配置 exclude 与 CLI `--exclude` 叠加而非覆盖，避免隐式丢失调用方意图。
- **误报修正走 import 感知而非名称黑名单**：`HttpBindings` 只标记从已知 HTTP 库 import 的构造器调用；比维护"同名白名单"更稳。
- **规则注册表单一事实来源**：`Rule` dataclass + `RULES`，`KNOWN_RULES` 派生，`--list-rules` 自省，抑制规则名拼写错误可被发现。
- **K8s 状态共享用 RWX PVC 而非 emptyDir**：emptyDir 是 per-pod 的，会静默切断 gateway 与 dashboard 的 `~/.hermes` 状态共享；单副本 + `Recreate` + HPA 封顶 1 是会话状态 pod 本地化期间的有意约束。
- **Ingress basic-auth fail-closed**：未创建 auth secret 时 nginx 返回 503 而非放行仪表盘（仪表盘存储 API 密钥）。
