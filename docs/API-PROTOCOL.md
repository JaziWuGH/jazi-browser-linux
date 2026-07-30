# Jazi Browser — API Protocol v0.1

本文档定义 Jazi Browser 的标准 HTTP API 接口。所有平台实现（Linux/Windows/macOS）必须兼容此协议，确保 Agent 无需关心底层平台。

## 基础约定

| 项目 | 值 |
|------|-----|
| 协议 | HTTP/1.1 REST |
| 格式 | JSON (请求/响应) |
| 编码 | UTF-8 |
| 端口 | 9228 (默认) |
| 绑定 | 127.0.0.1 (仅本地) |

## 1. 系统

### GET /health

服务健康检查。

**响应:**
```json
{
  "status": "ok",
  "browser_ready": true,
  "spaces": 1,
  "profile_dir": "/home/user/.jazi/profile"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | `"ok"` 或 `"degraded"` |
| browser_ready | bool | 浏览器引擎是否就绪 |
| spaces | int | 当前活跃 Space 数量 |
| profile_dir | string | 浏览器 Profile 目录路径 |

---

## 2. Space 管理

Space 是隔离的浏览器工作区。每个 Space 拥有独立的 Cookie/Storage/标签页。多个 Agent 使用不同 Space 可并行工作互不干扰。

### POST /space

创建新 Space。

**请求:**
```json
{
  "name": "myagent",
  "inherit_cookies": true
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 唯一 Space 名称 |
| inherit_cookies | bool | ❌ | 是否继承默认 Profile 的 Cookie，默认 true |

**响应 201:**
```json
{
  "name": "myagent",
  "page_count": 1,
  "spaces": [{"name": "default", "is_default": true, "page_count": 1}]
}
```

**错误:**
- `409` — Space 名称已存在
- `500` — 浏览器未就绪

### GET /spaces

列出所有活跃 Space。

**响应:**
```json
{
  "spaces": [
    {"name": "default", "is_default": true, "page_count": 1},
    {"name": "myagent", "is_default": false, "page_count": 2}
  ]
}
```

### DELETE /space/{name}

关闭并销毁指定 Space。

**响应:**
```json
{
  "closed": "myagent",
  "spaces": [{"name": "default", "is_default": true, "page_count": 1}]
}
```

**错误:**
- `400` — 不能关闭 default Space
- `404` — Space 不存在

---

## 3. 页面操作

所有页面操作基于 Space。交互元素通过快照中的 `@eN` 引用 ID 定位。

### POST /space/{name}/navigate

导航到指定 URL。返回目标页面的快照。

**请求:**
```json
{
  "url": "https://example.com",
  "timeout": 30000
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | ✅ | 目标 URL |
| timeout | int | ❌ | 超时毫秒，默认 30000 |

**响应:**
```json
{
  "url": "https://example.com",
  "snapshot": "[Snapshot] URL: https://example.com\n\n--- Interactive Elements (5 total) ---\n  @e1 | button | \"登录\"\n  @e2 | input | name=\"username\""
}
```

### GET /space/{name}/snapshot

获取当前页面快照（不重新导航）。

**参数:**
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| compact | bool | true | 紧凑模式（仅交互元素+标题） |

**响应:**
```json
{
  "snapshot": "[Snapshot] URL: https://example.com\n\n--- Interactive Elements (5 total) ---\n  @e1 | button | \"登录\"",
  "url": "https://example.com"
}
```

### POST /space/{name}/click

点击指定交互元素。

**请求:**
```json
{
  "ref": "@e3"
}
```

**响应:**
```json
{
  "clicked": "@e3",
  "url": "https://example.com/dashboard",
  "snapshot": "[Snapshot] URL: https://example.com/dashboard\n..."
}
```

**错误响应:**
```json
{
  "error": "Element @e3 not found on current page. Page may have changed.",
  "current_snapshot": "[Snapshot] ..."
}
```

### POST /space/{name}/fill

向输入框填入内容。

**请求:**
```json
{
  "ref": "@e5",
  "value": "hello world"
}
```

**响应:**
```json
{
  "filled": "@e5",
  "value": "hello world"
}
```

### POST /space/{name}/wait

等待页面出现指定文本。

**请求:**
```json
{
  "text": "Welcome back",
  "timeout": 15000
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| text | string | ✅ | 等待出现的文本 |
| timeout | int | ❌ | 超时毫秒，默认 15000 |

**响应:**
```json
{
  "found": "Welcome back",
  "snapshot": "[Snapshot] ..."
}
```

### POST /space/{name}/capture

截取当前页面。

**响应:**
```json
{
  "screenshot": "iVBORw0KGgo...",
  "format": "png",
  "url": "https://example.com"
}
```

| 字段 | 说明 |
|------|------|
| screenshot | Base64 编码的 PNG 图片 |
| format | 固定为 `"png"` |

### GET /space/{name}/text

提取页面可见文本。

**参数:**
| 参数 | 默认 | 说明 |
|------|------|------|
| max_chars | 5000 | 最大字符数 |

**响应:**
```json
{
  "text": "页面正文内容...",
  "url": "https://example.com"
}
```

### POST /space/{name}/eval

在页面上下文中执行任意 JavaScript。

**参数 (Query String):**
| 参数 | 说明 |
|------|------|
| js_code | 要执行的 JavaScript 代码 |

**响应:**
```json
{
  "result": "执行结果"
}
```

---

## 4. Cookie 管理

### POST /space/{name}/cookies/export

导出 Space 中所有 Cookie 到 JSON 文件。

**参数:**
| 参数 | 必填 | 说明 |
|------|------|------|
| output_path | ❌ | 输出路径，默认 `~/jazi-cookies-<timestamp>.json` |

**响应:**
```json
{
  "exported": "/home/user/jazi-cookies-20260730-120000.json"
}
```

**导出文件格式:**
```json
{
  "version": 1,
  "exported_at": "2026-07-30T12:00:00",
  "source": "jazi-browser",
  "count": 42,
  "cookies": [
    {
      "name": "session",
      "value": "abc123",
      "domain": ".example.com",
      "path": "/",
      "expires": 1750000000,
      "httpOnly": true,
      "secure": true,
      "sameSite": "Lax"
    }
  ]
}
```

### POST /space/{name}/cookies/import

从 JSON 文件导入 Cookie。

**请求:**
```json
{
  "file_path": "/path/to/cookies.json",
  "clear_existing": false
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file_path | string | ✅ | Cookie JSON 文件绝对路径 |
| clear_existing | bool | ❌ | 导入前是否清除已有 Cookie |

**响应:**
```json
{
  "imported": 40,
  "skipped": 2,
  "total_in_file": 42
}
```

**支持的输入格式:**
- Jazi Browser 导出格式 (version 1)
- Playwright storageState 格式
- EditThisCookie 导出格式
- 纯 Cookie 对象数组

### GET /space/{name}/cookies/inspect

预览 Cookie 文件内容（不导入）。

**参数:**
| 参数 | 说明 |
|------|------|
| file_path | Cookie JSON 文件路径 |

**响应:**
```json
{
  "total": 42,
  "unique_domains": 5,
  "top_domains": [
    {"domain": ".google.com", "cookies": 15},
    {"domain": ".github.com", "cookies": 8}
  ],
  "exported_at": "2026-07-30T12:00:00"
}
```

---

## 5. 快照格式规范

快照是 Agent 理解页面结构的关键。格式必须遵循以下规范：

```
[Snapshot] URL: <当前页面URL>
Title: <页面标题>

--- Headings --- (可选)
  # 一级标题
  ## 二级标题

--- Interactive Elements (N total) ---
  @e1 | <标签类型> | "<文本>"
  @e2 | <标签类型> | <属性信息>
```

### 交互元素格式

```
@eN | tag[subtype] | 描述字段...
```

| 标签类型 | 示例 |
|----------|------|
| button | `@e1 \| button \| "提交"` |
| a | `@e2 \| a \| "首页" \| href="/"` |
| input | `@e3 \| input \| name="username"` |
| input[email] | `@e4 \| input[email] \| name="email"` |
| input[radio] | `@e5 \| input[radio] \| name="size" \| value="medium"` |
| input[checkbox] | `@e6 \| input[checkbox] \| name="agree"` |
| select | `@e7 \| select \| name="country"` |
| textarea | `@e8 \| textarea \| name="comment"` |

### @eN 定位机制

每个交互元素在 DOM 中被注入 `data-jazi-ref="@eN"` 属性。click/fill 通过 CSS 选择器 `[data-jazi-ref="@eN"]` 定位。

⚠️ **注意:** 每次 navigate/click/页面跳转后 @eN 引用可能变化，Agent 必须在每次操作后重新获取快照。

---

## 6. 标准交互流程

Agent 控制浏览器的标准流程：

```
1. POST /health                    → 确认服务在线
2. POST /space -d '{"name":"X"}'  → 创建隔离 Space
3. POST /space/X/navigate          → 导航到目标 URL
4. 解析 snapshot 中的 @eN 引用
5. POST /space/X/fill              → 填写表单
6. POST /space/X/click             → 点击按钮
7. 循环 4-6 直到任务完成
8. GET  /space/X/snapshot          → 最终验证
9. DELETE /space/X                 → (可选) 清理 Space
```

## 7. 错误处理

所有错误返回标准 HTTP 状态码 + JSON body：

```json
{
  "detail": "错误描述信息"
}
```

| 状态码 | 场景 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | Space 或资源不存在 |
| 409 | Space 名称冲突 |
| 500 | 服务器内部错误 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.1 | 2026-07-30 | 初始协议定义 |
