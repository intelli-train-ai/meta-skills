#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语言检测脚本 - 检测 SKILL.md 文件的主要语言

用法: python detect_language.py /path/to/SKILL.md
"""

import argparse
import json
import re
import sys


def extract_frontmatter_description(content: str) -> str:
    """从 YAML frontmatter 中提取 description 字段"""
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return ""
    frontmatter = match.group(1)
    # 简单提取 description 字段（支持多行）
    desc_match = re.search(r'^description:\s*(.+?)(?:\n\S|\Z)', frontmatter, re.MULTILINE | re.DOTALL)
    if desc_match:
        return desc_match.group(1).strip()
    return ""


def count_cjk_chars(text: str) -> dict:
    """统计 CJK 字符数量，返回各语言字符计数"""
    # 中文字符范围（CJK 统一汉字 + 扩展 A）
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))
    # 日文字符范围（平假名 + 片假名）
    japanese_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text))
    # 韩文字符范围（韩文音节）
    korean_chars = len(re.findall(r'[\uac00-\ud7af]', text))
    # 非空白字符总数
    non_whitespace = len(re.findall(r'\S', text))

    return {
        "chinese": chinese_chars,
        "japanese": japanese_chars,
        "korean": korean_chars,
        "total_non_whitespace": non_whitespace,
    }


def detect_language(file_path: str) -> dict:
    """检测文件语言，返回检测结果"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"错误: 文件不存在 - {file_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: 读取文件失败 - {e}", file=sys.stderr)
        sys.exit(1)

    # 提取 frontmatter description
    description = extract_frontmatter_description(content)

    # 获取正文前 100 行（跳过 frontmatter）
    lines = content.split("\n")
    # 跳过 frontmatter
    body_start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                body_start = i + 1
                break

    body_lines = lines[body_start:body_start + 200]
    body_text = "\n".join(body_lines)

    # 过滤掉代码块（```...```），因为技术 skill 的代码块大量使用英文/ASCII，
    # 会严重稀释中文占比导致误判
    body_text_no_code = re.sub(r'```.*?```', '', body_text, flags=re.DOTALL)

    # 合并 description 和正文用于检测（description 权重更高，重复 3 次）
    sample_text = (description + "\n") * 3 + body_text_no_code

    # 统计字符
    counts = count_cjk_chars(sample_text)
    total = counts["total_non_whitespace"]

    if total == 0:
        return {
            "language": "unknown",
            "confidence": 0.0,
            "is_chinese": False,
            "chinese_ratio": 0.0,
            "japanese_ratio": 0.0,
            "korean_ratio": 0.0,
            "file": file_path,
        }

    chinese_ratio = counts["chinese"] / total
    japanese_ratio = counts["japanese"] / total
    korean_ratio = counts["korean"] / total

    # 判定语言
    # 技术 skill 即使是中文版也含大量英文（API 名、代码引用等），
    # 所以阈值设为 0.15 而非通常的 0.3
    if chinese_ratio > 0.15:
        language = "zh"
        confidence = min(chinese_ratio * 2, 1.0)
        is_chinese = True
    elif japanese_ratio > 0.1 or (japanese_ratio > 0.05 and chinese_ratio > 0.1):
        # 日文通常混合使用汉字和假名
        language = "ja"
        confidence = min((japanese_ratio + chinese_ratio) * 1.5, 1.0)
        is_chinese = False
    elif korean_ratio > 0.1:
        language = "ko"
        confidence = min(korean_ratio * 2, 1.0)
        is_chinese = False
    else:
        language = "en"
        confidence = max(1.0 - chinese_ratio - japanese_ratio - korean_ratio, 0.5)
        is_chinese = False

    return {
        "language": language,
        "confidence": round(confidence, 2),
        "is_chinese": is_chinese,
        "chinese_ratio": round(chinese_ratio, 4),
        "japanese_ratio": round(japanese_ratio, 4),
        "korean_ratio": round(korean_ratio, 4),
        "file": file_path,
    }


def main():
    parser = argparse.ArgumentParser(description="检测 SKILL.md 文件的主要语言")
    parser.add_argument("file", help="SKILL.md 文件路径")
    parser.add_argument("--pretty", action="store_true", help="格式化 JSON 输出")
    args = parser.parse_args()

    result = detect_language(args.file)

    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
