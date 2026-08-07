## Why

交接待办中的四项收尾：扫描器检测能力的两处增强（实例级 timeout 追踪、密钥熵第二信号），加上技能元数据与安装体验的修正（SKILL.md 版本与悬空 `related_skills`、`cp -R` 手工安装）。

## What Changes

- **实例级 timeout 追踪**：`_collect_client_instances` 赋值级数据流——构造器带 `timeout=` 的实例方法调用放行；无默认 timeout 的实例（含 `requests.Session`，其无法携带默认 timeout）方法调用标记，消息区分构造器/实例两种发现；未知值重赋值回落保守不标记。
- **密钥熵检测**：新规则 `HIGH_ENTROPY_STRING`（P1/D3，`needs_confirmation`/`[manual]` 通道）——Shannon 熵 ≥4.5、≥20 字符、大小写+数字混合、占位符豁免；已被前缀/赋值规则标记的行不重复报。
- **SKILL.md 元数据**：`version` 0.1.0 → 0.2.0；移除悬空的 `related_skills: [ponytail-review]`（全仓确认无此技能）。
- **安装脚本**：新增 `hermes-skills/hardening-review/install.sh`（POSIX sh，`--dest`/`--check`，原子替换，剔除 `__pycache__`，reload 提示）；README 安装节改用该脚本。
- **测试**：49 → 57 用例（实例追踪 4 例 + 熵检测 4 例）；新增 fixture `high_entropy.txt`；覆盖率 94% → 95%。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `hardening-review`: 扫描助手契约扩展——实例级 timeout 数据流语义与熵第二信号（含去重与豁免规则）；规则注册表新增 `HIGH_ENTROPY_STRING`。

## Impact

- 修改：`hermes-skills/hardening-review/scripts/hardening_scan.py`（+实例追踪、+熵检测、`_call_has_timeout` 抽取）、`SKILL.md`（版本/描述）、`tests/skills/test_hardening_review_skill.py`（57 用例）、`README.md`（安装节/徽章/验收表）。
- 新增：`hermes-skills/hardening-review/install.sh`、`tests/skills/fixtures/high_entropy.txt`。
- 不改动：纯 stdlib 承诺不变（新增仅用 `math`/`collections.Counter`）；检测阈值保守（hex digest、英文散文、占位符均实测不误报）。
