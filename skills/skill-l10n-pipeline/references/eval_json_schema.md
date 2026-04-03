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
        "correctness": "integer — 1-10",
        "completeness": "integer — 1-10",
        "accuracy": "integer — 1-10"
      },
      "structure": {
        "organization": "integer — 1-10",
        "formatting": "integer — 1-10",
        "usability": "integer — 1-10"
      }
    },
    "B": {
      "content": {
        "correctness": "integer — 1-10",
        "completeness": "integer — 1-10",
        "accuracy": "integer — 1-10"
      },
      "structure": {
        "organization": "integer — 1-10",
        "formatting": "integer — 1-10",
        "usability": "integer — 1-10"
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
        "correctness": 9,
        "completeness": 8,
        "accuracy": 9
      },
      "structure": {
        "organization": 8,
        "formatting": 9,
        "usability": 8
      }
    },
    "B": {
      "content": {
        "correctness": 8,
        "completeness": 7,
        "accuracy": 8
      },
      "structure": {
        "organization": 7,
        "formatting": 8,
        "usability": 7
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
  "eval_id": "string — 对应 eval_metadata.json 中的 eval_id",
  "comparison_summary": "string — 对比结果的一段话总结",
  "instruction_following": {
    "A": "string — A 对指令的遵循情况描述",
    "B": "string — B 对指令的遵循情况描述"
  },
  "winner_strengths": [
    {
      "aspect": "string — 优势方面",
      "description": "string — 具体描述"
    }
  ],
  "loser_weaknesses": [
    {
      "aspect": "string — 不足方面",
      "description": "string — 具体描述",
      "severity": "string — critical / medium / low"
    }
  ],
  "improvement_suggestions": [
    "string — 改进建议条目"
  ]
}
```

### 示例

```json
{
  "eval_id": "eval_01",
  "comparison_summary": "英文版在内容完整性和格式规范上整体略优于中文版。中文版在翻译准确性上表现良好，但在部分排版细节上有差异。",
  "instruction_following": {
    "A": "严格遵循了所有指令要求，包括章节结构、字数限制和格式规范。",
    "B": "基本遵循指令，但在页脚格式上使用了纯数字而非'第X页'格式。"
  },
  "winner_strengths": [
    {
      "aspect": "格式一致性",
      "description": "所有页面的页眉页脚格式完全统一，表格对齐精确。"
    },
    {
      "aspect": "内容完整性",
      "description": "包含了所有要求的章节，且每个章节的内容深度符合要求。"
    }
  ],
  "loser_weaknesses": [
    {
      "aspect": "页脚格式",
      "description": "使用纯数字页码而非指定的'第X页'格式。",
      "severity": "low"
    },
    {
      "aspect": "表格对齐",
      "description": "第二个数据表格的列宽不均匀，影响可读性。",
      "severity": "medium"
    }
  ],
  "improvement_suggestions": [
    "统一页脚格式为'第X页'样式",
    "调整表格列宽使数据对齐更加美观",
    "检查中文标点符号的使用是否符合 GB/T 15834 标准"
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
