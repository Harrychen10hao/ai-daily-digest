# AI 产品与 UX 科技早报

一个不依赖 Coze 的 Python 工具：从可配置的 RSS 和公开 API 获取资讯，去重、筛选、分类后使用 OpenAI 兼容 API 生成中文早报，并通过飞书群机器人 Webhook 推送。

## 功能

- 最近 24 小时优先；不足时扩大到最近 7 天。
- URL、标题和内容指纹去重。
- AI 产品体验、UX/UI 设计、科技资讯为主要分类；论文和 GitHub 为可选分类。
- 模型只能使用本次实际抓取文章的原始链接，模型输出链接会被再次校验。
- 单个 RSS/API 来源失败不会阻断其他来源。
- 没有 `LLM_API_KEY` 时使用本地降级早报；没有飞书 Webhook 时发送命令给出清晰提示。
- 飞书消息过长会按章节自动拆分并重试发送。

## 安装

建议使用 Python 3.9 或更高版本：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Windows PowerShell 等价命令：

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

如果系统没有 `python` 命令，请使用 `python3`；激活虚拟环境后，本文中的 `python` 命令即可使用。

## 配置资讯来源

所有来源只在 `config/sources.yaml` 中维护，代码不内置来源 URL。每项可以设置：

```yaml
- name: Source name
  url: https://example.com/feed.xml
  category: ai_product
  kind: rss
  enabled: true
  priority: 1
```

支持 `rss` 和 `github_search` 两种类型。新增来源前请确认其公开可访问、允许自动请求，并优先使用官方 RSS/API；不要加入需要登录或明显违反网站规则的来源。

## 环境变量

复制 `.env.example` 为 `.env` 后填写：

| 变量 | 必填场景 | 说明 |
| --- | --- | --- |
| `LLM_API_KEY` | 生成模型总结时 | OpenAI 兼容服务的 API Key |
| `LLM_BASE_URL` | 使用非 OpenAI 服务时 | 默认 `https://api.openai.com/v1` |
| `LLM_MODEL` | 生成模型总结时 | 默认 `gpt-4o-mini` |
| `FEISHU_WEBHOOK_URL` | 发送飞书时 | 飞书群机器人 Webhook |
| `DATA_DIR` | 否 | 默认 `data` |
| `SOURCES_FILE` | 否 | 默认 `config/sources.yaml` |
| `REQUEST_TIMEOUT` | 否 | 默认 20 秒 |
| `REQUEST_RETRIES` | 否 | 默认重试 2 次 |
| `FEISHU_MAX_CHARS` | 否 | 单条消息默认最多 6000 字符 |

## 本地运行

```bash
# 只抓取并保存 data/latest_articles.json
python -m ai_daily_digest fetch

# 读取已抓取文章，生成并保存 data/latest_digest.md
python -m ai_daily_digest generate

# 发送已生成的早报到飞书
python -m ai_daily_digest send

# 完整执行：抓取 -> 生成 -> 发送
python -m ai_daily_digest run

# 完整执行但不发送飞书，适合本地测试
python -m ai_daily_digest run --dry-run
```

没有 `LLM_API_KEY` 时，`generate` 和 `run --dry-run` 会记录提示并生成降级早报；没有 `FEISHU_WEBHOOK_URL` 时，`send` 或普通 `run` 会以错误提示结束。完全离线测试可使用：

```bash
python -m ai_daily_digest --test-mode run --dry-run
```

测试模式读取 `fixtures/sample_articles.json`，不请求 RSS、不调用模型、不调用飞书。

## 创建飞书群机器人

1. 在飞书中创建一个群；如果只想自己接收，可以创建一个只有自己的群作为接收入口。
2. 打开群设置，进入“群机器人”或“机器人”管理，添加“自定义机器人”。
3. 设置名称和头像，按需要配置关键词、签名或 IP 白名单安全策略。
4. 创建后复制 Webhook 地址，填入 `.env` 的 `FEISHU_WEBHOOK_URL`。
5. 先运行 `python -m ai_daily_digest --test-mode run --dry-run` 确认内容，再运行 `send` 或完整 `run`。

初版使用群机器人 Webhook 发送群消息，不实现个人私聊权限。如果机器人不能直接给个人发送，使用只有自己成员的飞书群即可。

## GitHub Actions

工作流位于 `.github/workflows/daily_digest.yml`：

```yaml
0 0 * * *
```

GitHub Actions 的 cron 使用 UTC，因此 `00:00 UTC` 对应北京时间 `08:00`。GitHub 的计划任务可能存在几分钟甚至更长的排队延迟，不能保证精确到秒。

在仓库的 **Settings → Secrets and variables → Actions** 中新增以下 Repository secrets：

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `FEISHU_WEBHOOK_URL`

其中 `LLM_BASE_URL` 和 `LLM_MODEL` 可以不配置，工作流会使用程序默认值；建议显式配置，便于后续切换服务。工作流也支持 GitHub Actions 页面上的 **Run workflow** 手动触发。

## 测试

测试只使用本地数据和 `httpx.MockTransport`，不调用真实模型 API、RSS 或飞书 Webhook：

```bash
python -m pytest
```

## 已知限制

- RSS 内容质量、发布时间字段和可用性由各来源决定；来源失效时会记录日志并跳过。
- 无法确认原始链接的模型条目会被丢弃，可能导致某些分类少于目标数量。
- GitHub Search API 默认关闭，匿名请求可能受限；需要时在 `config/sources.yaml` 中开启。
- 飞书机器人是群入口，不支持初版个人私聊、权限管理或消息回执业务。
- GitHub Actions 运行环境和公共来源可能偶发网络波动，单次失败不会自动补跑。
