# Hermes Agent Hardening

对 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的二次开发工作区。首个交付是一个可复用的 Hermes 用户技能 **`hardening-review`**：把"对抗性生产级审查"（5 维度扫描、P0/P1 分级、修复、验证、部署、验收报告）固化为标准流程，并用它完成了本仓库自身的加固闭环（dogfooding）。

规划由 [OpenSpec](https://openspec.dev) 驱动，全程不修改上游克隆——所有开发都落在本工作区，技能通过 Hermes 标准用户技能目录（`~/.hermes/skills/`）安装。

## 目录结构

```
├── hermes-skills/hardening-review/   # 核心交付：Hermes 用户技能
│   ├── SKILL.md                      # 5 维对抗审查程序（HARDLINE 合规）
│   ├── scripts/hardening_scan.py     # 机械扫描器（纯 stdlib，退出码 0/1/2）
│   └── templates/report_template.md  # 验收报告骨架（<YOUR_...> 占位符规范）
├── tests/skills/                     # pytest 测试 + fixtures（无网络）
├── deploy/                           # Kubernetes 清单（8 份，全部占位符）
├── docs/ACCEPTANCE_REPORT.md         # 本次交付的综合验收报告
├── openspec/                         # OpenSpec 规格仓库
│   ├── specs/hardening-review/       # 主规格（已同步）
│   └── changes/archive/              # 已归档变更
└── hermes-agent/                     # 上游只读克隆（参考，永不修改）
```

## hardening-review 技能

对目标代码库执行"即将部署到生产环境"级别的最终审查，输出按严重度分级的发现、修复 diff、测试与部署建议。**核心标准**：穷尽手段寻找必现崩溃、数据丢失、安全入侵与性能雪崩隐患。

### 五个审查维度

| 维度 | 关注点 |
|:---|:---|
| D1 逻辑黑洞与竞态 | Check-Then-Act 竞态、缺少 Saga 补偿、`except Exception: pass` 吞异常 |
| D2 隐性性能杀手 | N+1 查询、阻塞事件循环、HTTP 客户端无超时/重试 |
| D3 致命安全漏洞 | 注入、硬编码密钥（JWT Secret / AK/SK）、水平/垂直越权 |
| D4 配置与环境幻觉 | 本地绝对路径、未校验的环境变量静默失败 |
| D5 日志与可观测性 | 敏感日志、关键链路缺少 TraceId 透传 |

发现一律标注 `[严重][P0]` 或 `[中危][P1]`，并附具体文件位置与可复现的攻击/故障案例；某维度无发现时明确写"clean"，不允许省略。

### 机械扫描器

```bash
python3 hermes-skills/hardening-review/scripts/hardening_scan.py <target> \
  [--output report.md] [--exclude GLOB ...]
```

自动检测：裸 `except:` / `except X: pass`、HTTP 客户端无显式 `timeout`、硬编码密钥（`sk-`/`AKIA`/`ghp_` 前缀与常见键名赋值）、绝对路径、非 UTF-8 文件。

退出码：`0` 无发现 / `1` 有发现 / `2` 用法或目标错误。缺失目标必报错，绝不静默通过。行级正则发现标记 `[manual]`，需人工确认。

### 安装（Hermes 用户技能）

```bash
cp -R hermes-skills/hardening-review ~/.hermes/skills/security/hardening-review
hermes skills reload   # 或重启会话
```

然后在对话中按技能说明使用；或直接调用：

```text
用 hardening-review 技能审查 <目标目录>，输出 P0/P1 发现与修复 diff
```

## 验收结果

- **单元测试**：30 个用例全绿（stdlib + pytest + `unittest.mock`，无网络调用）
- **覆盖率**：`hardening_scan.py` 行覆盖率 **99%**（要求 ≥80%）
- **并发冒烟**：1000 次并发调用全部退出码符合预期（5.8s，无共享状态）
- **上游零污染**：`git -C hermes-agent status --porcelain` 恒为空
- **自审闭环**：技能审查自身代码，修复 3 个 [P1]（密钥样本文本入库、输出写入崩溃、BrokenPipe 未处理），复扫全 clean

详见 [docs/ACCEPTANCE_REPORT.md](docs/ACCEPTANCE_REPORT.md)。

## 部署

### Docker Compose（验证上游配置）

```bash
docker compose -f hermes-agent/docker-compose.yml config --quiet
HERMES_UID=$(id -u) HERMES_GID=$(id -g) docker compose -f hermes-agent/docker-compose.yml up -d
```

注意：dashboard 默认只绑定 `127.0.0.1`（存储 API 密钥），远程访问请走 SSH 隧道或反代认证。

### Kubernetes（本仓库清单）

```bash
kubectl apply -f deploy/            # namespace/configmap/secret/deployment/pdb/service/ingress/hpa
kubectl -n hermes get pods
```

使用前必须替换：

- `deploy/03-deployment.yaml` 中的 `<YOUR_REGISTRY>` 镜像地址
- `deploy/02-secret.yaml` 中的占位 base64（`printf '<YOUR_VALUE>' | base64` 重新生成）
- `deploy/06-ingress.yaml` 中的 `<YOUR_DOMAIN>`

### 真机验证状态

Docker daemon 与 Compose 配置已实测通过；完整镜像构建受本机 Docker Desktop 内部代理对大文件下载 502 的限制暂未完成（宿主机直连正常，SQLite 包 SHA256 与上游锁定值一致）。解决路径与命令见验收报告 §3.4。

## 开发流程（OpenSpec）

```text
$openspec-explore <想法>                          # 探索
$openspec-propose <change-name>                   # 立项（proposal/specs/design/tasks）
$openspec-apply-change                            # 实施
$openspec-sync-specs <change-name> && git commit specs
$openspec-archive-change <change-name>            # 归档
```

项目上下文与约定（不修改上游、技能装 `~/.hermes/skills/`、交付模式）记录在 [openspec/config.yaml](openspec/config.yaml)。

## 许可

MIT。上游 Hermes Agent 版权归 Nous Research 所有，本仓库仅作学习与二次开发参考。
