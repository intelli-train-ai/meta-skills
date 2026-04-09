#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过标准判定脚本 - 判定翻译后的 skill 是否通过评测

用法: python check_pass.py /path/to/workspace/
"""

import argparse
import json
import os
import sys

try:
    from .utils import read_json, discover_eval_ids, extract_pass_rate, extract_comparison_scores
except ImportError:
    from utils import read_json, discover_eval_ids, extract_pass_rate, extract_comparison_scores


def check_critical_issues(analysis_data: dict) -> list[str]:
    """检查 analysis.json 中的 severity=critical 问题"""
    if not analysis_data:
        return []

    critical_issues = []

    items = analysis_data.get("loser_weaknesses", [])
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                severity = str(item.get("severity", "")).lower()
                if severity == "critical":
                    desc = item.get("description") or str(item)
                    critical_issues.append(desc)

    return critical_issues


def check_pass(workspace: str) -> dict:
    """执行通过标准判定"""
    if not os.path.isdir(workspace):
        print(f"错误: 目录不存在 - {workspace}", file=sys.stderr)
        sys.exit(1)

    # 发现所有 eval ID
    eval_ids = discover_eval_ids(workspace)

    if not eval_ids:
        print(f"错误: 未找到 eval 数据文件 - {workspace}", file=sys.stderr)
        sys.exit(1)

    # 收集各 eval 的数据
    cn_pass_rates = []
    en_pass_rates = []
    cn_scores = []
    en_scores = []
    all_critical_issues = []

    for eid in eval_ids:
        # 读取 grading 文件 (flat structure)
        cn_grading = read_json(os.path.join(workspace, "cn_skill", f"grading_eval_{eid}.json"))
        en_grading = read_json(os.path.join(workspace, "en_skill", f"grading_eval_{eid}.json"))

        cn_rate = extract_pass_rate(cn_grading)
        en_rate = extract_pass_rate(en_grading)
        if cn_rate is not None:
            cn_pass_rates.append(cn_rate)
        if en_rate is not None:
            en_pass_rates.append(en_rate)

        # 读取 comparison 文件 (flat structure)
        comparison = read_json(os.path.join(workspace, f"comparison_eval_{eid}.json"))
        cn_score, en_score = extract_comparison_scores(comparison, workspace)
        if cn_score is not None:
            cn_scores.append(cn_score)
        if en_score is not None:
            en_scores.append(en_score)

    # 读取 analysis.json (single file, not per-eval)
    analysis = read_json(os.path.join(workspace, "analysis.json"))
    critical = check_critical_issues(analysis)
    all_critical_issues.extend(critical)

    # 计算均值
    cn_pass_avg = sum(cn_pass_rates) / len(cn_pass_rates) if cn_pass_rates else None
    en_pass_avg = sum(en_pass_rates) / len(en_pass_rates) if en_pass_rates else None
    cn_score_avg = sum(cn_scores) / len(cn_scores) if cn_scores else None
    en_score_avg = sum(en_scores) / len(en_scores) if en_scores else None

    criteria = []

    # 标准1: CN 断言通过率均值 >= 原版均值 * 0.95
    if cn_pass_avg is not None and en_pass_avg is not None:
        threshold = en_pass_avg * 0.95
        met = cn_pass_avg >= threshold
        criteria.append({
            "name": "断言通过率",
            "met": met,
            "cn_value": round(cn_pass_avg, 4),
            "en_value": round(en_pass_avg, 4),
            "threshold": ">=0.95x",
            "detail": f"CN {cn_pass_avg:.4f} >= EN {en_pass_avg:.4f} * 0.95 = {threshold:.4f}"
        })
    else:
        criteria.append({
            "name": "断言通过率",
            "met": False,
            "cn_value": cn_pass_avg,
            "en_value": en_pass_avg,
            "threshold": ">=0.95x",
            "detail": "数据不足，无法判定"
        })

    # 标准2: CN 盲评均分 >= 原版均分 - 1.0
    if cn_score_avg is not None and en_score_avg is not None:
        threshold = en_score_avg - 1.0
        met = cn_score_avg >= threshold
        criteria.append({
            "name": "盲评均分",
            "met": met,
            "cn_value": round(cn_score_avg, 2),
            "en_value": round(en_score_avg, 2),
            "threshold": ">=EN-1.0",
            "detail": f"CN {cn_score_avg:.2f} >= EN {en_score_avg:.2f} - 1.0 = {threshold:.2f}"
        })
    else:
        criteria.append({
            "name": "盲评均分",
            "met": False,
            "cn_value": cn_score_avg,
            "en_value": en_score_avg,
            "threshold": ">=EN-1.0",
            "detail": "数据不足，无法判定"
        })

    # 标准3: 无 critical 错误
    has_critical = len(all_critical_issues) > 0
    criteria.append({
        "name": "无critical错误",
        "met": not has_critical,
        "detail": f"发现 {len(all_critical_issues)} 个 severity=critical 的问题" if has_critical
                  else "未发现 severity=critical 的问题"
    })

    # 汇总
    met_count = sum(1 for c in criteria if c["met"])
    total_count = len(criteria)
    all_passed = met_count == total_count

    return {
        "passed": all_passed,
        "criteria": criteria,
        "summary": f"{met_count}/{total_count} 标准通过"
    }


def main():
    parser = argparse.ArgumentParser(description="判定翻译后的 skill 是否通过评测标准")
    parser.add_argument("workspace", help="workspace 目录路径 (如 /path/to/workspace/)")
    parser.add_argument("--pretty", action="store_true", help="格式化 JSON 输出")
    args = parser.parse_args()

    result = check_pass(args.workspace)

    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
