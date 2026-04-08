#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共享工具函数 - 供 check_pass.py 和 generate_report.py 使用

仅支持 eval_json_schema.md 中定义的规范格式，不做多格式猜测。
"""

import json
import os
import re
import sys


def read_json(path: str) -> dict | list | None:
    """安全读取 JSON 文件"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"警告: 读取 {path} 失败 - {e}", file=sys.stderr)
        return None


def discover_eval_ids(workspace: str) -> list[int]:
    """
    扫描 workspace 目录，根据 comparison_eval_*.json 文件发现所有 eval ID。
    返回排序后的整数 ID 列表。
    """
    ids = set()
    pattern = re.compile(r'^comparison_eval_(\d+)\.json$')
    for name in os.listdir(workspace):
        m = pattern.match(name)
        if m:
            ids.add(int(m.group(1)))

    # 也扫描 grading 文件以防 comparison 缺失
    for subdir in ("cn_skill", "en_skill"):
        dirpath = os.path.join(workspace, subdir)
        if not os.path.isdir(dirpath):
            continue
        grading_pattern = re.compile(r'^grading_eval_(\d+)\.json$')
        for name in os.listdir(dirpath):
            m = grading_pattern.match(name)
            if m:
                ids.add(int(m.group(1)))

    return sorted(ids)


def extract_pass_rate(grading_data: dict) -> float | None:
    """
    从 grading_eval_*.json 提取 pass_rate。
    仅支持规范格式: {"expectations": [...], "summary": {"pass_rate": N, ...}}
    """
    if not grading_data:
        return None

    # 直接从 summary 读取
    if "summary" in grading_data:
        summary = grading_data["summary"]
        if "pass_rate" in summary:
            return float(summary["pass_rate"])
        if "passed" in summary and "total" in summary:
            total = summary["total"]
            return summary["passed"] / total if total > 0 else 0.0

    # 从 expectations 列表计算
    if "expectations" in grading_data and isinstance(grading_data["expectations"], list):
        items = grading_data["expectations"]
        if not items:
            return 0.0
        passed = sum(1 for item in items if isinstance(item, dict) and item.get("passed"))
        return passed / len(items)

    # 直接有顶层 pass_rate
    if "pass_rate" in grading_data:
        return float(grading_data["pass_rate"])

    return None


def extract_comparison_scores(comparison_data: dict, workspace: str) -> tuple[float | None, float | None]:
    """
    从 comparison_eval_*.json 提取 CN 和 EN 的 output_quality 分数。
    返回 (cn_score, en_score)。

    仅支持规范格式:
    {
      "rubric": {"A": {...}, "B": {...}},
      "output_quality": {"A": N, "B": N}
    }

    A/B 映射从 {workspace}/ab_assignments.json 读取。
    """
    if not comparison_data:
        return None, None

    # 提取 A/B 分数
    output_quality = comparison_data.get("output_quality", {})
    a_score = None
    b_score = None

    if isinstance(output_quality, dict):
        a_val = output_quality.get("A")
        b_val = output_quality.get("B")
        if isinstance(a_val, dict):
            a_score = float(a_val["score"]) if "score" in a_val else None
        elif isinstance(a_val, (int, float)):
            a_score = float(a_val)
        if isinstance(b_val, dict):
            b_score = float(b_val["score"]) if "score" in b_val else None
        elif isinstance(b_val, (int, float)):
            b_score = float(b_val)

    # 回退: 从 rubric 的 overall_score 提取
    if a_score is None or b_score is None:
        rubric = comparison_data.get("rubric", {})
        if isinstance(rubric, dict):
            for label in ("A", "B"):
                if label in rubric and isinstance(rubric[label], dict):
                    os_val = rubric[label].get("overall_score")
                    if os_val is not None:
                        if label == "A" and a_score is None:
                            a_score = float(os_val)
                        elif label == "B" and b_score is None:
                            b_score = float(os_val)

    if a_score is None and b_score is None:
        return None, None

    # 读取 A/B 映射
    ab_path = os.path.join(workspace, "ab_assignments.json")
    ab_data = read_json(ab_path)
    ab_map = _parse_ab_assignments(ab_data, comparison_data.get("eval_id"))

    if ab_map:
        cn_score = a_score if ab_map.get("A") == "cn" else b_score
        en_score = a_score if ab_map.get("A") == "en" else b_score
        return cn_score, en_score

    # 无法区分 CN/EN，按 A=cn, B=en 猜测（不理想但比 None 好）
    return a_score, b_score


def _parse_ab_assignments(ab_data, eval_id=None) -> dict:
    """
    解析 ab_assignments.json，返回 {"A": "cn"/"en", "B": "cn"/"en"}。
    ab_data 可以是列表（多 eval）或单个 dict。
    """
    if not ab_data:
        return {}

    record = None
    if isinstance(ab_data, list):
        # 列表格式：找匹配的 eval_id
        for item in ab_data:
            if isinstance(item, dict):
                if eval_id is not None and item.get("eval_id") == eval_id:
                    record = item
                    break
        # 如果没找到精确匹配，取第一个
        if record is None and ab_data and isinstance(ab_data[0], dict):
            record = ab_data[0]
    elif isinstance(ab_data, dict):
        record = ab_data

    if not record:
        return {}

    ab_map = {}
    for key in ("A", "B"):
        val = record.get(key, "")
        val_lower = str(val).lower()
        if "cn" in val_lower or "zh" in val_lower or "chinese" in val_lower:
            ab_map[key] = "cn"
        elif "en" in val_lower or "english" in val_lower:
            ab_map[key] = "en"

    return ab_map
