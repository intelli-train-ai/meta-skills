#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三层评测报告 HTML 生成脚本

用法: python generate_report.py /path/to/workspace/iteration-N/ --output report.html --skill-name "xxx"
"""

import argparse
import json
import os
import sys
from datetime import date


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
    """从 grading.json 提取 pass_rate，兼容多种格式"""
    if not grading_data:
        return None

    if "summary" in grading_data:
        summary = grading_data["summary"]
        if "pass_rate" in summary:
            return float(summary["pass_rate"])
        if "passed" in summary and "total" in summary:
            total = summary["total"]
            return summary["passed"] / total if total > 0 else 0.0

    if "total_requirements" in grading_data and "passed" in grading_data:
        total = grading_data["total_requirements"]
        return grading_data["passed"] / total if total > 0 else 0.0

    if "total_score" in grading_data and "max_score" in grading_data:
        max_score = grading_data["max_score"]
        return grading_data["total_score"] / max_score if max_score > 0 else 0.0

    for key in ("expectations", "results", "details"):
        if key in grading_data and isinstance(grading_data[key], list):
            items = grading_data[key]
            if not items:
                return 0.0
            passed = sum(1 for item in items if isinstance(item, dict) and (
                item.get("passed") or item.get("pass") or item.get("result") == "pass"
                or item.get("status") == "passed" or item.get("met")
            ))
            return passed / len(items)

    return None


def extract_grading_items(grading_data: dict) -> list[dict]:
    """从 grading.json 提取逐条断言结果"""
    if not grading_data:
        return []

    for key in ("expectations", "results", "details"):
        if key in grading_data and isinstance(grading_data[key], list):
            items = []
            for item in grading_data[key]:
                if not isinstance(item, dict):
                    continue
                # 判定是否通过
                passed = bool(
                    item.get("passed") or item.get("pass") or item.get("result") == "pass"
                    or item.get("status") == "passed" or item.get("met")
                )
                # 提取描述
                desc = (item.get("description") or item.get("requirement") or
                        item.get("name") or item.get("expectation") or str(item))
                # 提取证据
                evidence = item.get("evidence") or item.get("detail") or item.get("reason") or ""
                items.append({
                    "description": desc,
                    "passed": passed,
                    "evidence": evidence,
                })
            return items
    return []


def extract_passed_total(grading_data: dict) -> tuple[int, int]:
    """提取通过数/总数"""
    items = extract_grading_items(grading_data)
    if items:
        passed = sum(1 for i in items if i["passed"])
        return passed, len(items)

    if not grading_data:
        return 0, 0

    if "summary" in grading_data:
        s = grading_data["summary"]
        if "passed" in s and "total" in s:
            return int(s["passed"]), int(s["total"])
    if "total_requirements" in grading_data and "passed" in grading_data:
        return int(grading_data["passed"]), int(grading_data["total_requirements"])

    return 0, 0


def extract_comparison_scores(comparison_data: dict, eval_dir: str) -> tuple[float | None, float | None]:
    """从 comparison.json 提取 CN 和 EN 的总分"""
    if not comparison_data:
        return None, None

    # 直接有 cn_score/en_score
    if "cn_score" in comparison_data:
        return float(comparison_data["cn_score"]), float(comparison_data.get("en_score", 0))
    if "cn_total" in comparison_data:
        return float(comparison_data["cn_total"]), float(comparison_data.get("en_total", 0))

    # 确定 A/B 映射
    ab_map = {}
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

    if not ab_map:
        for mkey in ("ab_mapping", "assignments", "mapping"):
            if mkey in comparison_data and isinstance(comparison_data[mkey], dict):
                for label, val in comparison_data[mkey].items():
                    label_upper = label.upper()
                    if label_upper in ("A", "B"):
                        val_lower = str(val).lower()
                        if "cn" in val_lower or "chinese" in val_lower:
                            ab_map[label_upper] = "cn"
                        elif "en" in val_lower or "english" in val_lower:
                            ab_map[label_upper] = "en"
                break

    # 提取 A/B 分数
    a_score, b_score = None, None

    for score_key in ("total_score", "overall_score", "score", "total"):
        for prefix in ("a_", "b_", "A_", "B_"):
            full_key = prefix + score_key
            if full_key in comparison_data:
                if prefix[0].upper() == "A":
                    a_score = float(comparison_data[full_key])
                else:
                    b_score = float(comparison_data[full_key])

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

    if a_score is None and b_score is None:
        if "dimensions" in comparison_data and isinstance(comparison_data["dimensions"], list):
            a_total, b_total, count = 0.0, 0.0, 0
            for dim in comparison_data["dimensions"]:
                if isinstance(dim, dict):
                    a_val = dim.get("a_score") or dim.get("A_score") or dim.get("score_a")
                    b_val = dim.get("b_score") or dim.get("B_score") or dim.get("score_b")
                    if a_val is not None and b_val is not None:
                        a_total += float(a_val)
                        b_total += float(b_val)
                        count += 1
            if count > 0:
                a_score, b_score = a_total, b_total

    if ab_map and a_score is not None and b_score is not None:
        cn_score = a_score if ab_map.get("A") == "cn" else b_score
        en_score = a_score if ab_map.get("A") == "en" else b_score
        return cn_score, en_score

    if a_score is not None and b_score is not None:
        return a_score, b_score

    return None, None


def extract_comparison_dimensions(comparison_data: dict) -> list[dict]:
    """提取盲评维度详情"""
    if not comparison_data:
        return []

    dims = comparison_data.get("dimensions", [])
    if isinstance(dims, list):
        result = []
        for dim in dims:
            if isinstance(dim, dict):
                name = dim.get("name") or dim.get("dimension") or "未知维度"
                a_score = dim.get("a_score") or dim.get("A_score") or dim.get("score_a")
                b_score = dim.get("b_score") or dim.get("B_score") or dim.get("score_b")
                result.append({
                    "name": name,
                    "a_score": float(a_score) if a_score is not None else None,
                    "b_score": float(b_score) if b_score is not None else None,
                })
        return result
    return []


def extract_comparison_reasoning(comparison_data: dict) -> str:
    """提取盲评理由"""
    if not comparison_data:
        return ""
    for key in ("reasoning", "rationale", "explanation", "summary", "analysis"):
        if key in comparison_data and isinstance(comparison_data[key], str):
            return comparison_data[key]
    return ""


def extract_winner(comparison_data: dict, eval_dir: str) -> str:
    """提取胜出方，返回 'cn', 'en', 或 'tie'"""
    if not comparison_data:
        return "unknown"

    # 直接有 winner 字段
    winner = comparison_data.get("winner", "")
    winner_lower = str(winner).lower()
    if "cn" in winner_lower or "chinese" in winner_lower:
        return "cn"
    if "en" in winner_lower or "english" in winner_lower:
        return "en"
    if "tie" in winner_lower or "draw" in winner_lower:
        return "tie"

    # 根据分数判断
    cn_score, en_score = extract_comparison_scores(comparison_data, eval_dir)
    if cn_score is not None and en_score is not None:
        if cn_score > en_score:
            return "cn"
        elif en_score > cn_score:
            return "en"
        else:
            return "tie"

    return "unknown"


def extract_ab_mapping_str(comparison_data: dict, eval_dir: str) -> str:
    """获取 A/B 映射的简短描述"""
    ab_path = os.path.join(eval_dir, "ab_assignments.json")
    ab_data = read_json(ab_path)
    if ab_data:
        parts = []
        for key in sorted(ab_data.keys()):
            parts.append(f"{key.upper()}={ab_data[key]}")
        return ", ".join(parts)

    if comparison_data:
        for mkey in ("ab_mapping", "assignments", "mapping"):
            if mkey in comparison_data and isinstance(comparison_data[mkey], dict):
                mapping = comparison_data[mkey]
                parts = []
                for key in sorted(mapping.keys()):
                    parts.append(f"{key.upper()}={mapping[key]}")
                return ", ".join(parts)
    return ""


def extract_analysis_data(analysis_data: dict) -> dict:
    """提取第三层归因分析数据"""
    if not analysis_data:
        return {}

    result = {}

    # 指令遵循度评分
    for key in ("cn_score", "cn_instruction_score", "winner_score"):
        if key in analysis_data:
            result["cn_instruction_score"] = float(analysis_data[key])
            break
    for key in ("en_score", "en_instruction_score", "loser_score"):
        if key in analysis_data:
            result["en_instruction_score"] = float(analysis_data[key])
            break

    # 胜出者优势
    for key in ("winner_strengths", "strengths", "advantages"):
        if key in analysis_data and isinstance(analysis_data[key], list):
            result["strengths"] = analysis_data[key]
            break

    # 失败方劣势
    for key in ("loser_weaknesses", "weaknesses", "issues"):
        if key in analysis_data and isinstance(analysis_data[key], list):
            result["weaknesses"] = analysis_data[key]
            break

    # 改进建议
    for key in ("suggestions", "recommendations", "improvements"):
        if key in analysis_data and isinstance(analysis_data[key], list):
            result["suggestions"] = analysis_data[key]
            break

    # 核心洞察
    for key in ("insight", "core_insight", "key_finding", "summary"):
        if key in analysis_data and isinstance(analysis_data[key], str):
            result["insight"] = analysis_data[key]
            break

    return result


def html_escape(text: str) -> str:
    """HTML 转义"""
    if not isinstance(text, str):
        text = str(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_css() -> str:
    """生成内联 CSS 样式"""
    return """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; background: #f5f5f7; color: #1d1d1f; line-height: 1.6; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
h1 { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
h2 { font-size: 22px; font-weight: 600; margin: 32px 0 16px; padding-bottom: 8px; border-bottom: 2px solid #0071e3; }
h3 { font-size: 18px; font-weight: 600; margin: 24px 0 12px; }
h4 { font-size: 15px; font-weight: 600; margin: 16px 0 8px; color: #424245; }
.subtitle { color: #86868b; font-size: 16px; margin-bottom: 24px; }
.tabs { display: flex; gap: 0; margin-bottom: 0; border-bottom: 1px solid #d2d2d7; }
.tab { padding: 12px 24px; cursor: pointer; font-size: 14px; font-weight: 500; color: #86868b; border-bottom: 2px solid transparent; transition: all 0.2s; }
.tab:hover { color: #1d1d1f; }
.tab.active { color: #0071e3; border-bottom-color: #0071e3; }
.tab-content { display: none; }
.tab-content.active { display: block; }
.card { background: white; border-radius: 12px; padding: 24px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
.stat-card { background: white; border-radius: 12px; padding: 20px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.stat-value { font-size: 36px; font-weight: 700; }
.stat-label { font-size: 13px; color: #86868b; margin-top: 4px; }
.cn-color { color: #34c759; }
.en-color { color: #0071e3; }
.tie-color { color: #ff9500; }
table { width: 100%; border-collapse: collapse; margin: 12px 0; }
th { background: #1d1d1f; color: white; padding: 10px 14px; text-align: left; font-size: 13px; font-weight: 600; }
td { padding: 10px 14px; border-bottom: 1px solid #e8e8ed; font-size: 14px; }
tr:hover td { background: #f5f5f7; }
.pass { color: #34c759; font-weight: 600; }
.fail { color: #ff3b30; font-weight: 600; }
.winner-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.winner-cn { background: #d1f7d6; color: #1a7a2e; }
.winner-en { background: #d1e5f7; color: #1a5a9e; }
.winner-tie { background: #fff3d1; color: #9e7a1a; }
.dimension-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.evidence { font-size: 13px; color: #6e6e73; margin-top: 4px; font-style: italic; }
.insight-card { border-left: 4px solid #0071e3; padding: 12px 16px; margin: 8px 0; background: #f0f7ff; border-radius: 0 8px 8px 0; }
.strength-card { border-left-color: #34c759; background: #f0fff4; }
.weakness-card { border-left-color: #ff3b30; background: #fff5f5; }
.suggestion-card { border-left-color: #ff9500; background: #fffbf0; }
.priority-high { display: inline-block; padding: 1px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; background: #ff3b30; color: white; }
.priority-medium { display: inline-block; padding: 1px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; background: #ff9500; color: white; }
.priority-low { display: inline-block; padding: 1px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; background: #86868b; color: white; }
.eval-nav { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.eval-btn { padding: 8px 16px; border: 1px solid #d2d2d7; border-radius: 8px; background: white; cursor: pointer; font-size: 13px; transition: all 0.2s; }
.eval-btn:hover { border-color: #0071e3; }
.eval-btn.active { background: #0071e3; color: white; border-color: #0071e3; }
.no-data { color: #86868b; font-style: italic; padding: 24px; text-align: center; }
"""


def generate_js(eval_count: int) -> str:
    """生成 JavaScript 交互代码"""
    return """
function switchTab(tabId) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.getElementById(tabId).classList.add('active');
  event.target.classList.add('active');
}

function switchEval(idx) {
  document.querySelectorAll('#layer1 .eval-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.eval-detail').forEach(d => d.style.display = 'none');
  document.querySelectorAll('#layer1 .eval-btn')[idx].classList.add('active');
  document.getElementById('eval-detail-' + idx).style.display = 'block';
}

function switchBlind(idx) {
  document.querySelectorAll('#layer2 .eval-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.blind-detail').forEach(d => d.style.display = 'none');
  document.querySelectorAll('#layer2 .eval-btn')[idx].classList.add('active');
  document.getElementById('blind-detail-' + idx).style.display = 'block';
}
"""


def get_eval_label(eval_dir: str, metadata: dict | None) -> str:
    """获取 eval 的显示标签"""
    dirname = os.path.basename(eval_dir)
    idx = dirname.replace("eval-", "")
    if metadata:
        prompt = metadata.get("prompt", "") or metadata.get("description", "")
        if prompt:
            # 截取前 20 个字符作为标签
            short = prompt[:20].strip()
            if len(prompt) > 20:
                short += "..."
            return f"Eval {idx}: {short}"
    return f"Eval {idx}"


def generate_overview_tab(eval_data_list: list[dict]) -> str:
    """生成总览标签页"""
    cn_wins, en_wins, ties = 0, 0, 0
    cn_scores_all = []
    en_scores_all = []
    cn_pass_rates = []
    en_pass_rates = []

    for ed in eval_data_list:
        w = ed.get("winner", "unknown")
        if w == "cn":
            cn_wins += 1
        elif w == "en":
            en_wins += 1
        elif w == "tie":
            ties += 1
        if ed["cn_score"] is not None:
            cn_scores_all.append(ed["cn_score"])
        if ed["en_score"] is not None:
            en_scores_all.append(ed["en_score"])
        if ed["cn_pass_rate"] is not None:
            cn_pass_rates.append(ed["cn_pass_rate"])
        if ed["en_pass_rate"] is not None:
            en_pass_rates.append(ed["en_pass_rate"])

    cn_avg = sum(cn_scores_all) / len(cn_scores_all) if cn_scores_all else 0
    en_avg = sum(en_scores_all) / len(en_scores_all) if en_scores_all else 0
    cn_pr = sum(cn_pass_rates) / len(cn_pass_rates) if cn_pass_rates else 0
    en_pr = sum(en_pass_rates) / len(en_pass_rates) if en_pass_rates else 0

    html = '<h2>评测总览</h2>\n'

    # 统计卡片
    html += '<div class="summary-grid">\n'
    html += f'  <div class="stat-card"><div class="stat-value cn-color">{cn_wins}</div><div class="stat-label">CN 胜出</div></div>\n'
    html += f'  <div class="stat-card"><div class="stat-value tie-color">{ties}</div><div class="stat-label">平局</div></div>\n'
    html += f'  <div class="stat-card"><div class="stat-value en-color">{en_wins}</div><div class="stat-label">EN 胜出</div></div>\n'
    html += f'  <div class="stat-card"><div class="stat-value cn-color">{cn_avg:.2f}</div><div class="stat-label">CN 盲评均分</div></div>\n'
    html += f'  <div class="stat-card"><div class="stat-value en-color">{en_avg:.2f}</div><div class="stat-label">EN 盲评均分</div></div>\n'

    pr_text = f"CN {cn_pr:.0%} / EN {en_pr:.0%}"
    html += f'  <div class="stat-card"><div class="stat-value">{pr_text}</div><div class="stat-label">断言通过率</div></div>\n'
    html += '</div>\n'

    # 各测试对比表格
    html += '<div class="card">\n<h3>各测试盲评对比</h3>\n<table>\n'
    html += '  <tr><th>测试用例</th><th>CN 分数</th><th>EN 分数</th><th>差距</th><th>胜出</th></tr>\n'
    for ed in eval_data_list:
        label = html_escape(ed["label"])
        cn_s = f'{ed["cn_score"]:.2f}' if ed["cn_score"] is not None else "N/A"
        en_s = f'{ed["en_score"]:.2f}' if ed["en_score"] is not None else "N/A"
        if ed["cn_score"] is not None and ed["en_score"] is not None:
            diff = ed["cn_score"] - ed["en_score"]
            diff_str = f'+{diff:.2f}' if diff > 0 else f'{diff:.2f}' if diff < 0 else "0"
        else:
            diff_str = "N/A"
        w = ed["winner"]
        if w == "cn":
            badge = '<span class="winner-badge winner-cn">CN</span>'
        elif w == "en":
            badge = '<span class="winner-badge winner-en">EN</span>'
        elif w == "tie":
            badge = '<span class="winner-badge winner-tie">TIE</span>'
        else:
            badge = '<span class="winner-badge">N/A</span>'

        bold_cn = "<strong>" if w == "cn" else ""
        bold_cn_end = "</strong>" if w == "cn" else ""
        bold_en = "<strong>" if w == "en" else ""
        bold_en_end = "</strong>" if w == "en" else ""

        html += f'  <tr><td><strong>{label}</strong></td><td>{bold_cn}{cn_s}{bold_cn_end}</td><td>{bold_en}{en_s}{bold_en_end}</td><td>{diff_str}</td><td>{badge}</td></tr>\n'
    html += '</table>\n</div>\n'

    return html


def generate_layer1_tab(eval_data_list: list[dict]) -> str:
    """生成第一层标签页"""
    html = '<h2>第一层: Grader 逐断言评分</h2>\n'
    html += '<p style="color:#86868b;margin-bottom:16px">通过解包 .docx 文件检查实际 XML 内容来验证每条原子需求。</p>\n'

    if not any(ed.get("cn_grading_items") or ed.get("en_grading_items") for ed in eval_data_list):
        html += '<div class="card"><p class="no-data">暂无第一层评测数据</p></div>\n'
        return html

    # Eval 导航按钮
    html += '<div class="eval-nav">\n'
    for i, ed in enumerate(eval_data_list):
        active = " active" if i == 0 else ""
        html += f'  <button class="eval-btn{active}" onclick="switchEval({i})">{html_escape(ed["label"])}</button>\n'
    html += '</div>\n'

    # 各 eval 详情
    for i, ed in enumerate(eval_data_list):
        display = "" if i == 0 else ' style="display:none"'
        cn_items = ed.get("cn_grading_items", [])
        en_items = ed.get("en_grading_items", [])
        cn_passed, cn_total = ed.get("cn_passed_total", (0, 0))
        en_passed, en_total = ed.get("en_passed_total", (0, 0))

        html += f'<div class="eval-detail" id="eval-detail-{i}"{display}>\n<div class="card">\n'
        html += f'<h3>{html_escape(ed["label"])} (CN {cn_passed}/{cn_total} | EN {en_passed}/{en_total})</h3>\n'

        if cn_items or en_items:
            html += '<table>\n<tr><th>#</th><th>原子需求</th><th>CN</th><th>EN</th><th>CN 证据</th><th>EN 证据</th></tr>\n'
            max_len = max(len(cn_items), len(en_items))
            for j in range(max_len):
                cn_item = cn_items[j] if j < len(cn_items) else {}
                en_item = en_items[j] if j < len(en_items) else {}
                desc = html_escape(cn_item.get("description", "") or en_item.get("description", ""))
                cn_status = "PASS" if cn_item.get("passed") else "FAIL" if cn_item else "N/A"
                en_status = "PASS" if en_item.get("passed") else "FAIL" if en_item else "N/A"
                cn_class = "pass" if cn_item.get("passed") else "fail" if cn_item else ""
                en_class = "pass" if en_item.get("passed") else "fail" if en_item else ""
                cn_ev = html_escape(cn_item.get("evidence", ""))
                en_ev = html_escape(en_item.get("evidence", ""))
                html += f'<tr><td>{j+1}</td><td>{desc}</td>'
                html += f'<td class="{cn_class}">{cn_status}</td><td class="{en_class}">{en_status}</td>'
                html += f'<td class="evidence">{cn_ev}</td><td class="evidence">{en_ev}</td></tr>\n'
            html += '</table>\n'
        else:
            html += '<p class="no-data">暂无断言数据</p>\n'

        html += '</div>\n</div>\n'

    return html


def generate_layer2_tab(eval_data_list: list[dict]) -> str:
    """生成第二层标签页"""
    html = '<h2>第二层: Comparator 盲评对比</h2>\n'
    html += '<p style="color:#86868b;margin-bottom:16px">两个输出被标记为 A/B（随机分配），评审者不知道哪个是 CN/EN，纯粹基于输出质量打分。</p>\n'

    if not any(ed.get("cn_score") is not None for ed in eval_data_list):
        html += '<div class="card"><p class="no-data">暂无第二层盲评数据</p></div>\n'
        return html

    # 导航按钮
    html += '<div class="eval-nav">\n'
    for i, ed in enumerate(eval_data_list):
        active = " active" if i == 0 else ""
        html += f'  <button class="eval-btn{active}" onclick="switchBlind({i})">{html_escape(ed["label"])}</button>\n'
    html += '</div>\n'

    # 各 eval 盲评详情
    for i, ed in enumerate(eval_data_list):
        display = "" if i == 0 else ' style="display:none"'
        w = ed["winner"]
        if w == "cn":
            badge = '<span class="winner-badge winner-cn">CN 胜</span>'
        elif w == "en":
            badge = '<span class="winner-badge winner-en">EN 胜</span>'
        elif w == "tie":
            badge = '<span class="winner-badge winner-tie">平局</span>'
        else:
            badge = ''

        ab_str = ed.get("ab_mapping_str", "")
        if ab_str:
            badge += f' <span style="font-size:12px;color:#86868b">({html_escape(ab_str)})</span>'

        html += f'<div class="blind-detail" id="blind-detail-{i}"{display}>\n<div class="card">\n'
        html += f'<h3>{html_escape(ed["label"])} {badge}</h3>\n'

        # 维度分数表
        dims = ed.get("comparison_dimensions", [])
        if dims:
            html += '<h4>维度评分</h4>\n<table>\n<tr><th>维度</th><th>A</th><th>B</th></tr>\n'
            for dim in dims:
                a_s = f'{dim["a_score"]:.1f}' if dim["a_score"] is not None else "N/A"
                b_s = f'{dim["b_score"]:.1f}' if dim["b_score"] is not None else "N/A"
                html += f'<tr><td>{html_escape(dim["name"])}</td><td>{a_s}</td><td>{b_s}</td></tr>\n'
            html += '</table>\n'

        # 总分
        cn_s = f'{ed["cn_score"]:.2f}' if ed["cn_score"] is not None else "N/A"
        en_s = f'{ed["en_score"]:.2f}' if ed["en_score"] is not None else "N/A"
        html += '<div style="margin-top:16px;display:flex;gap:24px;align-items:center">\n'
        html += f'  <div><strong>CN 总分:</strong> <span style="font-size:24px;font-weight:700;color:#34c759">{cn_s}</span></div>\n'
        html += f'  <div><strong>EN 总分:</strong> <span style="font-size:24px;font-weight:700;color:#0071e3">{en_s}</span></div>\n'
        html += '</div>\n'

        # 评审理由
        reasoning = ed.get("comparison_reasoning", "")
        if reasoning:
            html += '<h4>评审理由</h4>\n'
            html += f'<p style="font-size:14px">{html_escape(reasoning)}</p>\n'

        html += '</div>\n</div>\n'

    return html


def generate_layer3_tab(eval_data_list: list[dict]) -> str:
    """生成第三层标签页"""
    html = '<h2>第三层: Analyzer 事后归因分析</h2>\n'
    html += '<p style="color:#86868b;margin-bottom:16px">揭盲后深度分析：为什么一方表现更好？根本原因是什么？如何改进？</p>\n'

    has_analysis = any(ed.get("analysis") for ed in eval_data_list)
    if not has_analysis:
        html += '<div class="card"><p class="no-data">暂无第三层归因分析数据</p></div>\n'
        return html

    # 汇总所有 analysis 数据
    all_strengths = []
    all_weaknesses = []
    all_suggestions = []
    cn_inst_scores = []
    en_inst_scores = []
    insights = []

    for ed in eval_data_list:
        analysis = ed.get("analysis", {})
        if not analysis:
            continue
        if "cn_instruction_score" in analysis:
            cn_inst_scores.append(analysis["cn_instruction_score"])
        if "en_instruction_score" in analysis:
            en_inst_scores.append(analysis["en_instruction_score"])
        for s in analysis.get("strengths", []):
            if isinstance(s, dict):
                all_strengths.append(s)
            elif isinstance(s, str):
                all_strengths.append({"description": s})
        for w in analysis.get("weaknesses", []):
            if isinstance(w, dict):
                all_weaknesses.append(w)
            elif isinstance(w, str):
                all_weaknesses.append({"description": w})
        for sg in analysis.get("suggestions", []):
            if isinstance(sg, dict):
                all_suggestions.append(sg)
            elif isinstance(sg, str):
                all_suggestions.append({"description": sg})
        if "insight" in analysis:
            insights.append(analysis["insight"])

    # 指令遵循度评分
    if cn_inst_scores or en_inst_scores:
        cn_avg = sum(cn_inst_scores) / len(cn_inst_scores) if cn_inst_scores else 0
        en_avg = sum(en_inst_scores) / len(en_inst_scores) if en_inst_scores else 0
        html += '<div class="card">\n<h3>指令遵循度评分</h3>\n'
        html += '<div style="display:flex;gap:48px;align-items:center;margin:16px 0">\n'
        html += f'  <div style="text-align:center"><div style="font-size:48px;font-weight:700;color:#34c759">{cn_avg:.1f}</div><div style="color:#86868b">CN Skill</div></div>\n'
        html += f'  <div style="text-align:center"><div style="font-size:48px;font-weight:700;color:#0071e3">{en_avg:.1f}</div><div style="color:#86868b">EN Skill</div></div>\n'
        html += '</div>\n</div>\n'

    # 优势
    if all_strengths:
        html += '<div class="card">\n<h3>胜出者优势归因</h3>\n'
        for s in all_strengths:
            desc = html_escape(s.get("description") or s.get("title") or str(s))
            detail = html_escape(s.get("detail") or s.get("explanation") or "")
            html += '<div class="insight-card strength-card">\n'
            html += f'<strong>{desc}</strong>\n'
            if detail:
                html += f'<p style="margin-top:4px">{detail}</p>\n'
            html += '</div>\n'
        html += '</div>\n'

    # 劣势
    if all_weaknesses:
        html += '<div class="card">\n<h3>失败方问题清单</h3>\n'
        for w in all_weaknesses:
            desc = html_escape(w.get("description") or w.get("title") or str(w))
            severity = w.get("severity", "").lower()
            detail = html_escape(w.get("detail") or w.get("explanation") or "")
            severity_badge = ""
            if severity == "critical":
                severity_badge = '<span class="priority-high">CRITICAL</span> '
            elif severity == "high":
                severity_badge = '<span class="priority-high">HIGH</span> '
            elif severity == "medium":
                severity_badge = '<span class="priority-medium">MEDIUM</span> '
            elif severity == "low":
                severity_badge = '<span class="priority-low">LOW</span> '
            html += '<div class="insight-card weakness-card">\n'
            html += f'{severity_badge}<strong>{desc}</strong>\n'
            if detail:
                html += f'<p style="margin-top:4px">{detail}</p>\n'
            html += '</div>\n'
        html += '</div>\n'

    # 改进建议
    if all_suggestions:
        html += '<div class="card">\n<h3>改进建议</h3>\n'
        for sg in all_suggestions:
            desc = html_escape(sg.get("description") or sg.get("title") or str(sg))
            priority = sg.get("priority", "").lower()
            detail = html_escape(sg.get("detail") or sg.get("explanation") or sg.get("impact") or "")
            priority_badge = ""
            if priority == "high":
                priority_badge = '<span class="priority-high">HIGH</span> '
            elif priority == "medium":
                priority_badge = '<span class="priority-medium">MEDIUM</span> '
            elif priority == "low":
                priority_badge = '<span class="priority-low">LOW</span> '
            html += '<div class="insight-card suggestion-card">\n'
            html += f'{priority_badge}<strong>{desc}</strong>\n'
            if detail:
                html += f'<p style="margin-top:4px">{detail}</p>\n'
            html += '</div>\n'
        html += '</div>\n'

    # 核心洞察
    if insights:
        html += '<div class="card">\n<h3>核心洞察</h3>\n'
        for ins in insights:
            html += '<div class="insight-card">\n'
            html += f'<p>{html_escape(ins)}</p>\n'
            html += '</div>\n'
        html += '</div>\n'

    return html


def generate_report(iteration_dir: str, output_path: str, skill_name: str) -> None:
    """生成完整的 HTML 评测报告"""
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

    # 收集所有 eval 数据
    eval_data_list = []
    for eval_dir in eval_dirs:
        metadata = read_json(os.path.join(eval_dir, "eval_metadata.json"))
        cn_grading = read_json(os.path.join(eval_dir, "cn_skill", "grading.json"))
        en_grading = read_json(os.path.join(eval_dir, "en_skill", "grading.json"))
        comparison = read_json(os.path.join(eval_dir, "comparison.json"))
        analysis_raw = read_json(os.path.join(eval_dir, "analysis.json"))

        label = get_eval_label(eval_dir, metadata)
        cn_score, en_score = extract_comparison_scores(comparison, eval_dir)
        winner = extract_winner(comparison, eval_dir)

        eval_data_list.append({
            "dir": eval_dir,
            "label": label,
            "metadata": metadata,
            "cn_grading": cn_grading,
            "en_grading": en_grading,
            "cn_pass_rate": extract_pass_rate(cn_grading),
            "en_pass_rate": extract_pass_rate(en_grading),
            "cn_grading_items": extract_grading_items(cn_grading),
            "en_grading_items": extract_grading_items(en_grading),
            "cn_passed_total": extract_passed_total(cn_grading),
            "en_passed_total": extract_passed_total(en_grading),
            "cn_score": cn_score,
            "en_score": en_score,
            "winner": winner,
            "comparison_dimensions": extract_comparison_dimensions(comparison),
            "comparison_reasoning": extract_comparison_reasoning(comparison),
            "ab_mapping_str": extract_ab_mapping_str(comparison, eval_dir),
            "analysis": extract_analysis_data(analysis_raw),
        })

    # 组装 HTML
    today = date.today().isoformat()
    title = f"{html_escape(skill_name)} 三层评测报告"

    html_parts = [
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n',
        '<meta charset="UTF-8">\n',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n',
        f'<title>{title}</title>\n',
        f'<style>\n{generate_css()}\n</style>\n',
        '</head>\n<body>\n<div class="container">\n',
        f'<h1>{title}</h1>\n',
        f'<p class="subtitle">中文翻译版 (CN) vs 英文原版 (EN) | {today}</p>\n\n',
        # 标签导航
        '<div class="tabs">\n',
        '  <div class="tab active" onclick="switchTab(\'overview\')">总览</div>\n',
        '  <div class="tab" onclick="switchTab(\'layer1\')">第一层: 逐断言评分</div>\n',
        '  <div class="tab" onclick="switchTab(\'layer2\')">第二层: 盲评对比</div>\n',
        '  <div class="tab" onclick="switchTab(\'layer3\')">第三层: 归因分析</div>\n',
        '</div>\n\n',
        # 总览
        '<div id="overview" class="tab-content active">\n',
        generate_overview_tab(eval_data_list),
        '</div>\n\n',
        # 第一层
        '<div id="layer1" class="tab-content">\n',
        generate_layer1_tab(eval_data_list),
        '</div>\n\n',
        # 第二层
        '<div id="layer2" class="tab-content">\n',
        generate_layer2_tab(eval_data_list),
        '</div>\n\n',
        # 第三层
        '<div id="layer3" class="tab-content">\n',
        generate_layer3_tab(eval_data_list),
        '</div>\n\n',
        '</div>\n\n',
        f'<script>\n{generate_js(len(eval_dirs))}\n</script>\n',
        '</body>\n</html>\n',
    ]

    html_content = "".join(html_parts)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"报告已生成: {output_path}", file=sys.stderr)
    except OSError as e:
        print(f"错误: 写入文件失败 - {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="生成三层评测报告 HTML")
    parser.add_argument("iteration_dir", help="iteration 目录路径 (如 /path/to/workspace/iteration-0/)")
    parser.add_argument("--output", "-o", default="report.html", help="输出 HTML 文件路径 (默认: report.html)")
    parser.add_argument("--skill-name", default="Skill", help="Skill 名称，用于报告标题")
    args = parser.parse_args()

    generate_report(args.iteration_dir, args.output, args.skill_name)


if __name__ == "__main__":
    main()
