#!/usr/bin/env python3
"""Generate meta-skills.pdf from README.md and SKILL_LIST.md via WeasyPrint."""

import markdown
from weasyprint import HTML

CSS = """
@page {
    size: A4;
    margin: 20mm;
    @bottom-center {
        content: counter(page);
        font-size: 8pt;
        color: #999;
    }
}

body {
    font-family: "Noto Sans CJK SC", "Noto Sans", sans-serif;
    font-size: 10pt;
    line-height: 1.6;
    color: #333;
}

h1 {
    font-size: 24pt;
    color: #2C3E50;
    text-align: center;
    border-bottom: 2px solid #2C3E50;
    padding-bottom: 4mm;
    margin-top: 10mm;
}

h2 {
    font-size: 16pt;
    color: #2C3E50;
    margin-top: 8mm;
    margin-bottom: 3mm;
}

h3 {
    font-size: 13pt;
    color: #2980B9;
    margin-top: 6mm;
    margin-bottom: 2mm;
}

h4 {
    font-size: 11pt;
    color: #2C3E50;
    margin-top: 5mm;
    margin-bottom: 2mm;
}

blockquote {
    background: #F0F4F8;
    border-left: 3px solid #2980B9;
    margin: 3mm 0;
    padding: 3mm 4mm 3mm 5mm;
    color: #555;
}

blockquote p {
    margin: 0.5em 0;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 3mm 0;
    font-size: 9pt;
}

thead th {
    background: #34495E;
    color: white;
    padding: 3mm;
    text-align: left;
    font-weight: bold;
}

tbody td {
    padding: 3mm;
    border: 0.5px solid #DEE2E6;
}

tbody tr:nth-child(even) {
    background: #F8F9FA;
}

a {
    color: #2980B9;
    text-decoration: none;
}

code {
    font-family: "Noto Sans Mono", "Noto Sans Mono CJK SC", monospace;
    background: #F5F5F5;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 8.5pt;
    color: #C0392B;
}

pre {
    background: #F5F5F5;
    border: 0.5px solid #DEE2E6;
    padding: 3mm 4mm;
    border-radius: 3px;
    overflow-x: auto;
}

pre code {
    background: none;
    padding: 0;
    color: #333;
    font-size: 8.5pt;
}

ul {
    padding-left: 6mm;
}

li {
    margin-bottom: 1mm;
}

hr {
    border: none;
    border-top: 0.5px solid #DEE2E6;
    margin: 5mm 0;
}

/* Page break before SKILL_LIST section */
.skill-list-section {
    page-break-before: always;
}
"""


def md_to_html(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    return markdown.markdown(text, extensions=['tables', 'fenced_code'])


def main():
    readme_html = md_to_html('README.md')
    skill_list_html = md_to_html('SKILL_LIST.md')

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>{CSS}</style>
</head>
<body>
{readme_html}
<div class="skill-list-section">
{skill_list_html}
</div>
</body>
</html>"""

    HTML(string=full_html).write_pdf('meta-skills.pdf')
    print('Generated meta-skills.pdf')


if __name__ == '__main__':
    main()
