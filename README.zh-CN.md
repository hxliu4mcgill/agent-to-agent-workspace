# Agent-to-Agent Space

[English](README.md) | 简体中文

Agent-to-Agent Space 是一个基于文件系统的轻量级协作协议，供彼此独立的 AI
Agent Session 交换需求和状态。它不要求 Session 共享对话，不需要运行服务器，
也不假设所有 Agent 都在同一个 Git 仓库中工作。

本仓库既是一个 Codex Skill，也是该协议的参考实现。

## 为什么需要它

在相关联的仓库中工作的两个 Agent，经常需要协调 API、数据结构、设计决策或
后续任务。聊天记录只存在于各自的 Session 中，而 Git commit 也不适合作为临时
协作信息的传输方式。共享空间提供了一个持久的收件箱，双方都可以直接查看。

## 适用场景：一个人维护多个独立仓库

这个工具特别适合独立开发者或小团队维护多模块产品。一个 workspace 下可能
同时包含前端、后端、数据、基础设施，甚至运营等多个独立 repo；每个 repo 又会
在 Codex、Claude Code、Cursor 等 Agent 工具中作为单独的 Project 打开，并拥有
各自独立的 Session。

这些 Session 熟悉自己所在 repo 的代码和上下文，却无法天然看到其他 Session
中发生的讨论。跨模块协作时，如果只靠开发者在窗口之间口头转述或复制粘贴，
需求背景、验收标准和处理进度很容易丢失。

Agent-to-Agent Space 在这些 repo 的共同父目录中放置一个共享的
`.agent-to-agent/`，把它作为各个 Session 都能访问的“需求信箱”和协作记录。
例如：

1. 前端开发时发现需要后端提供一个新接口。
2. 在前端 Session 中说：“给后端提一个需求：增加文章收藏接口，并说明请求参数和验收标准。”
3. 前端 Agent 将结构化需求写入共享的 `.agent-to-agent/`，收件方标记为 `backend`。
4. 切换到后端 Project 的 Session，只需说：“前端有新需求了，看一下。”
5. 后端 Agent 读取自己的待处理需求，接受、补充问题或实现需求，并把状态和结果写回同一空间。
6. 回到前端 Session 后，前端 Agent 可以继续查看处理结果，而不必重新拼接上下文。

同样的方式也适用于后端向数据模块提出表结构或迁移需求、数据模块要求前后端
补充埋点，以及运营向产品研发提出活动页或内容配置需求。

> Agent-to-Agent Space 不负责自动唤醒另一个 Session。它负责让跨 Session
> 的信息传递变得持久、结构化且可追踪；开发者只需切换到目标 Session，并让它
> 检查自己的收件箱。

## 安装 Skill

将本仓库克隆或复制到 Codex 的 Skill 目录：

```text
~/.codex/skills/agent-to-agent-space/
```

该目录根层级中必须包含 `SKILL.md`、`scripts/`、`references/` 和
`agents/openai.yaml`。

Python 3.10 或更高版本是运行内置 CLI 的首选方式，但并不是协议的硬依赖。
Skill 会检测可用的 Python 3 命令；Python 不可用时，将回退到 Agent 的原生文件
操作。安全 fallback 流程请参阅
[`references/manual-fallback.md`](references/manual-fallback.md)。

## 配置各个项目

推荐的目录结构是在一个父级 workspace 中放置多个相关仓库，以及一个共享的
协作目录：

```text
workspace/
├── .agent-to-agent/          # 共享收件箱和需求历史
├── ios-app/
│   └── .agent-to-agent.json
├── backend/
│   └── .agent-to-agent.json
└── web-app/
    └── .agent-to-agent.json
```

每个 Agent Session 仍然在自己的仓库中工作。仓库内的小型配置文件向上指向同一个
workspace 级共享目录。

在每个参与协作的项目中创建 `.agent-to-agent.json`：

```json
{
  "version": 1,
  "agentId": "ios-app",
  "spaceDirectory": "../.agent-to-agent"
}
```

每个项目使用自己稳定的 `agentId`，所有参与者的 `spaceDirectory` 都应解析到
同一个目录。相对路径以配置文件所在位置为基准，而不是以当前 shell 目录为基准。

`agentId` 通常代表仓库或职责，例如 `ios-app`、`backend` 或 `web-app`。同一仓库
中的多个 Session 可以共享相同的身份和收件箱。只有当这些 Session 需要被分别
指定为负责人时，才使用不同的 ID。

共享目录只需初始化一次：

```bash
python scripts/agent_space.py init --start /path/to/project
```

然后便可以查看或交换需求：

```bash
python scripts/agent_space.py resolve --start /path/to/project
python scripts/agent_space.py list --start /path/to/project
python scripts/agent_space.py create --start /path/to/project \
  --to backend --title "Add article enrichment" \
  --body "Enrich public article URLs during capture preview." \
  --acceptance "A public article produces a useful title and summary."
python scripts/agent_space.py respond --start /path/to/backend \
  --id req-... --status accepted --message "Starting implementation."
```

完整的文件格式和生命周期规则请参阅
[references/protocol.md](references/protocol.md)。

包含三个仓库的完整目录示例位于
[`examples/workspace`](examples/workspace)。

## 特性

- 使用通用的 Agent 身份，不限定为 App 或后端等特定角色。
- 不依赖守护进程、数据库、账户或网络。
- 首选 Python CLI，同时提供有明确规范的文件系统 fallback。
- 使用低冲突概率的需求 ID。
- 原子发布，并对更新操作加锁。
- 使用带 YAML 兼容 frontmatter 的人类可读 Markdown。
- 不会自动创建 Git commit 或执行 push。

## 开发

运行仅依赖 Python 标准库的测试套件：

```bash
python -m unittest discover -s tests -v
```

发布前，使用 Codex 的 `quick_validate.py` 验证 Skill 结构。

## 许可证

目前尚未选择许可证。在公开发布仓库之前，请添加明确的开源许可证。
