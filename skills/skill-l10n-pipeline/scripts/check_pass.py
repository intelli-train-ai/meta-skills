#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过标准判定脚本 - 判定翻译后的 skill 是否通过评测

用法: python check_pass.py /path/to/workspace/iteration-N/
"""

import argparse
import json
import os
import sys


def read_json(path: str) -> dict | None:
    """安全读取 JSON 文件"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"警告: 读取 {path} 失败 - {e}", file=sys.stderr)
        return None


def extract_pass_rate(grading_data: dict) -> float | None:
    """
    从 grading.json 提取 pass_rate，兼容多种格式:
    - 格式A: {"expectations": [...], "summary": {"pass_rate": 0.XX}}
    - 格式B: {"total_requirements": N, "passed": M, "results": [...]}
    - 格式C: {"total_score": N, "max_score": M, "details": [...]}
    """
    if not grading_data:
        return None

    # 格式A: 直接有 summary.pass_rate
    if "summary" in grading_data:
        summary = grading_data["summary"]
        if "pass_rate" in summary:
            return float(summary["pass_rate"])
        if "passed" in summary and "total" in summary:
            total = summary["total"]
            return summary["passed"] / total if total > 0 else 0.0

    # 格式B: total_requirements + passed
    if "total_requirements" in grading_data and "passed" in grading_data:
        total = grading_data["total_requirements"]
        if total > 0:
            return grading_data["passed"] / total
        return 0.0

    # 格式C: total_score / max_score
    if "total_score" in grading_data and "max_score" in grading_data:
        max_score = grading_data["max_score"]
        if max_score > 0:
            return grading_data["total_score"] / max_score
        return 0.0

    # 尝试从 expectations/results 列表推断
    for key in ("expectations", "results", "details"):
        if key in grading_data and isinstance(grading_data[key], list):
            items = grading_data[key]
            if not items:
                return 0.0
            passed = 0
            for item in items:
                # 检查各种可能的通过标志
                if item.get("passed") or item.get("pass") or item.get("result") == "pass" \
                        or item.get("status") == "passed" or item.get("met"):
                    passed += 1
            return passed / len(items)

    return None


def extract_comparison_scores(comparison_data: dict, eval_dir: str) -> tuple[float | None, float | None]:
    """
    从 comparison.json 提取 CN 和 EN 的总分，兼容多种格式。
    返回 (cn_score, en_score)
    """
    if not comparison_data:
        return None, None

    # 确定 A/B 映射
    ab_map = {}  # {"A": "cn"/"en", "B": "cn"/"en"}

    # 方式1: 从 ab_assignments.json 读取
    ab_path = os.path.join(eval_dir, "ab_assignments.json")
    ab_data = read_json(ab_path)
    if ab_data:
        for key, val in ab_data.items():
            label = key.upper()
            if label in ("A", "B"):
                val_lower = str(val).lower()
                if "cn" in val_lower or "chinese" in val_lower:
                    ab_map[label] = "cn"
                elif "en" in val_lower or "english" in val_lower:
                    ab_map[label] = "en"

    # 方式2: 从 comparison.json 内部字段推断
    if not ab_map:
        for key in ("ab_mapping", "assignments", "mapping"):
            if key in comparison_data and isinstance(comparison_data[key], dict):
                mapping = comparison_data[key]
                for label, val in mapping.items():
                    label_upper = label.upper()
                    if label_upper in ("A", "B"):
                        val_lower = str(val).lower()
                        if "cn" in val_lower or "chinese" in val_lower:
                            ab_map[label_upper] = "cn"
                        elif "en" in val_lower or "english" in val_lower:
                            ab_map[label_upper] = "en"
                break

    # 提取 A/B 分数
    a_score = None
    b_score = None

    # 尝试多种字段名提取分数
    for score_key in ("total_score", "overall_score", "score", "total"):
        # 直接在 comparison 中的 A/B 分数
        for prefix in ("a_", "b_", "A_", "B_"):
            full_key = prefix + score_key
            if full_key in comparison_data:
                if prefix[0].upper() == "A":
                    a_score = float(comparison_data[full_key])
                else:
                    b_score = float(comparison_data[full_key])

    # 尝试从 scores/results 子对象提取
    for container_key in ("scores", "results", "evaluation"):
        if container_key in comparison_data and isinstance(comparison_data[container_key], dict):
            container = comparison_data[container_key]
            for label in ("A", "a", "B", "b"):
                if label in container:
                    val = container[label]
                    score = None
                    if isinstance(val, (int, float)):
                        score = float(val)
                    elif isinstance(val, dict):
                        for sk in ("total_score", "overall_score", "score", "total"):
                            if sk in val:
                                score = float(val[sk])
                                break
                        # 尝试求和维度分数
                        if score is None and "dimensions" in val:
                            dims = val["dimensions"]
                            if isinstance(dims, dict):
                                score = sum(float(v) for v in dims.values() if isinstance(v, (int, float)))
                            elif isinstance(dims, list):
                                score = sum(float(d.get("score", 0)) for d in dims if isinstance(d, dict))
                    if score is not None:
                        if label.upper() == "A":
                            a_score = score
                        else:
                            b_score = score

    # 尝试从 dimensions 列表汇总
    if a_score is None and b_score is None:
        if "dimensions" in comparison_data and isinstance(comparison_data["dimensions"], list):
            a_total = 0.0
            b_total = 0.0
            count = 0
            for dim in comparison_data["dimensions"]:
                if isinstance(dim, dict):
                    a_val = dim.get("a_score") or dim.get("A_score") or dim.get("score_a")
                    b_val = dim.get("b_score") or dim.get("B_score") or dim.get("score_b")
                    if a_val is not None and b_val is not None:
                        a_total += float(a_val)
                        b_total += float(b_val)
                        count += 1
            if count > 0:
                a_score = a_total
                b_score = b_total

    # 直接有 cn_score/en_score 字段
    if "cn_score" in comparison_data:
        return float(comparison_data["cn_score"]), float(comparison_data.get("en_score", 0))
    if "cn_total" in comparison_data:
        return float(comparison_data["cn_total"]), float(comparison_data.get("en_total", 0))

    # 根据 ab_map 转换
    if ab_map and a_score is not None and b_score is not None:
        cn_score = a_score if ab_map.get("A") == "cn" else b_score
        en_score = a_score if ab_map.get("A") == "en" else b_score
        return cn_score, en_score

    # 如果没有 A/B 映射，尝试用 winner 推断
    if a_score is not None and b_score is not None:
        winner = comparison_data.get("winner", "").upper()
        if winner in ("A", "B"):
            # 无法确定映射关系，返回 None
            pass
        return a_score, b_score  # 无法区分 CN/EN，返回原始分数

    return None, None


def check_critical_issues(analysis_data: dict) -> list[str]:
    """检查 analysis.json 中的 severity=critical 问题"""
    if not analysis_data:
        return []

    critical_issues = []

    # 检查 loser_weaknesses
    for key in ("loser_weaknesses", "weaknesses", "issues", "problems"):
        items = analysis_data.get(key, [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    severity = str(item.get("severity", "")).lower()
                    if severity == "critical":
                        desc = item.get("description") or item.get("detail") or item.get("message") or str(item)
                        critical_issues.append(desc)

    return critical_issues


def check_pass(iteration_dir: str) -> dict:
    """执行通过标准判定"""
    if not os.path.isdir(iteration_dir):
        print(f"错误: 目录不存在 - {iteration_dir}", file=sys.stderr)
        sys.exit(1)

    # 查找所有 eval-* 目录
    eval_dirs = sorted([
        os.path.join(iteration_dir, d)
        for d in os.listdir(iteration_dir)
        if d.startswith("eval-") and os.path.isdir(os.path.join(iteration_dir, d))
    ])

    if not eval_dirs:
        print(f"错误: 未找到 eval-* 目录 - {iteration_dir}", file=sys.stderr)
        sys.exit(1)

    # 收集各 eval 的数据
    cn_pass_rates = []
    en_pass_rates = []
    cn_scores = []
    en_scores = []
    all_critical_issues = []

    for eval_dir in eval_dirs:
        # 读取 grading.json
        cn_grading = read_json(os.path.join(eval_dir, "cn_skill", "grading.json"))
        en_grading = read_json(os.path.join(eval_dir, "en_skill", "grading.json"))

        cn_rate = extract_pass_rate(cn_grading)
        en_rate = extract_pass_rate(en_grading)
        if cn_rate is not None:
            cn_pass_rates.append(cn_rate)
        if en_rate is not None:
            en_pass_rates.append(en_rate)

        # 读取 comparison.json
        comparison = read_json(os.path.join(eval_dir, "comparison.json"))
        cn_score, en_score = extract_comparison_scores(comparison, eval_dir)
        if cn_score is not None:
            cn_scores.append(cn_score)
        if en_score is not None:
            en_scores.append(en_score)

        # 读取 analysis.json
        analysis = read_json(os.path.join(eval_dir, "analysis.json"))
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
            "detail": f"CN {cn_pass_avg:.4f} {'>=':s} EN {en_pass_avg:.4f} * 0.95 = {threshold:.4f}"
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
            "detail": f"CN {cn_score_avg:.2f} {'>=':s} EN {en_score_avg:.2f} - 1.0 = {threshold:.2f}"
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
    parser.add_argument("iteration_dir", help="iteration 目录路径 (如 /path/to/workspace/iteration-0/)")
    parser.add_argument("--pretty", action="store_true", help="格式化 JSON 输出")
    args = parser.parse_args()

    result = check_pass(args.iteration_dir)

    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
