## 1. 实例级 timeout 追踪

- [x] 1.1 复测交接描述场景（4 种写法），确认原误报不存在、实际缺口为实例方法漏报
- [x] 1.2 实现 `_collect_client_instances` / `_is_http_constructor` / `_call_has_timeout` / `_instance_call_verdict`
- [x] 1.3 `INSTANCE_TRACKED_CONSTRUCTORS` 纳入 `Session`；实例发现消息与构造器发现区分
- [x] 1.4 测试：有 timeout 放行 / 无 timeout 标记（构造器+方法两行）/ `requests.Session` 标记 / 未知重赋值回落（4 例）

## 2. 密钥熵检测

- [x] 2.1 注册 `HIGH_ENTROPY_STRING` 规则（P1/D3，`needs_confirmation`）
- [x] 2.2 实现 `_shannon_entropy` / `_has_mixed_character_classes` / `_has_high_entropy_token`（≥20 字符、熵 ≥4.5、占位符豁免、密钥行去重）
- [x] 2.3 实测不误报：40 位 hex（3.97）、低熵长串、英文散文、`REPLACE_WITH_*` 行
- [x] 2.4 fixture `high_entropy.txt` + 测试：正向标记 / hex 豁免 / 低熵豁免 / 同行不重复（4 例）

## 3. 技能元数据与安装

- [x] 3.1 SKILL.md `version: 0.2.0`；移除悬空 `related_skills: [ponytail-review]`；Phase 1 描述同步新检测能力
- [x] 3.2 新增 `install.sh`（`--dest`/`--check`，原子替换，reload 提示）并实测安装与校验

## 4. 基线与收尾

- [x] 4.1 全量基线：ruff clean、57 passed、覆盖率 95%、`hardening-scan .` 退出码 0、fixtures `--no-config` 退出码 1
- [x] 4.2 README（徽章 57/95%、扫描器能力、install.sh 安装节、目录结构）与 REFACTOR_PROGRESS 同步
- [x] 4.3 主规格同步（实例追踪与熵信号场景）并归档本 change
- [x] 4.4 提交推送远端，CI 全绿
