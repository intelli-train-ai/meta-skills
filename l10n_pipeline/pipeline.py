#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流水线各阶段实现
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from .detect_language import detect_language
from .check_pass import check_pass
from .generate_report import generate_report
from .utils import read_json


# ─── Phase 1: 发现 ────────────────────────────────────────────────────────────


def discover_skills(skills_dir: str) -> list[dict]:
    """扫描目录下所有包含 SKILL.md 的子目录，返回 skill 信息列表"""
    skills_dir = os.path.abspath(skills_dir)
    results = []

    for name in sorted(os.listdir(skills_dir)):
        skill_md = os.path.join(skills_dir, name, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue

        lang_info = detect_language(skill_md)
        frontmatter = _extract_frontmatter(skill_md)

        results.append({
            "name": frontmatter.get("name", name),
            "path": os.path.join(skills_dir, name),
            "language": lang_info["language"],
            "is_chinese": lang_info["is_chinese"],
            "chinese_ratio": lang_info["chinese_ratio"],
            "description": frontmatter.get("description", ""),
        })

    return results


def _extract_frontmatter(skill_md_path: str) -> dict:
    """从 SKILL.md 提取 YAML frontmatter 的 name 和 description"""
    try:
        with open(skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return {}

    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}

    fm = match.group(1)
    result = {}
    for field in ("name", "description"):
        m = re.search(rf'^{field}:\s*"?(.+?)"?\s*$', fm, re.MULTILINE)
        if m:
            result[field] = m.group(1).strip().strip('"')
    return result


def cmd_discover(args):
    """discover 子命令"""
    skills = discover_skills(args.skills_dir)

    if args.json:
        print(json.dumps(skills, ensure_ascii=False, indent=2))
        return

    if not skills:
        print("未找到任何 skill")
        return

    # 分类输出
    need_translate = [s for s in skills if not s["is_chinese"]]
    already_chinese = [s for s in skills if s["is_chinese"]]

    print(f"共发现 {len(skills)} 个 skill:\n")

    if need_translate:
        print(f"  需翻译 ({len(need_translate)}):")
        for s in need_translate:
            print(f"    - {s['name']} [{s['language']}] {s['path']}")

    if already_chinese:
        print(f"\n  已是中文 ({len(already_chinese)}):")
        for s in already_chinese:
            print(f"    - {s['name']} {s['path']}")


# ─── Phase 3: 翻译 ────────────────────────────────────────────────────────────


def translate_skill(skill_path: str, output_path: str, model: str = "claude-sonnet-4-20250514") -> bool:
    """
    调用 claude CLI 翻译一个 skill 到中文。
    返回 True 表示成功。
    """
    skill_path = os.path.abspath(skill_path)
    output_path = os.path.abspath(output_path)

    # 复制整个 skill 目录结构
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    shutil.copytree(skill_path, output_path)

    # 找到所有需要翻译的 .md 文件
    md_files = list(Path(output_path).rglob("*.md"))

    for md_file in md_files:
        _translate_file(str(md_file), model)

    # 验证翻译结果
    skill_md = os.path.join(output_path, "SKILL.md")
    if not os.path.isfile(skill_md):
        print(f"错误: 翻译后 SKILL.md 不存在", file=sys.stderr)
        return False

    lang = detect_language(skill_md)
    if not lang["is_chinese"]:
        print(f"警告: 翻译后仍检测为非中文 (chinese_ratio={lang['chinese_ratio']})", file=sys.stderr)

    return True


def _translate_file(file_path: str, model: str):
    """调用 claude CLI 翻译单个 .md 文件"""
    prompt = (
        f"请将以下文件翻译为中文。要求:\n"
        f"1. 保留所有代码块、命令、XML/JSON 示例不变\n"
        f"2. 保留 YAML frontmatter 结构，翻译 description 字段\n"
        f"3. 保留技术术语原文（如 pandoc, docx-js, reportlab 等）\n"
        f"4. 只翻译英文说明文本\n"
        f"5. 直接输出翻译后的完整文件内容，不要加任何额外说明\n\n"
        f"文件路径: {file_path}\n"
        f"请读取该文件并输出翻译后的完整内容。"
    )

    try:
        result = subprocess.run(
            ["claude", "--model", model, "--print", "--no-input", "-p", prompt],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0 and result.stdout.strip():
            translated = result.stdout.strip()
            # 去除 claude 可能添加的 markdown 代码块包装
            if translated.startswith("```") and translated.endswith("```"):
                lines = translated.split("\n")
                translated = "\n".join(lines[1:-1])
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(translated)
            print(f"  翻译完成: {os.path.basename(file_path)}", file=sys.stderr)
        else:
            print(f"  翻译失败: {os.path.basename(file_path)} - {result.stderr[:200]}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"  翻译超时: {os.path.basename(file_path)}", file=sys.stderr)
    except FileNotFoundError:
        print("错误: 未找到 claude CLI，请确认已安装 Claude Code", file=sys.stderr)
        sys.exit(1)


def cmd_translate(args):
    """translate 子命令"""
    print(f"翻译 skill: {args.skill_path} → {args.output}")
    success = translate_skill(args.skill_path, args.output, args.model)
    if success:
        print(f"翻译完成: {args.output}")
    else:
        print("翻译失败", file=sys.stderr)
        sys.exit(1)


# ─── Phase 4-5: 评测 ──────────────────────────────────────────────────────────


def generate_test_prompts(cn_skill_path: str, en_skill_path: str,
                          num_prompts: int = 3, model: str = "claude-sonnet-4-20250514") -> dict:
    """调用 claude CLI 生成测试 prompt"""
    prompt = (
        f"你是一个测试用例生成器。请为以下翻译后的中文 skill 生成 {num_prompts} 个中文测试 prompt。\n\n"
        f"阅读以下两个文件:\n"
        f"- 中文版: {cn_skill_path}/SKILL.md\n"
        f"- 英文原版: {en_skill_path}/SKILL.md\n\n"
        f"要求:\n"
        f"1. 测试 prompt 用口语化中文，像真实用户会说的话\n"
        f"2. 包含具体的文件路径、中文公司名、中文人名等细节\n"
        f"3. 每个 prompt 附带 atomic_requirements（可验证的原子需求列表）\n"
        f"4. 每个 prompt 必须包含语言质量断言\n\n"
        f"输出严格 JSON 格式，不要加任何其他文字:\n"
        f'{{"skill_name": "xxx", "data_source": "ai_generated", "evals": ['
        f'{{"id": 0, "prompt": "...", "expected_output": "...", "atomic_requirements": ["...", "..."]}}'
        f']}}'
    )

    try:
        result = subprocess.run(
            ["claude", "--model", model, "--print", "--no-input", "-p", prompt],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode == 0:
            # 提取 JSON
            output = result.stdout.strip()
            # 尝试找到 JSON 部分
            json_match = re.search(r'\{[\s\S]*\}', output)
            if json_match:
                return json.loads(json_match.group())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"生成测试 prompt 失败: {e}", file=sys.stderr)

    return None


def run_evaluation(en_skill: str, cn_skill: str, workspace: str,
                   evals_data: dict, model: str = "claude-sonnet-4-20250514") -> bool:
    """执行三层评测"""
    os.makedirs(workspace, exist_ok=True)
    os.makedirs(os.path.join(workspace, "en_skill", "outputs"), exist_ok=True)
    os.makedirs(os.path.join(workspace, "cn_skill", "outputs"), exist_ok=True)

    evals_path = os.path.join(workspace, "evals.json")
    with open(evals_path, "w", encoding="utf-8") as f:
        json.dump(evals_data, ensure_ascii=False, indent=2, fp=f)

    # 对每个 eval，分别用英文和中文 skill 执行
    for eval_item in evals_data.get("evals", []):
        eval_id = eval_item["id"]
        eval_prompt = eval_item["prompt"]
        requirements = eval_item.get("atomic_requirements", [])

        print(f"\n  评测 {eval_id}: {eval_prompt[:50]}...", file=sys.stderr)

        # 英文版执行
        en_output_dir = os.path.join(workspace, "en_skill", "outputs", f"eval_{eval_id}")
        os.makedirs(en_output_dir, exist_ok=True)
        _run_skill_agent(en_skill, eval_prompt, en_output_dir, model)

        # 中文版执行
        cn_output_dir = os.path.join(workspace, "cn_skill", "outputs", f"eval_{eval_id}")
        os.makedirs(cn_output_dir, exist_ok=True)
        _run_skill_agent(cn_skill, eval_prompt, cn_output_dir, model)

        # Layer 1: Grader — 逐条评分
        _run_grader(workspace, eval_id, en_output_dir, cn_output_dir, requirements, eval_prompt, model)

        # Layer 2: Comparator — 盲评
        _run_comparator(workspace, eval_id, en_output_dir, cn_output_dir, eval_prompt, requirements, model)

    # Layer 3: Analyzer — 归因分析
    _run_analyzer(workspace, en_skill, cn_skill, evals_data, model)

    return True


def _run_skill_agent(skill_path: str, prompt: str, output_dir: str, model: str):
    """用指定 skill 执行一个 prompt"""
    full_prompt = (
        f"先阅读 {skill_path}/SKILL.md 中的指令，然后执行以下任务。"
        f"所有输出文件保存到 {output_dir}/\n\n{prompt}"
    )
    try:
        subprocess.run(
            ["claude", "--model", model, "--print", "--no-input", "-p", full_prompt],
            capture_output=True, text=True, timeout=300
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def _run_grader(workspace: str, eval_id: int, en_output_dir: str, cn_output_dir: str,
                requirements: list, prompt: str, model: str):
    """Layer 1: 对每个版本逐条评分"""
    for version, output_dir in [("en", en_output_dir), ("cn", cn_output_dir)]:
        grader_prompt = (
            f"你是一个评分器。请检查 {output_dir}/ 目录中的输出文件，"
            f"对照以下原子需求逐条判定 passed/failed，给出证据。\n\n"
            f"原始任务: {prompt}\n\n"
            f"原子需求:\n" + "\n".join(f"- {r}" for r in requirements) + "\n\n"
            f"输出严格 JSON 格式到标准输出:\n"
            f'{{"expectations": [{{"text": "...", "passed": true, "evidence": "..."}}], '
            f'"summary": {{"passed": N, "failed": N, "total": N, "pass_rate": 0.XX}}}}'
        )
        try:
            result = subprocess.run(
                ["claude", "--model", model, "--print", "--no-input", "-p", grader_prompt],
                capture_output=True, text=True, timeout=180
            )
            if result.returncode == 0:
                json_match = re.search(r'\{[\s\S]*\}', result.stdout)
                if json_match:
                    grading = json.loads(json_match.group())
                    grading_path = os.path.join(workspace, f"{version}_skill", f"grading_eval_{eval_id}.json")
                    with open(grading_path, "w", encoding="utf-8") as f:
                        json.dump(grading, ensure_ascii=False, indent=2, fp=f)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass


def _run_comparator(workspace: str, eval_id: int, en_output_dir: str, cn_output_dir: str,
                    prompt: str, requirements: list, model: str):
    """Layer 2: 盲评对比"""
    import random
    if random.random() < 0.5:
        a_version, b_version = "en", "cn"
        a_dir, b_dir = en_output_dir, cn_output_dir
    else:
        a_version, b_version = "cn", "en"
        a_dir, b_dir = cn_output_dir, en_output_dir

    # 保存 A/B 分配
    ab_path = os.path.join(workspace, "ab_assignments.json")
    ab_data = read_json(ab_path) or []
    if not isinstance(ab_data, list):
        ab_data = [ab_data]
    ab_data.append({"eval_id": eval_id, "A": a_version, "B": b_version})
    with open(ab_path, "w", encoding="utf-8") as f:
        json.dump(ab_data, ensure_ascii=False, indent=2, fp=f)

    comparator_prompt = (
        f"你是一个盲评对比器。请比较 A 和 B 两组输出的质量。\n"
        f"A 的输出目录: {a_dir}/\n"
        f"B 的输出目录: {b_dir}/\n"
        f"原始任务: {prompt}\n\n"
        f"按 6 维度（correctness, completeness, accuracy, organization, formatting, usability）"
        f"各打 1-5 分，计算总分。\n\n"
        f"输出严格 JSON 格式到标准输出:\n"
        f'{{"winner": "A"/"B"/"TIE", "reasoning": "...", '
        f'"rubric": {{"A": {{"content": {{"correctness": N, "completeness": N, "accuracy": N}}, '
        f'"structure": {{"organization": N, "formatting": N, "usability": N}}, '
        f'"content_score": N.N, "structure_score": N.N, "overall_score": N.N}}, '
        f'"B": {{...}}}}, '
        f'"output_quality": {{"A": {{"score": N.N}}, "B": {{"score": N.N}}}}}}'
    )
    try:
        result = subprocess.run(
            ["claude", "--model", model, "--print", "--no-input", "-p", comparator_prompt],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode == 0:
            json_match = re.search(r'\{[\s\S]*\}', result.stdout)
            if json_match:
                comparison = json.loads(json_match.group())
                comparison["eval_id"] = eval_id
                comp_path = os.path.join(workspace, f"comparison_eval_{eval_id}.json")
                with open(comp_path, "w", encoding="utf-8") as f:
                    json.dump(comparison, ensure_ascii=False, indent=2, fp=f)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass


def _run_analyzer(workspace: str, en_skill: str, cn_skill: str, evals_data: dict, model: str):
    """Layer 3: 归因分析"""
    analyzer_prompt = (
        f"你是评测归因分析器。请分析以下评测结果:\n\n"
        f"工作目录: {workspace}/\n"
        f"英文 skill: {en_skill}/SKILL.md\n"
        f"中文 skill: {cn_skill}/SKILL.md\n\n"
        f"请:\n"
        f"1. 读取 ab_assignments.json 揭盲\n"
        f"2. 读取所有 grading_eval_*.json 和 comparison_eval_*.json\n"
        f"3. 对比两版 SKILL.md 的指令差异\n"
        f"4. 输出 analysis.json 到 {workspace}/\n\n"
        f"analysis.json 格式:\n"
        f'{{"comparison_summary": {{"overall_winner": "cn_skill"/"en_skill", "cn_wins": N, "en_wins": N, "ties": N}}, '
        f'"instruction_following": {{"cn_skill": {{"score": N, "issues": [...]}}, "en_skill": {{...}}}}, '
        f'"winner_strengths": [...], "loser_weaknesses": [...], "improvement_suggestions": [...]}}'
    )
    try:
        subprocess.run(
            ["claude", "--model", model, "--print", "--no-input", "-p", analyzer_prompt],
            capture_output=True, text=True, timeout=300
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def cmd_evaluate(args):
    """evaluate 子命令"""
    num_prompts = 1 if args.fast else args.num_prompts
    model = getattr(args, "model", "claude-sonnet-4-20250514")

    print(f"生成 {num_prompts} 个测试 prompt...", file=sys.stderr)
    evals_data = generate_test_prompts(args.cn_skill, args.en_skill, num_prompts, model)
    if not evals_data:
        print("错误: 无法生成测试 prompt", file=sys.stderr)
        sys.exit(1)

    print(f"开始三层评测...", file=sys.stderr)
    run_evaluation(args.en_skill, args.cn_skill, args.workspace, evals_data, model)

    print(f"\n评测完成，结果在: {args.workspace}", file=sys.stderr)


# ─── Phase 6: 检查 ────────────────────────────────────────────────────────────


def cmd_check(args):
    """check 子命令"""
    result = check_pass(args.workspace)
    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))


# ─── 报告 ─────────────────────────────────────────────────────────────────────


def cmd_report(args):
    """report 子命令"""
    generate_report(args.workspace, args.output, args.skill_name)


# ─── Phase 7: 发布 ────────────────────────────────────────────────────────────


def publish_skill(skill_path: str, output_dir: str,
                  eval_report: str = None, translated: bool = False) -> dict:
    """打包 skill 并生成元数据"""
    skill_path = os.path.abspath(skill_path)
    output_dir = os.path.expanduser(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # 验证 SKILL.md 存在
    skill_md = os.path.join(skill_path, "SKILL.md")
    if not os.path.isfile(skill_md):
        raise FileNotFoundError(f"SKILL.md 不存在: {skill_md}")

    frontmatter = _extract_frontmatter(skill_md)
    skill_name = frontmatter.get("name", os.path.basename(skill_path))

    # 如果有评测报告，复制到 skill 目录
    if eval_report and os.path.isfile(eval_report):
        shutil.copy2(eval_report, os.path.join(skill_path, "eval_report.html"))

    # 打包
    tar_name = f"{skill_name}.tar.gz"
    tar_path = os.path.join(output_dir, tar_name)
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(skill_path, arcname=os.path.basename(skill_path))

    # 生成元数据
    file_count = sum(1 for _ in Path(skill_path).rglob("*") if _.is_file())
    info = {
        "name": skill_name,
        "description": frontmatter.get("description", ""),
        "language": "zh",
        "source_language": "en" if translated else "zh",
        "file_count": file_count,
        "has_scripts": os.path.isdir(os.path.join(skill_path, "scripts")),
        "has_eval_report": eval_report is not None and os.path.isfile(eval_report),
        "translated": translated,
        "package_file": tar_name,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }

    info_path = os.path.join(output_dir, f"{skill_name}_info.json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, ensure_ascii=False, indent=2, fp=f)

    return info


def _update_manifest(output_dir: str, info: dict):
    """更新 manifest.json"""
    manifest_path = os.path.join(output_dir, "manifest.json")
    manifest = read_json(manifest_path) or {"generated_at": "", "skills": []}

    # 去重
    manifest["skills"] = [s for s in manifest["skills"] if s.get("name") != info["name"]]
    manifest["skills"].append({
        "name": info["name"],
        "language": info["language"],
        "translated": info["translated"],
        "package": info["package_file"],
    })
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, ensure_ascii=False, indent=2, fp=f)


def cmd_publish(args):
    """publish 子命令"""
    output_dir = os.path.expanduser(args.output_dir)
    info = publish_skill(args.skill_path, output_dir, args.eval_report, args.translated)
    _update_manifest(output_dir, info)
    print(f"已发布: {info['package_file']} → {output_dir}")


# ─── 全流程 ───────────────────────────────────────────────────────────────────


def cmd_run(args):
    """run 子命令 — 全流程"""
    output_dir = os.path.expanduser(args.output_dir)
    workspace = os.path.abspath(args.workspace)
    os.makedirs(workspace, exist_ok=True)

    # Phase 1: 发现
    print("=" * 60)
    print("Phase 1: 发现 skill")
    print("=" * 60)
    skills = discover_skills(args.skills_dir)

    if not skills:
        print("未找到任何 skill，退出")
        return

    # 过滤指定的 skill
    if args.skills:
        skills = [s for s in skills if s["name"] in args.skills]

    # Phase 2: 语言分流
    print("\n" + "=" * 60)
    print("Phase 2: 语言检测与分流")
    print("=" * 60)
    need_translate = [s for s in skills if not s["is_chinese"]]
    already_chinese = [s for s in skills if s["is_chinese"]]

    if need_translate:
        print(f"\n  需翻译 ({len(need_translate)}):")
        for s in need_translate:
            print(f"    - {s['name']} [{s['language']}]")
    if already_chinese:
        print(f"\n  已是中文 ({len(already_chinese)}):")
        for s in already_chinese:
            print(f"    - {s['name']}")

    # 处理需翻译的 skill
    for skill_info in need_translate:
        name = skill_info["name"]
        en_path = skill_info["path"]
        cn_path = os.path.join(workspace, f"{name}-zh")
        eval_workspace = os.path.join(workspace, f"{name}-eval")

        # Phase 3: 翻译
        print(f"\n{'=' * 60}")
        print(f"Phase 3: 翻译 {name}")
        print("=" * 60)
        success = translate_skill(en_path, cn_path, args.model)
        if not success:
            print(f"  跳过 {name}: 翻译失败")
            continue

        # Phase 4-5: 评测（带迭代）
        num_prompts = 1 if args.fast else 3
        passed = False

        for iteration in range(args.max_iterations):
            print(f"\n{'=' * 60}")
            print(f"Phase 4-5: 评测 {name} (迭代 {iteration + 1}/{args.max_iterations})")
            print("=" * 60)

            iter_workspace = os.path.join(eval_workspace, f"iteration-{iteration}")

            # 生成测试 prompt
            evals_data = generate_test_prompts(cn_path, en_path, num_prompts, args.model)
            if not evals_data:
                print("  无法生成测试 prompt，跳过")
                break

            # 执行评测
            run_evaluation(en_path, cn_path, iter_workspace, evals_data, args.model)

            # Phase 6: 检查
            print(f"\n{'=' * 60}")
            print(f"Phase 6: 判定 {name}")
            print("=" * 60)
            result = check_pass(iter_workspace)
            print(f"  结果: {result['summary']}")
            for c in result["criteria"]:
                status = "PASS" if c["met"] else "FAIL"
                print(f"    [{status}] {c['name']}: {c['detail']}")

            if result["passed"]:
                passed = True
                # 生成报告
                report_path = os.path.join(iter_workspace, "report.html")
                generate_report(iter_workspace, report_path, name)
                break
            elif args.fast:
                print("  快速模式，跳过迭代")
                break

        # Phase 7: 发布
        print(f"\n{'=' * 60}")
        print(f"Phase 7: 发布 {name}")
        print("=" * 60)

        report_file = None
        if passed:
            report_file = os.path.join(eval_workspace, f"iteration-{iteration}", "report.html")

        info = publish_skill(cn_path, output_dir, report_file, translated=True)
        _update_manifest(output_dir, info)
        status = "PASS" if passed else "WARN (未通过评测但仍发布)"
        print(f"  [{status}] {info['package_file']}")

    # 处理已是中文的 skill（直接发布）
    for skill_info in already_chinese:
        name = skill_info["name"]
        print(f"\n  直接发布中文 skill: {name}")
        info = publish_skill(skill_info["path"], output_dir, translated=False)
        _update_manifest(output_dir, info)
        print(f"  已发布: {info['package_file']}")

    # 汇总
    print(f"\n{'=' * 60}")
    print("完成!")
    print("=" * 60)
    print(f"输出目录: {output_dir}")
