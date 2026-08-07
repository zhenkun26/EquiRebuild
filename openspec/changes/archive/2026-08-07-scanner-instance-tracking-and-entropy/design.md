## Context

上一轮（`2026-08-07-refactor-scanner-and-k8s`）交接清单剩余四项：③密钥熵检测、④实例级 timeout 追踪、⑤SKILL.md 版本与悬空 related_skills、⑥install.sh。其中④的原始描述（"`client.get(url)` 仍会标记"）在本轮复测中**未复现**——import 感知改造后该误报已不存在，实际缺口是反向漏报：无 timeout 构造的实例（尤其 `requests.Session`）其方法调用完全不被检查。

## Goals / Non-Goals

**Goals:**
- 赋值级实例追踪，双向修正：有 timeout 的实例放行（防未来回归），无 timeout 的实例方法调用标记（补漏报）。
- 熵检测作为第二信号上线，严格限制在 `needs_confirmation`/`[manual]` 通道，实测不误报 hex digest / 英文散文 / 占位符。
- SKILL.md 元数据正确化；安装一键化。

**Non-Goals:**
- 不做跨函数/跨文件数据流（保持单文件 AST walk，"简单赋值-属性"范围）。
- 熵检测不升级为 P0 或默认判定通道——误报率需要真实使用数据后再评估。
- 不为 `requests.Session()` 构造器本身加发现（Session 无 timeout 参数，标记构造器无可操作修复）。

## Decisions

- **重赋值保守回落**：名字被重赋值为未知值时从追踪表删除而非保持旧状态——宁可漏报不可误报，与扫描器整体启发式定位一致。
- **`requests.Session` 纳入追踪集但不纳入构造器标记集**：`INSTANCE_TRACKED_CONSTRUCTORS = HTTP_CLIENT_CONSTRUCTORS | {"Session"}`；Session 无法设默认 timeout，正确信号是标记其无 timeout 的方法调用。
- **熵阈值 4.5 + 三类字符混合**：纯 hex 上限 4.0 天然豁免（git SHA、md5 不报）；英文散文约 4.0–4.3 且含空格被 token 正则切断；要求 lower+upper+digit 进一步压掉 base64 之外的结构化字符串。
- **熵发现与密钥发现同行去重**：前缀/赋值规则已标记的行跳过熵检查，避免同一行两个 D3 发现噪声。
- **测试样本仍走 fixture 文件**：高熵 token 不内联进测试源码（dogfooding 教训），新增 `tests/skills/fixtures/high_entropy.txt`，由仓级 `.hardening-scan.toml` 豁免。
