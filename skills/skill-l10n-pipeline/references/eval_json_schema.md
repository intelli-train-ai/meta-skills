# 评测 JSON 输出 Schema

本文档定义了三层评测中所有 JSON 文件的精确格式。Agent 必须严格遵守这些 schema。

## eval_metadata.json

每个 eval 目录下的元数据文件。

### Schema

```json
{
  "eval_id": "string — 唯一标识符，格式为 eval_<序号>",
  "eval_name": "string — eval 的简短描述性名称",
  "source_skill": "string — 原版 skill 名称",
  "target_skill": "string — 翻译版 skill 名称",
  "source_language": "string — 原版语言代码，如 en",
  "target_language": "string — 目标语言代码，如 zh",
  "created_at": "string — ISO 8601 时间戳",
  "prompt": "string — 用于该 eval 的用户提示词"
}
```

### 示例

```json
{
  "eval_id": "eval_01",
  "eval_name": "基础功能测试",
  "source_skill": "pdf-maker",
  "target_skill": "pdf-maker-zh",
  "source_language": "en",
  "target_language": "zh",
  "created_at": "2026-04-02T10:30:00Z",
  "prompt": "请根据以下内容生成一份 PDF 报告..."
}
```

## grading.json (第一层)

断言式评分结果。

**关键**: 必须使用 `expectations` 数组，每个元素有 `text`, `passed`, `evidence` 三个字段。

**禁止**: 不要使用 `results`, `details`, `requirements` 等替代字段名。

### Schema

```json
{
  "eval_id": "string — 对应 eval_metadata.json 中的 eval_id",
  "version": "string — en 或 zh，标识被评分的版本",
  "expectations": [
    {
      "text": "string — 断言描述，如'输出文件存在且可打开'",
      "passed": "boolean — 是否通过",
      "evidence": "string — 判断依据的简要说明"
    }
  ],
  "pass_rate": "number — 通过的断言数 / 总断言数，0.0-1.0",
  "total": "integer — 断言总数",
  "passed_count": "integer — 通过的断言数"
}
```

### 示例

```json
{
  "eval_id": "eval_01",
  "version": "zh",
  "expectations": [
    {
      "text": "输出文件存在且可打开",
      "passed": true,
      "evidence": "output.pdf 存在，文件大小 245KB，可正常打开"
    },
    {
      "text": "包含所有要求的章节标题",
      "passed": true,
      "evidence": "找到全部 5 个章节标题：引言、方法、结果、讨论、结论"
    },
    {
      "text": "页码连续且正确",
      "passed": false,
      "evidence": "第 3 页页码显示为 5，页码不连续"
    }
  ],
  "pass_rate": 0.67,
  "total": 3,
  "passed_count": 2
}
```

## comparison.json (第二层)

盲评对比结果。

**关键**: 必须有 `winner`, `rubric`, `output_quality` 三个顶层字段。rubric 下 A 和 B 各有 content（correctness/completeness/accuracy）和 structure（organization/formatting/usability）。

### Schema

```json
{
  "eval_id": "string — 对应 eval_metadata.json 中的 eval_id",
  "winner": "string — 'A', 'B', 或 'tie'",
  "rubric": {
    "A": {
      "content": {
        "correctness": "integer — 1-5",
        "completeness": "integer — 1-5",
        "accuracy": "integer — 1-5"
      },
      "structure": {
        "organization": "integer — 1-5",
        "formatting": "integer — 1-5",
        "usability": "integer — 1-5"
      }
    },
    "B": {
      "content": {
        "correctness": "integer — 1-5",
        "completeness": "integer — 1-5",
        "accuracy": "integer — 1-5"
      },
      "structure": {
        "organization": "integer — 1-5",
        "formatting": "integer — 1-5",
        "usability": "integer — 1-5"
      }
    }
  },
  "output_quality": {
    "A": "number — A 的综合得分，1.0-10.0",
    "B": "number — B 的综合得分，1.0-10.0"
  },
  "reasoning": "string — 评判理由的简要说明"
}
```

### 示例

```json
{
  "eval_id": "eval_01",
  "winner": "A",
  "rubric": {
    "A": {
      "content": {
        "correctness": 5,
        "completeness": 4,
        "accuracy": 5
      },
      "structure": {
        "organization": 4,
        "formatting": 5,
        "usability": 4
      }
    },
    "B": {
      "content": {
        "correctness": 4,
        "completeness": 3,
        "accuracy": 4
      },
      "structure": {
        "organization": 3,
        "formatting": 4,
        "usability": 3
      }
    }
  },
  "output_quality": {
    "A": 8.5,
    "B": 7.5
  },
  "reasoning": "A 版本在内容准确性和格式规范方面略优于 B 版本，特别是在表格对齐和引用格式上更加规范。"
}
```

## analysis.json (第三层)

深度分析结果。

**关键**: 必须有 `comparison_summary`, `instruction_following`, `winner_strengths`, `loser_weaknesses`, `improvement_suggestions`。

### Schema

```json
{
  "comparison_summary": {
    "overall_winner": "string — 'cn_skill' 或 'en_skill'",
    "cn_wins": "integer — CN 胜出的 eval 数",
    "en_wins": "integer — EN 胜出的 eval 数",
    "ties": "integer — 平局的 eval 数"
  },
  "instruction_following": {
    "cn_skill": {
      "score": "integer — 指令遵循度评分，1-10",
      "issues": ["string — 具体遵循问题描述"]
    },
    "en_skill": {
      "score": "integer — 指令遵循度评分，1-10",
      "issues": ["string — 具体遵循问题描述"]
    }
  },
  "winner_strengths": [
    "string — 胜出者优势描述"
  ],
  "loser_weaknesses": [
    {
      "category": "string — 问题类别，如 instructions / localization / examples",
      "description": "string — 具体描述",
      "severity": "string — critical / high / medium / low"
    }
  ],
  "improvement_suggestions": [
    {
      "priority": "string — high / medium / low",
      "category": "string — 问题类别",
      "suggestion": "string — 改进建议",
      "expected_impact": "string — 预期影响"
    }
  ]
}
```

### 示例

```json
{
  "comparison_summary": {
    "overall_winner": "cn_skill",
    "cn_wins": 3,
    "en_wins": 1,
    "ties": 1
  },
  "instruction_following": {
    "cn_skill": {
      "score": 8,
      "issues": [
        "在 eval_2 中未使用 SKILL.md 指定的模板格式",
        "输出文件命名不符合指令要求"
      ]
    },
    "en_skill": {
      "score": 7,
      "issues": [
        "在 eval_0 中跳过了验证步骤",
        "未遵循指令中'始终使用中文标点'的要求",
        "在 eval_3 中自行添加了指令未要求的额外章节"
      ]
    }
  },
  "winner_strengths": [
    "中文版 SKILL.md 的指令更具体，明确列出了输出结构要求",
    "中文版包含了针对中文排版的专门指导，减少了格式问题",
    "翻译后的模板更符合中文用户的阅读习惯"
  ],
  "loser_weaknesses": [
    {
      "category": "instructions",
      "description": "原版指令中'format appropriately'过于模糊，导致中文输出的格式不一致",
      "severity": "high"
    },
    {
      "category": "localization",
      "description": "原版缺少中文排版相关指导（标点、段落间距、字体建议）",
      "severity": "medium"
    }
  ],
  "improvement_suggestions": [
    {
      "priority": "high",
      "category": "instructions",
      "suggestion": "将'format appropriately'替换为具体的格式规范",
      "expected_impact": "消除格式模糊性，预计格式相关断言通过率提升 30%"
    },
    {
      "priority": "medium",
      "category": "localization",
      "suggestion": "添加中文排版专节：中文标点规范、中英文混排时的空格规则",
      "expected_impact": "减少语言质量相关的扣分"
    }
  ]
}
```

## ab_assignments.json

A/B 盲评分配文件，用于记录哪个版本被分配为 A 或 B。

### Schema

```json
{
  "eval_id": "string — 对应 eval_metadata.json 中的 eval_id",
  "A": "string — 'en' 或 'zh'，表示 A 对应的版本",
  "B": "string — 'en' 或 'zh'，表示 B 对应的版本",
  "randomized": "boolean — 是否随机分配"
}
```

### 示例

```json
{
  "eval_id": "eval_01",
  "A": "zh",
  "B": "en",
  "randomized": true
}
```

## timing.json

运行计时数据，记录每个阶段的耗时。

### Schema

```json
{
  "eval_id": "string — 对应 eval_metadata.json 中的 eval_id",
  "stages": {
    "en_execution": "number — 英文版执行耗时（秒）",
    "zh_execution": "number — 中文版执行耗时（秒）",
    "grading": "number — 第一层评分耗时（秒）",
    "comparison": "number — 第二层对比耗时（秒）",
    "analysis": "number — 第三层分析耗时（秒）"
  },
  "total_seconds": "number — 总耗时（秒）",
  "started_at": "string — ISO 8601 开始时间",
  "finished_at": "string — ISO 8601 结束时间"
}
```

### 示例

```json
{
  "eval_id": "eval_01",
  "stages": {
    "en_execution": 45.2,
    "zh_execution": 52.8,
    "grading": 30.1,
    "comparison": 25.6,
    "analysis": 18.3
  },
  "total_seconds": 172.0,
  "started_at": "2026-04-02T10:30:00Z",
  "finished_at": "2026-04-02T10:32:52Z"
}
```
