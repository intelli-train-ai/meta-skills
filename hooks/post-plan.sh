#!/bin/bash
# 在 ExitPlanMode 后触发，提示 Claude 调用 plan-visualizer
# hook 的 stdout 会作为反馈注入到对话中

# 从 stdin 读取 hook input JSON
INPUT=$(cat)

# 提取 plan 文件路径（如果有的话）
PLAN_FILE=$(echo "$INPUT" | jq -r '.tool_result // empty' 2>/dev/null | grep -oP 'plan file.*?:\s*\K\S+\.md' || true)

if [ -n "$PLAN_FILE" ]; then
    echo "[meta-skills] 检测到计划完成，请使用 /meta-skills:skill-plan-visualizer 将计划 $PLAN_FILE 可视化。"
else
    echo "[meta-skills] 检测到计划完成，请使用 /meta-skills:skill-plan-visualizer 将当前计划可视化。"
fi
