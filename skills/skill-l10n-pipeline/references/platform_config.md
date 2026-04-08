# 平台配置

## 上传方式

当前: 文件上传（手动）
未来: API 接口（开发中）

## 打包格式

- 格式: .tar.gz
- 命名: `<skill-name>.tar.gz`
- 包含: 完整 skill 目录 + 评测报告 HTML（如果有）

## 输出目录

```
~/l10n-output/
├── <skill-name>.tar.gz
├── <skill-name>_info.json
├── <skill-name>_report.html  (翻译 skill 才有)
└── manifest.json             (所有 skill 的汇总清单)
```

## manifest.json 格式

```json
{
  "generated_at": "2026-04-02T10:30:00Z",
  "skills": [
    {
      "name": "pdf-maker-zh",
      "language": "zh",
      "translated": true,
      "package": "pdf-maker-zh.tar.gz",
      "eval_passed": true
    },
    {
      "name": "code-reviewer",
      "language": "en",
      "translated": false,
      "package": "code-reviewer.tar.gz",
      "eval_passed": false
    }
  ]
}
```

## 未来 API 扩展

当 API 开发完成后:
- 在此文件中添加 API endpoint、认证方式、请求格式
- publisher.md 中的上传逻辑从文件复制改为 HTTP 请求
- 保留文件上传作为 fallback
