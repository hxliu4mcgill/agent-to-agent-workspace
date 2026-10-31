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

## 用户指南：连接多个项目

下面以一个包含 iOS App、后端和 Web 前端的 workspace 为例，从零完成接入。
请将示例中的名称和路径替换为自己的仓库。

### Setup

Setup 是用户需要执行的唯一准备工作。配置创建、共享收件箱初始化以及结果验证
都由 Agent 自动完成。

#### 1. 把相关仓库放在同一个 workspace 下

让参与协作的仓库拥有同一个父目录。它们仍然是彼此独立的 Git 仓库，也仍然可以
在 Codex 或其他 Agent 工具中作为单独的 Project 打开。

```text
workspace/
├── ios-app/
├── backend/
└── web-app/
```

所有参与协作的 Session 都必须能够读写这个父目录。共享的
`.agent-to-agent/` 将在后续步骤中创建。

#### 2. 让 Agent 设置第一个项目

在 Agent 工具中将 `ios-app` 作为 Project 打开，然后在 Session 中输入：

```text
$agent-to-agent-space setup
```

也可以直接使用自然语言：

> 为当前项目设置 Agent-to-Agent Space。

Agent 会找到 Git 仓库根目录，默认使用 `ios-app` 作为身份，创建
`.agent-to-agent.json`，并在 workspace 父目录初始化共享收件箱。完成后，它应
报告项目路径、身份、配置文件和共享空间的实际路径。

如果仓库名称不是你想要的身份，可以明确指定：

> 为当前项目设置 Agent-to-Agent Space，身份使用 `mobile`。

#### 3. 在其他项目中重复 setup

把 `backend` 作为另一个独立 Project 打开，并输入同样的请求：

```text
$agent-to-agent-space setup
```

在 `web-app` 和其他参与协作的仓库中重复执行。第一个项目会创建共享目录，后续
项目会复用它。每个项目拥有自己的身份和配置，但都指向同一个收件箱：

```text
workspace/
├── .agent-to-agent/
│   └── requirements/
├── ios-app/
│   └── .agent-to-agent.json
├── backend/
│   └── .agent-to-agent.json
└── web-app/
    └── .agent-to-agent.json
```

每次 setup 都会重新读取保存后的配置，并自动验证共享目录。Agent 会报告成功，
或者直接说明错误；用户不需要再执行独立的验证步骤。`resolve` 只用于故障排查。

如果 Skill 是在 Session 启动后安装的，请刷新或重新打开 Session，让工具发现
新的 Skill。

### 发送第一条需求

在 iOS Session 中直接用自然语言说：

> 给后端提一个需求：增加文章收藏接口，并说明请求参数和验收标准。

Agent 应创建一条从 `ios-app` 发给 `backend` 的结构化需求。等价的 CLI 命令是：

```bash
python /path/to/agent-to-agent-space/scripts/agent_space.py create \
  --start /path/to/workspace/ios-app \
  --to backend \
  --title "增加文章收藏接口" \
  --body "提供一个需要登录的文章收藏接口。" \
  --acceptance "有效请求能够返回保存后的收藏记录。"
```

命令会返回一个类似 `req-...` 的需求 ID。此时需求已经持久保存，但不会自动唤醒
后端 Session。

### 接收并回复需求

切换到后端 Session，说：

> 前端有新需求了，看一下。

Agent 应检查后端收件箱，说明需求内容，并根据情况接受、阻塞、拒绝或完成它。
等价的 CLI 操作是：

```bash
python /path/to/agent-to-agent-space/scripts/agent_space.py list \
  --start /path/to/workspace/backend
python /path/to/agent-to-agent-space/scripts/agent_space.py respond \
  --start /path/to/workspace/backend \
  --id req-... \
  --status accepted \
  --message "已接受，将按照需求中约定的接口契约开始实现。"
```

### 回到来源 Session 检查结果

切回 iOS Session，说：

> 看一下后端有没有回复刚才的需求。

iOS Agent 此时可以直接读取更新后的状态和完整回复历史，不需要你在 Session 之间
复制上下文。之后，前端、后端、数据、基础设施和运营等仓库都可以重复使用同一
流程协作。

当所有项目都能解析到同一个共享目录，并且接收方 Session 能发现和回复第一条
需求时，接入就完成了。

完整的文件格式和生命周期规则请参阅
[references/protocol.md](references/protocol.md)。包含三个仓库的完整目录示例位于
[`examples/workspace`](examples/workspace)。

## 手动设置与故障排查

正常情况下，Agent 会代替你完成下面的操作。只有在自动化或排查问题时，才需要
直接使用这些命令。

与自动 setup 等价的单步 CLI 命令是：

```bash
python /path/to/agent-to-agent-space/scripts/agent_space.py setup \
  --start /path/to/workspace/ios-app
```

它会根据仓库目录名推导 `agentId`，并把 `../.agent-to-agent` 作为共享路径。
需要时可以覆盖这两个值：

```bash
python /path/to/agent-to-agent-space/scripts/agent_space.py setup \
  --start /path/to/workspace/ios-app \
  --agent-id mobile \
  --space ../shared-agent-space
```

如果不使用 setup 命令，项目根目录中等价的手动配置是：

```json
{
  "version": 1,
  "agentId": "ios-app",
  "spaceDirectory": "../.agent-to-agent"
}
```

之后只需执行一次 `init`，并从每个项目执行 `resolve`。相对共享路径以配置文件
所在目录为基准，而不是以当前 shell 目录为基准。如果 Python 不可用，请使用
[`references/manual-fallback.md`](references/manual-fallback.md) 中的流程。

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
