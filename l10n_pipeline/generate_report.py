#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三层评测报告 HTML 生成脚本

用法: python generate_report.py /path/to/workspace/ --output report.html --skill-name "xxx"
"""

import argparse
import json
import os
import sys
from datetime import date

try:
    from .utils import read_json, discover_eval_ids, extract_pass_rate, extract_comparison_scores
except ImportError:
    from utils import read_json, discover_eval_ids, extract_pass_rate, extract_comparison_scores


def extract_grading_items(grading_data: dict) -> list[dict]:
    """从 grading_eval_*.json 提取逐条断言结果（仅规范格式）"""
    if not grading_data:
        return []

    expectations = grading_data.get("expectations", [])
    if not isinstance(expectations, list):
        return []

    items = []
    for item in expectations:
        if not isinstance(item, dict):
            continue
        items.append({
            "description": item.get("text", str(item)),
            "passed": bool(item.get("passed")),
            "evidence": item.get("evidence", ""),
        })
    return items


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

    return 0, 0


def extract_comparison_dimensions(comparison_data: dict) -> list[dict]:
    """从 comparison_eval_*.json 提取 rubric 维度详情（规范格式）"""
    if not comparison_data:
        return []

    rubric = comparison_data.get("rubric", {})
    if not isinstance(rubric, dict):
        return []

    a_rubric = rubric.get("A", {})
    b_rubric = rubric.get("B", {})
    if not isinstance(a_rubric, dict) or not isinstance(b_rubric, dict):
        return []

    result = []
    for group_key in ("content", "structure"):
        a_group = a_rubric.get(group_key, {})
        b_group = b_rubric.get(group_key, {})
        if isinstance(a_group, dict) and isinstance(b_group, dict):
            for dim_key in a_group:
                a_val = a_group.get(dim_key)
                b_val = b_group.get(dim_key)
                if isinstance(a_val, (int, float)) and isinstance(b_val, (int, float)):
                    result.append({
                        "name": dim_key,
                        "a_score": float(a_val),
                        "b_score": float(b_val),
                    })
    return result


def extract_comparison_reasoning(comparison_data: dict) -> str:
    """提取盲评理由"""
    if not comparison_data:
        return ""
    return comparison_data.get("reasoning", "")


def extract_winner(comparison_data: dict, workspace: str) -> str:
    """提取胜出方，返回 'cn', 'en', 或 'tie'"""
    if not comparison_data:
        return "unknown"

    winner = comparison_data.get("winner", "")
    winner_upper = str(winner).upper()

    # winner 是 A/B，需要映射
    if winner_upper in ("A", "B"):
        ab_data = read_json(os.path.join(workspace, "ab_assignments.json"))
        if ab_data:
            from utils import _parse_ab_assignments
            ab_map = _parse_ab_assignments(ab_data, comparison_data.get("eval_id"))
            mapped = ab_map.get(winner_upper, "")
            if mapped == "cn":
                return "cn"
            elif mapped == "en":
                return "en"
        # 无法映射，根据分数判断
        cn_score, en_score = extract_comparison_scores(comparison_data, workspace)
        if cn_score is not None and en_score is not None:
            if cn_score > en_score:
                return "cn"
            elif en_score > cn_score:
                return "en"
            else:
                return "tie"
        return "unknown"

    winner_lower = str(winner).lower()
    if "tie" in winner_lower or "draw" in winner_lower:
        return "tie"

    return "unknown"


def extract_ab_mapping_str(workspace: str, eval_id=None) -> str:
    """获取 A/B 映射的简短描述"""
    ab_data = read_json(os.path.join(workspace, "ab_assignments.json"))
    if not ab_data:
        return ""

    from utils import _parse_ab_assignments
    ab_map = _parse_ab_assignments(ab_data, eval_id)
    if ab_map:
        parts = []
        for key in sorted(ab_map.keys()):
            parts.append(f"{key}={ab_map[key]}")
        return ", ".join(parts)
    return ""


def extract_analysis_data(analysis_data: dict) -> dict:
    """提取第三层归因分析数据（规范格式）"""
    if not analysis_data:
        return {}

    result = {}

    # 指令遵循度评分
    inst = analysis_data.get("instruction_following", {})
    if isinstance(inst, dict):
        cn_inst = inst.get("cn_skill", {})
        en_inst = inst.get("en_skill", {})
        if isinstance(cn_inst, dict) and "score" in cn_inst:
            result["cn_instruction_score"] = float(cn_inst["score"])
        if isinstance(en_inst, dict) and "score" in en_inst:
            result["en_instruction_score"] = float(en_inst["score"])

    # 胜出者优势
    strengths = analysis_data.get("winner_strengths", [])
    if isinstance(strengths, list):
        result["strengths"] = strengths

    # 失败方劣势
    weaknesses = analysis_data.get("loser_weaknesses", [])
    if isinstance(weaknesses, list):
        result["weaknesses"] = weaknesses

    # 改进建议
    suggestions = analysis_data.get("improvement_suggestions", [])
    if isinstance(suggestions, list):
        result["suggestions"] = suggestions

    # comparison_summary 作为 insight
    cs = analysis_data.get("comparison_summary", {})
    if isinstance(cs, dict):
        winner = cs.get("overall_winner", "")
        cn_w = cs.get("cn_wins", 0)
        en_w = cs.get("en_wins", 0)
        ties = cs.get("ties", 0)
        result["insight"] = f"总体胜出: {winner} (CN {cn_w} 胜, EN {en_w} 胜, {ties} 平局)"
    elif isinstance(cs, str) and cs:
        result["insight"] = cs

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


def get_eval_label(eval_id: int, metadata: dict | None) -> str:
    """获取 eval 的显示标签"""
    if metadata:
        prompt = metadata.get("prompt", "") or metadata.get("description", "")
        if prompt:
            short = prompt[:20].strip()
            if len(prompt) > 20:
                short += "..."
            return f"Eval {eval_id}: {short}"
    return f"Eval {eval_id}"


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
            if isinstance(sg, dict):
                desc = html_escape(sg.get("suggestion") or sg.get("description") or sg.get("title") or str(sg))
                priority = sg.get("priority", "").lower()
                detail = html_escape(sg.get("expected_impact") or sg.get("detail") or sg.get("explanation") or "")
            else:
                desc = html_escape(str(sg))
                priority = ""
                detail = ""
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


def generate_report(workspace: str, output_path: str, skill_name: str) -> None:
    """生成完整的 HTML 评测报告"""
    if not os.path.isdir(workspace):
        print(f"错误: 目录不存在 - {workspace}", file=sys.stderr)
        sys.exit(1)

    # 发现所有 eval ID
    eval_ids = discover_eval_ids(workspace)

    if not eval_ids:
        print(f"错误: 未找到 eval 数据文件 - {workspace}", file=sys.stderr)
        sys.exit(1)

    # 读取 analysis.json (single file, not per-eval)
    analysis_raw = read_json(os.path.join(workspace, "analysis.json"))

    # 收集所有 eval 数据
    eval_data_list = []
    for eid in eval_ids:
        cn_grading = read_json(os.path.join(workspace, "cn_skill", f"grading_eval_{eid}.json"))
        en_grading = read_json(os.path.join(workspace, "en_skill", f"grading_eval_{eid}.json"))
        comparison = read_json(os.path.join(workspace, f"comparison_eval_{eid}.json"))

        label = get_eval_label(eid, None)
        cn_score, en_score = extract_comparison_scores(comparison, workspace)
        winner = extract_winner(comparison, workspace)

        eval_data_list.append({
            "eval_id": eid,
            "label": label,
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
            "ab_mapping_str": extract_ab_mapping_str(workspace, eid),
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
        f'<script>\n{generate_js(len(eval_ids))}\n</script>\n',
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
    parser.add_argument("workspace", help="workspace 目录路径 (如 /path/to/workspace/)")
    parser.add_argument("--output", "-o", default="report.html", help="输出 HTML 文件路径 (默认: report.html)")
    parser.add_argument("--skill-name", default="Skill", help="Skill 名称，用于报告标题")
    args = parser.parse_args()

    generate_report(args.workspace, args.output, args.skill_name)


if __name__ == "__main__":
    main()
