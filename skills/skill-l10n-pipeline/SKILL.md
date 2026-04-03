---
name: skill-l10n-pipeline
description: "Skill 本地化全自动流水线。当用户需要批量发现、翻译、评测和发布 Claude Code Skills 时使用此技能。触发条件包括：提及'本地化流水线'、'批量翻译 skill'、'skill 翻译评测'、'find and translate skills'，或任何涉及将英文 skill 翻译为中文并评测质量的需求。"
---

# Skill 本地化全自动流水线

一个端到端的编排器，用于批量发现英文 skill、翻译为中文、三层评测质量、自动迭代修复、最终打包发布。

整体流程分为 7 个阶段（Phase）。你的工作是判断用户处于哪个阶段，然后推进流水线。如果用户已经有了翻译好的 skill，可以直接跳到评测阶段；如果用户只是想上传已有的中文 skill，直接进入 Phase 7。

支持 `--fast` 快速模式：只用 1 个测试 prompt 做快速验证，跳过完整评测，适合开发调试阶段。

---

## Phase 1: 发现

目标：确定要处理的 skill 列表。

有两种输入方式：
1. **用户直接给出 skill 路径** — 跳过搜索，直接进入 Phase 2
2. **用户给出搜索关键词** — 调用以下搜索工具：
   - `skill-skillsh-finder`：在 skills.sh 平台搜索
   - `skill-find-skills-clawhub`：在 ClawHub 平台搜索

搜索完成后，输出候选 skill 列表，格式如下：

```
序号 | skill 名称 | 来源 | 简要描述
```

**用户确认点**：列出候选列表后，等待用户确认要处理哪些 skill，再继续。

---

## Phase 2: 语言检测与分流

对每个候选 skill 运行语言检测：

```bash
python scripts/detect_language.py <skill-path>/SKILL.md
```

根据检测结果分流：
- **is_chinese=true**（中文 skill）→ 跳过翻译和评测，直接进入 Phase 7 上传
- **is_chinese=false**（非中文 skill）→ 进入 Phase 3 翻译流程

将分流结果汇总展示给用户：

```
需翻译：skill-a, skill-b, skill-c
直接上传：skill-d（已是中文）
```

---

## Phase 3: 翻译

对每个需要翻译的 skill，调用 `skill-translator` 执行翻译。

翻译配置：
- 源语言：英文（或其他非中文语言）
- 目标语言：中文
- 输出目录：`<skill-name>-zh/`

翻译完成后执行文件完整性验证：
1. 检查 `SKILL.md` 是否存在且非空
2. 检查原版中的子目录和引用文件是否都有对应翻译
3. 检查 frontmatter 格式是否完整（name、description 字段）

**用户确认点**：翻译完成后展示翻译结果摘要，等待用户确认后再进入评测。

---

## Phase 4: 测试设计

读取 `agents/test_writer.md` 中的指导，为每个翻译后的 skill 生成测试用例。

测试设计要求：
- 生成 **3-5 个中文测试 prompt**（`--fast` 模式下只生成 1 个）
- 每个 prompt 附带原子需求分解（可验证的具体断言）
- 自动加入语言质量断言：
  - 输出语言是否为中文
  - 是否存在未翻译的英文残留
  - 术语一致性检查

输出文件：`evals/evals.json`

---

## Phase 5: 三层评测

读取 `agents/evaluator.md` 中的指导，执行完整的三层评测流程。

### 阶段一：双路执行

两个独立 agent 分别执行测试：
- **Agent A**：使用原版英文 skill 执行所有测试 prompt
- **Agent B**：使用翻译后中文 skill 执行相同测试 prompt

所有执行使用**前台顺序模式**（避免后台权限问题）。

### 阶段二：三层评分

1. **Layer 1 — Grader（解包验证）**：逐条检查每个原子断言是否通过，输出通过率
2. **Layer 2 — Comparator（盲评 6 维度）**：对原版和中文版的输出进行盲评打分
   - 维度：准确性、完整性、格式规范、术语质量、自然度、可用性
   - 每个维度 1-5 分
3. **Layer 3 — Analyzer（归因分析）**：对未通过的断言和低分维度做根因分析，生成改进建议

所有 JSON 输出必须遵循 `references/eval_json_schema.md` 定义的 schema。

---

## Phase 6: 自动判定与迭代

运行通过标准检查：

```bash
python scripts/check_pass.py <workspace>/iteration-N/
```

### 通过标准（详见 references/pass_criteria.md）

- CN 断言通过率 >= 原版 × 0.95
- CN 盲评均分 >= 原版均分 - 1.0
- 无 critical 级别错误

### 判定逻辑

- **通过** → 进入 Phase 7
- **未通过** → 执行自动迭代：
  1. 读取 `analysis.json` 中的改进建议
  2. 根据建议修改中文版 skill
  3. 回到 Phase 5 重新评测
  4. 最多迭代 **3 轮**，超过 3 轮仍未通过则暂停，报告问题给用户

**用户确认点**：评测结果出来后，展示通过/未通过状态和关键指标，等待用户确认是否继续。

---

## Phase 7: 上传

读取 `agents/publisher.md` 中的指导，执行打包发布。

### 打包规则

- **中文原生 skill**（Phase 2 直接分流的）：直接打包为 `.tar.gz`
- **翻译过的 skill**：打包时附带三层评测报告

### 执行步骤

1. 运行 `python scripts/generate_report.py` 生成评测报告 HTML
2. 打包 skill 目录和报告为 `.tar.gz`
3. 输出到 `~/l10n-output/` 目录，等待用户上传

最终输出结构：

```
~/l10n-output/
├── skill-a-zh.tar.gz          # 翻译 skill + 评测报告
├── skill-b-zh.tar.gz
└── skill-d.tar.gz             # 中文原生 skill，直接打包
```

---

## 快速模式（--fast）

当用户指定 `--fast` 时，流水线做以下简化：
- Phase 4：只生成 1 个测试 prompt
- Phase 5：只执行单次评测，跳过完整盲评
- Phase 6：放宽通过标准，不做自动迭代

适用于开发调试阶段的快速验证，不建议用于最终发布。

---

## 参考文件
- agents/test_writer.md — 测试 prompt 生成指导
- agents/evaluator.md — 三层评测编排指导
- agents/publisher.md — 打包发布指导
- references/pass_criteria.md — 通过标准定义
- references/eval_json_schema.md — JSON 输出 schema
- references/platform_config.md — 平台配置
- scripts/detect_language.py — 语言检测
- scripts/check_pass.py — 通过标准判定
- scripts/generate_report.py — 三层评测报告生成
