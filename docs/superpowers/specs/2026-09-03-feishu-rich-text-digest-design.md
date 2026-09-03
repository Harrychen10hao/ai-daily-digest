# 飞书富文本早报改造设计

## 背景

当前早报内容以 Markdown 字符串保存，并通过飞书群机器人 `text` 消息发送。飞书不会在普通文本消息中渲染 Markdown 标题，因此手机端会直接看到 `#`、`##`、`###`，标题层级不明显，重点内容也不突出。

目标是保留本地 Markdown 产物，同时将飞书消息改为接近参考截图的中文富文本早报：标题清晰、重点突出、链接可点击、适合手机阅读。

## 目标与非目标

### 目标

- 飞书消息使用群机器人支持的 `post` 富文本消息。
- 早报标题、日期、重点新闻和分类层级清晰可读。
- 每条新闻显示清晰的编号/标题行、摘要、价值说明和可点击原文链接；使用群机器人 `post` 支持的字段，不发送不兼容的样式字段。
- 长消息按完整新闻条目拆分为多条，不截断新闻内容。
- 保留 `latest_digest.md` 作为本地 Markdown 输出。
- 额外保存结构化早报 JSON，供发送阶段直接渲染，避免解析 Markdown。
- 所有飞书请求继续使用现有超时、重试和 mock 测试机制。
- `--dry-run` 继续保证不调用飞书 Webhook。

### 非目标

- 不改动 RSS 抓取、分类、去重和模型总结规则。
- 不实现飞书交互卡片、按钮、回执或个人私聊权限。
- 不改变飞书 Webhook 的认证方式。
- 不把任何密钥写入代码、配置样例或测试夹具。

## 用户可见格式

飞书每条消息使用富文本结构：

1. 顶部显示日报标题和日期。
2. 首段显示一句话趋势总结。
3. “今日重点”使用 `①`、`②`、`③` 编号，新闻标题加粗。
4. 每条新闻按以下顺序显示：
   - 编号或清晰的标题行
   - 摘要
   - 为什么值得关注/设计启发/行业影响
   - “查看原文”可点击链接
5. 后续分类按“AI 产品体验、UX/UI 设计经验、科技资讯、AI 论文、GitHub 开源项目”顺序显示；空分类省略。
6. 最后显示今日行动建议。

消息中不显示 Markdown 的 `#`、`##`、`###` 标记。

## 方案与数据流

### 结构化早报保存

`generate_pipeline` 在生成 digest 后同时写入：

- `data/latest_digest.md`：继续保存本地 Markdown 文本。
- `data/latest_digest.json`：保存经过链接校验和字段清洗后的 digest 对象。

`send_pipeline` 优先读取 `latest_digest.json`，通过新的飞书富文本格式化器生成消息 payload。若结构化文件不存在，给出要求重新执行 `generate` 的清晰错误，不从 Markdown 反向解析。

### 飞书 payload

新增富文本格式化函数，将一个 digest 转换为一个或多个飞书 `post` 消息 payload：

```json
{
  "msg_type": "post",
  "content": {
    "post": {
      "zh_cn": {
        "title": "AI 产品与 UX 科技早报",
        "content": [
          [
            {"tag": "text", "text": "① "},
            {"tag": "text", "text": "新闻标题", "style": ["bold"]}
          ],
          [
            {"tag": "text", "text": "摘要：..."}
          ],
          [
            {"tag": "a", "text": "查看原文", "href": "https://example.com/article"}
          ]
        ]
      }
    }
  }
}
```

现有 `FeishuClient.send` 的普通文本能力保留；新增富文本发送入口，避免破坏现有低层调用和测试。`send_pipeline` 使用富文本入口。群机器人 `post` 的文本元素不添加 `style` 字段，避免 Webhook 返回 `19002 unknown content value`。

### 消息拆分

拆分以完整新闻条目为边界，优先在分类之间切分；单条消息超过配置上限时再按富文本行安全切分。每个消息都保留日报标题，必要时附加序号，例如“（1/2）”。不拆断链接的 href，也不生成空消息。

## 错误处理与兼容性

- 飞书返回 HTTP 错误或业务错误时沿用现有重试逻辑。
- 富文本构造时缺少 URL 的条目直接省略链接行，不编造 URL。
- 缺少 `latest_digest.json` 时，`send` 失败并提示重新运行 `generate`。
- 缺少 `FEISHU_WEBHOOK_URL` 时仍然清晰报错。
- Python 3.9 和 GitHub Actions Python 3.11 均使用现有依赖和类型写法，不引入新的运行时依赖。

## 测试设计

- 富文本格式化测试：验证标题层级、重点编号、加粗标题、可点击链接和空分类省略。
- 拆分测试：验证按完整条目拆分、最大长度、序号和无空消息。
- 飞书客户端测试：使用 `httpx.MockTransport` 验证 `msg_type=post`、请求 payload、重试和业务错误处理。
- pipeline 测试：验证生成阶段同时保存 Markdown 与 JSON，发送阶段读取 JSON；不调用真实模型、RSS 或飞书。
- 运行现有全量 pytest 和 `compileall`，确认旧功能没有回归。

## 验收标准

- 飞书中不再显示 Markdown 标题符号。
- 手机端能快速识别日报标题、今日重点、新闻标题和链接。
- 原文链接可以点击并且全部来自实际抓取文章。
- `python -m ai_daily_digest run --dry-run` 不发送飞书请求。
- `python -m pytest` 和 Python 3.9 `compileall` 通过。
