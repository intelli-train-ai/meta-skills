#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skill 本地化流水线 CLI 入口

用法:
    python -m l10n_pipeline discover /path/to/skills/
    python -m l10n_pipeline translate /path/to/skill/ --output /path/to/output/
    python -m l10n_pipeline evaluate /path/to/en_skill/ /path/to/cn_skill/ --workspace /tmp/eval/
    python -m l10n_pipeline check /path/to/workspace/
    python -m l10n_pipeline report /path/to/workspace/ --output report.html
    python -m l10n_pipeline publish /path/to/cn_skill/ --output-dir ~/l10n-output/
    python -m l10n_pipeline run /path/to/skills/ --output-dir ~/l10n-output/   # 全流程
"""

import argparse
import sys

from . import __version__
from .pipeline import (
    cmd_check,
    cmd_discover,
    cmd_evaluate,
    cmd_publish,
    cmd_report,
    cmd_run,
    cmd_translate,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="l10n_pipeline",
        description="Skill 本地化全自动流水线 — 发现、翻译、评测、发布",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # discover
    p_discover = subparsers.add_parser("discover", help="扫描目录，列出所有 skill 及其语言")
    p_discover.add_argument("skills_dir", help="包含 skill 子目录的根目录")
    p_discover.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    # translate
    p_translate = subparsers.add_parser("translate", help="将英文 skill 翻译为中文")
    p_translate.add_argument("skill_path", help="英文 skill 目录路径")
    p_translate.add_argument("--output", "-o", required=True, help="中文版输出目录")
    p_translate.add_argument("--model", default="claude-sonnet-4-20250514", help="翻译使用的模型")

    # evaluate
    p_eval = subparsers.add_parser("evaluate", help="三层评测：对比英文原版和中文翻译版")
    p_eval.add_argument("en_skill", help="英文原版 skill 目录")
    p_eval.add_argument("cn_skill", help="中文翻译版 skill 目录")
    p_eval.add_argument("--workspace", "-w", required=True, help="评测工作目录")
    p_eval.add_argument("--num-prompts", type=int, default=3, help="测试 prompt 数量 (默认 3)")
    p_eval.add_argument("--fast", action="store_true", help="快速模式: 1 个 prompt，跳过盲评")

    # check
    p_check = subparsers.add_parser("check", help="检查评测结果是否通过标准")
    p_check.add_argument("workspace", help="评测工作目录")
    p_check.add_argument("--pretty", action="store_true", help="格式化 JSON 输出")

    # report
    p_report = subparsers.add_parser("report", help="生成三层评测 HTML 报告")
    p_report.add_argument("workspace", help="评测工作目录")
    p_report.add_argument("--output", "-o", default="report.html", help="输出 HTML 路径")
    p_report.add_argument("--skill-name", default="Skill", help="报告标题中的 skill 名称")

    # publish
    p_publish = subparsers.add_parser("publish", help="打包 skill 为 .tar.gz 并生成元数据")
    p_publish.add_argument("skill_path", help="skill 目录路径")
    p_publish.add_argument("--output-dir", default="~/l10n-output", help="输出目录")
    p_publish.add_argument("--eval-report", help="评测报告路径（可选）")
    p_publish.add_argument("--translated", action="store_true", help="标记为翻译过的 skill")

    # run (全流程)
    p_run = subparsers.add_parser("run", help="全流程: 发现 → 翻译 → 评测 → 发布")
    p_run.add_argument("skills_dir", help="包含 skill 子目录的根目录")
    p_run.add_argument("--output-dir", default="~/l10n-output", help="最终输出目录")
    p_run.add_argument("--workspace", "-w", default="/tmp/l10n-workspace", help="工作目录")
    p_run.add_argument("--model", default="claude-sonnet-4-20250514", help="翻译使用的模型")
    p_run.add_argument("--fast", action="store_true", help="快速模式")
    p_run.add_argument("--max-iterations", type=int, default=3, help="最大迭代次数")
    p_run.add_argument("--skills", nargs="*", help="只处理指定的 skill 名称")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "discover": cmd_discover,
        "translate": cmd_translate,
        "evaluate": cmd_evaluate,
        "check": cmd_check,
        "report": cmd_report,
        "publish": cmd_publish,
        "run": cmd_run,
    }

    handler = handlers[args.command]
    try:
        handler(args)
    except KeyboardInterrupt:
        print("\n中断", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
