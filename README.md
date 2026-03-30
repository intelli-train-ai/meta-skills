# Meta Skills

> Skills about skills — 用于管理、发现、创建和分析 Claude Code Skills 的元技能集合。

## 概述

Meta Skills 是一套围绕 Claude Code Skill 生态系统构建的工具集，帮助用户更高效地使用和管理 skills。它分为四大模块：

| 模块 | 说明 | 核心能力 |
|------|------|---------|
| **Search** | 搜索 Skill | 从本地和远程 skill 库中快速定位所需 skill |
| **Recommend** | 推荐 Skill | 根据用户上下文和意图智能推荐最合适的 skill |
| **Create & Improve** | 创建/改进 Skill | 从零构建新 skill，或对现有 skill 进行迭代优化 |
| **Analyze** | 分析 Skill | 评估 skill 质量、性能、使用情况和改进空间 |

## Skill 清单

详见 [SKILL_LIST.md](SKILL_LIST.md) 获取完整清单。

### Search — 搜索 Skill

| Skill | 链接 | 说明 |
|-------|------|------|
| skill-skillsh-finder | [GitHub](https://github.com/OrionZou/skill-skillsh-finder) | 基于 Shell 脚本的 skill 搜索工具 |
| skill-find-skills-clawhub | [GitHub](https://github.com/OrionZou/skill-find-skills-clawhub) | 从 ClawHub 平台查找 skill |

### Recommend — 推荐 Skill

| Skill | 链接 | 说明 |
|-------|------|------|
| skill-recommender | [GitHub](https://github.com/OrionZou/skill-recommender) | 根据用户上下文智能推荐 skill |

### Create & Improve — 创建/改进 Skill

| Skill | 链接 | 说明 |
|-------|------|------|
| skill-master | [GitHub](https://github.com/OrionZou/skill-master) | Skill 创建与改进工具 |

### Analyze — 分析 Skill

| Skill | 链接 | 说明 |
|-------|------|------|
| plan-visualizer | [GitHub](https://github.com/OrionZou/skill-plan-visualizer) | 将计划、任务列表和工作流可视化为交互式 HTML 页面 |
| session-distiller | [GitHub](https://github.com/OrionZou/skill-session-distiller) | 分析对话内容，自动提取可复用的技能模式 |
| skill-analyzer | [GitHub](https://github.com/OrionZou/skill-analyzer) | 递归分析 skill 的完整依赖关系并生成交互式可视化图表 |

## 安装

本仓库是一个 Claude Code Plugin，包含全部 7 个 meta-skill。

### 从 Marketplace 安装

```
/plugin install meta-skills
```

### 手动安装

```bash
git clone --recurse-submodules https://github.com/intelli-train-ai/meta-skills.git
```

然后通过 `--plugin-dir` 加载：

```bash
claude --plugin-dir ./meta-skills
```

### 安装后可用的 Skill 命令

| 命令 | 说明 |
|------|------|
| `/meta-skills:skill-skillsh-finder` | 从 skills.sh 搜索 skill |
| `/meta-skills:skill-find-skills-clawhub` | 从 ClawHub 平台查找 skill |
| `/meta-skills:skill-recommender` | 根据上下文智能推荐 skill |
| `/meta-skills:skill-master` | 创建与改进 skill |
| `/meta-skills:skill-plan-visualizer` | 可视化计划和工作流 |
| `/meta-skills:skill-session-distiller` | 从对话中提取可复用技能模式 |
| `/meta-skills:skill-analyzer` | 分析 skill 依赖关系 |

## 相关资源

| 资源 | 链接 | 说明 |
|------|------|------|
| skill-template | [GitHub](https://github.com/OrionZou/skill-template) | Skill 模板，帮助用户快速编写新 skill |

## 用户故事

### 找到合适的 Skill

> "我想生成一个 API 文档，但不知道有没有现成的 skill 能用。"

用户通过 **skill-skillsh-finder** 或 **skill-find-skills-clawhub** 搜索关键词，快速找到匹配的 skill 并安装使用。

### 获得智能推荐

> "我正在写一个 React 项目，有哪些 skill 能帮到我？"

**skill-recommender** 根据当前项目上下文（语言、框架、正在进行的任务）主动推荐最相关的 skill，无需用户手动搜索。

### 从零创建 Skill

> "我有一个重复性工作流，想把它封装成 skill 分享给团队。"

**skill-master** 引导用户从模板开始，逐步构建、测试并发布新 skill。

### 分析和改进现有 Skill

> "我的 skill 依赖关系越来越复杂，想理清楚结构。"

**skill-analyzer** 递归分析依赖关系并生成可视化图表；**session-distiller** 从历史对话中提取可复用的模式，帮助持续迭代。

### 可视化工作计划

> "我想把当前的任务拆解和执行计划分享给同事看。"

**plan-visualizer** 将计划和工作流导出为交互式 HTML 页面，方便团队协作和评审。

## 设计原则

- **组合优于单体**：每个 meta skill 专注做好一件事，通过组合实现复杂工作流
- **上下文感知**：尽可能利用当前工作上下文来提供更精准的结果
- **渐进式使用**：从简单搜索开始，按需深入到创建和分析
- **自举能力**：meta skills 本身也是 skills，可以用 meta skills 来改进 meta skills
