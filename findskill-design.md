# findskill Skill 实现文档

> 从自建 Skill 平台搜索、下载、发布 Claude Code Skills。

---

## 1. API 端点总览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/skills/search` | 按关键词/分类搜索 skill |
| GET | `/api/skills/:id/download` | 下载 skill 文件包 |
| POST | `/api/skills` | 发布新 skill |
| GET | `/api/categories` | 获取分类列表 |

---

## 2. 端点详细设计

### 2.1 搜索 Skill

```
GET /api/skills/search
```

**请求参数（Query String）：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| q | string | 否 | 搜索关键词，匹配 name 和 description |
| category | string | 否 | 分类筛选 |
| tag | string | 否 | 标签筛选，多个用逗号分隔 |
| author | string | 否 | 按作者筛选 |
| sort | string | 否 | 排序方式：`downloads`（默认）/ `newest` / `updated` |
| page | int | 否 | 页码，默认 1 |
| per_page | int | 否 | 每页数量，默认 20，最大 100 |

**响应示例：**

```json
{
  "total": 128,
  "page": 1,
  "per_page": 20,
  "results": [
    {
      "id": "skill-pdf-tools",
      "name": "pdf-tools",
      "description": "PDF 读取、合并、拆分工具",
      "author": "orion",
      "category": "工具",
      "tags": ["pdf", "document"],
      "downloads": 1234,
      "created_at": "2026-01-15T08:00:00Z",
      "updated_at": "2026-03-20T12:00:00Z"
    }
  ]
}
```

---

### 2.2 下载 Skill

```
GET /api/skills/:id/download
```

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| id | string | skill 唯一标识 |

**响应：**

返回 `.tar.gz` 压缩包（`Content-Type: application/gzip`），包含完整的 skill 目录结构：

```
skill-name/
├── SKILL.md
├── scripts/       # 可选
├── references/    # 可选
└── assets/        # 可选
```

**响应头：**

```
Content-Type: application/gzip
Content-Disposition: attachment; filename="skill-name.tar.gz"
```

**错误响应：**

```json
// 404
{ "error": "skill_not_found", "message": "Skill 不存在" }
```

---

### 2.3 发布 Skill

```
POST /api/skills
```

**请求头：**

```
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

**请求字段（multipart）：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | skill 名称（唯一标识） |
| description | string | 是 | skill 简介 |
| category | string | 是 | 所属分类 |
| tags | string | 否 | 标签，逗号分隔 |
| file | file | 是 | `.tar.gz` 压缩包，包含 SKILL.md 及相关文件 |

**响应示例：**

```json
// 201 Created
{
  "id": "skill-pdf-tools",
  "name": "pdf-tools",
  "message": "发布成功"
}
```

**错误响应：**

```json
// 400
{ "error": "invalid_package", "message": "压缩包中缺少 SKILL.md" }

// 409
{ "error": "name_conflict", "message": "skill 名称已存在" }

// 401
{ "error": "unauthorized", "message": "缺少或无效的 token" }
```

---

### 2.4 分类列表

```
GET /api/categories
```

**无请求参数。**

**响应示例：**

```json
{
  "categories": [
    { "name": "搜索", "count": 15 },
    { "name": "开发", "count": 42 },
    { "name": "工具", "count": 28 },
    { "name": "集成", "count": 19 },
    { "name": "效率", "count": 11 }
  ]
}
```

---

## 3. Skill 工作流设计

### 3.1 搜索流程

```
用户输入关键词
    → GET /api/skills/search?q=xxx
    → 格式化展示结果列表
    → 用户选择某个 skill
    → 询问安装位置（全局 / 项目）
    → 执行下载安装
```

### 3.2 下载安装流程

```
GET /api/skills/:id/download
    → 保存 .tar.gz 到临时目录
    → 解压到目标位置：
        全局：~/.claude/skills/<name>/
        项目：.claude/skills/<name>/
    → 验证 SKILL.md 存在且 frontmatter 合法
    → 清理临时文件
    → 输出安装成功信息
```

### 3.3 发布流程

```
用户指定 skill 目录路径
    → 验证目录结构（SKILL.md 必须存在）
    → 从 SKILL.md frontmatter 提取 name、description
    → 打包为 .tar.gz
    → POST /api/skills（需要 token）
    → 输出发布结果
```

### 3.4 浏览分类流程

```
GET /api/categories
    → 展示分类列表及 skill 数量
    → 用户选择分类
    → GET /api/skills/search?category=xxx
    → 展示该分类下的 skill
```

---

## 4. 认证方式

| 操作 | 是否需要认证 |
|------|-------------|
| 搜索 | 否 |
| 下载 | 否 |
| 发布 | 是（Bearer Token） |
| 分类列表 | 否 |

Token 存储位置：`~/.findskill/token`，skill 首次发布时引导用户配置。

---

## 5. 错误码规范

| HTTP 状态码 | error 字段 | 说明 |
|------------|-----------|------|
| 400 | invalid_request | 请求参数不合法 |
| 400 | invalid_package | 上传的压缩包格式不正确 |
| 401 | unauthorized | 未认证或 token 无效 |
| 404 | skill_not_found | skill 不存在 |
| 409 | name_conflict | skill 名称冲突 |
| 429 | rate_limited | 请求过于频繁 |
| 500 | internal_error | 服务器内部错误 |
