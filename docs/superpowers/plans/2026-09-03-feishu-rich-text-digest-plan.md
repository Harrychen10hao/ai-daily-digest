# Feishu Rich Text Digest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将飞书早报从显示 Markdown 符号的普通文本改为层级清晰、原文链接可点击且兼容 Webhook 的 `post` 富文本消息，同时保留本地 Markdown 输出。

**Architecture:** 生成阶段继续产出 `latest_digest.md`，并新增经过校验的 `latest_digest.json`。发送阶段读取 JSON，由独立的飞书富文本格式化器生成一个或多个 `post` payload；低层 `FeishuClient.send()` 保留普通文本能力，并新增 `send_posts()` 发送结构化 payload。所有网络测试使用 `httpx.MockTransport`。

**Tech Stack:** Python 3.9+, dataclasses/标准库、httpx、pytest、httpx.MockTransport、飞书群机器人 Webhook。

## Global Constraints

- 不改动 RSS 抓取、分类、去重和模型总结规则。
- 不实现飞书交互卡片、按钮、回执或个人私聊权限。
- 不把密钥写入代码、测试或配置样例。
- 所有飞书、模型和 RSS 测试必须使用 mock，不发送真实请求。
- 模型输出链接只能来自本次实际抓取文章。
- `python -m ai_daily_digest run --dry-run` 不得调用飞书。
- 保持 Python 3.9 本地和 Python 3.11 GitHub Actions 兼容。

---

### Task 1: 新增飞书富文本 payload 格式化器

**Files:**
- Modify: `src/ai_daily_digest/formatter.py`
- Test: `tests/test_formatter.py`

**Interfaces:**
- Consumes: 已校验的 digest 字典，字段包括 `trend`、`highlights`、分类数组和 `action_suggestions`。
- Produces: `format_feishu_posts(digest: dict, published_at: datetime | None = None, max_chars: int = 6000) -> list[dict]`。每个返回值都是完整的飞书 `post` payload，形状为 `{"msg_type": "post", "content": {"post": {"zh_cn": {"title": str, "content": list[list[dict]]}}}}`。

- [x] **Step 1: Write failing tests**

在 `tests/test_formatter.py` 增加：

```python
def test_format_feishu_posts_uses_hierarchy_bold_titles_and_clickable_links():
    digest = {
        "trend": "AI 产品从聊天走向工作流。",
        "highlights": [{
            "title": "Agent 交互更新",
            "summary": "摘要",
            "why": "值得关注",
            "url": "https://example.com/agent",
        }],
        "ai_product": [],
        "ux_design": [],
        "tech": [],
        "paper": [],
        "github": [],
        "action_suggestions": ["体验一次 Agent"],
    }

    posts = format_feishu_posts(digest, datetime(2026, 9, 3, tzinfo=timezone.utc))
    payload = posts[0]
    content = payload["content"]["post"]["zh_cn"]["content"]
    flattened = [element for line in content for element in line]

    assert payload["msg_type"] == "post"
    assert payload["content"]["post"]["zh_cn"]["title"] == "AI 产品与 UX 科技早报"
    assert any(element.get("tag") == "text" and element["text"] == "Agent 交互更新" for element in flattened)
    assert {element["tag"] for element in flattened} >= {"text", "a"}
    assert any(element.get("href") == "https://example.com/agent" for element in flattened)
    assert all("#" not in element.get("text", "") for element in flattened)


def test_format_feishu_posts_omits_empty_sections_and_splits_items():
    item = {"title": "标题", "summary": "摘要", "why": "原因", "url": "https://example.com/a"}
    digest = {
        "trend": "趋势",
        "highlights": [item, {**item, "url": "https://example.com/b"}],
        "ai_product": [], "ux_design": [], "tech": [], "paper": [], "github": [],
        "action_suggestions": [],
    }

    posts = format_feishu_posts(digest, max_chars=250)

    assert len(posts) > 1
    assert all(post["msg_type"] == "post" for post in posts)
    assert all(post["content"]["post"]["zh_cn"]["content"] for post in posts)
    assert "AI 产品体验" not in str(posts)
```

- [x] **Step 2: Run formatter tests and confirm RED**

Run:

```bash
source .venv/bin/activate
python -m pytest tests/test_formatter.py -q
```

Expected: new tests fail because `format_feishu_posts` does not exist yet。

- [x] **Step 3: Implement the minimal formatter**

在 `formatter.py` 中新增内部 helper，将每一行构造成飞书富文本元素：普通文本使用 `{"tag": "text", "text": ...}`，链接使用 `{"tag": "a", "text": "查看原文", "href": url}`。不要添加 `style` 等群机器人 `post` 不支持的字段。使用 `SECTION_NAMES` 保持现有分类顺序，空分类跳过；每个新闻条目作为不可拆分的行集合，按 `max_chars` 估算文本长度分组，最终构造：

```python
{
    "msg_type": "post",
    "content": {
        "post": {
            "zh_cn": {
                "title": "AI 产品与 UX 科技早报",
                "content": lines,
            }
        }
    },
}
```

标题行包含 `①`/`②`/`③`，其他分类条目使用同样的加粗标题但不强制编号。不要从 URL 生成显示文本以外的链接，不允许缺失 URL 的条目生成 href。

- [x] **Step 4: Run formatter tests and confirm GREEN**

Run:

```bash
python -m pytest tests/test_formatter.py -q
```

Expected: all formatter tests pass。

---

### Task 2: 增加 Feishu post payload 发送入口

**Files:**
- Modify: `src/ai_daily_digest/feishu.py`
- Test: `tests/test_feishu.py`

**Interfaces:**
- Consumes: `list[dict]`，每项是 `format_feishu_posts` 生成的完整 payload。
- Produces: `FeishuClient.send_posts(payloads: list[dict]) -> None`，沿用现有超时、指数退避、HTTP 错误和飞书业务错误处理。

- [x] **Step 1: Write failing test**

在 `tests/test_feishu.py` 增加：

```python
def test_feishu_client_sends_post_payload():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request, json={"code": 0})

    client = FeishuClient(
        "https://example.com/hook",
        transport=httpx.MockTransport(handler),
        backoff_seconds=0,
    )
    client.send_posts([{
        "msg_type": "post",
        "content": {"post": {"zh_cn": {"title": "早报", "content": [[{"tag": "text", "text": "内容"}]]}}},
    }])

    assert len(requests) == 1
    assert requests[0].json()["msg_type"] == "post"
```

- [x] **Step 2: Run the focused test and confirm RED**

Run `python -m pytest tests/test_feishu.py::test_feishu_client_sends_post_payload -q`。Expected: FAIL，因为 `send_posts` 尚不存在。

- [x] **Step 3: Implement `send_posts` using one shared retry helper**

将当前 `send` 的重试循环抽取为接收 `payload: dict` 的内部方法；保留 `send(messages: list[str])`，继续包装为 `msg_type=text`，新增 `send_posts(payloads)` 传入 post payload。每次请求仍调用 `raise_for_status()`、解析 JSON，并检查 `code` 和 `StatusCode` 非零错误。

- [x] **Step 4: Run all Feishu tests and confirm GREEN**

Run `python -m pytest tests/test_feishu.py -q`。Expected: all Feishu mock tests pass，且没有真实网络请求。

---

### Task 3: 保存结构化 digest 并让 pipeline 使用 post 消息

**Files:**
- Modify: `src/ai_daily_digest/pipeline.py`
- Modify: `src/ai_daily_digest/cli.py` only if the pipeline interface requires an explicit digest path error
- Test: Create `tests/test_pipeline.py`

**Interfaces:**
- Adds `save_digest(digest: dict, path: Path) -> None` and `load_digest(path: Path) -> dict` in `pipeline.py`。
- `generate_pipeline` keeps returning Markdown `str` but also writes `data/latest_digest.json`。
- `send_pipeline` reads `latest_digest.json`, calls `format_feishu_posts`, and calls `FeishuClient.send_posts`。

- [x] **Step 1: Write failing pipeline tests**

创建 `tests/test_pipeline.py`，验证结构化文件保存和发送入口：

```python
from pathlib import Path

from ai_daily_digest.config import Settings
from ai_daily_digest.models import Article
from ai_daily_digest.pipeline import generate_pipeline, load_digest


def test_generate_pipeline_saves_markdown_and_structured_digest(tmp_path: Path):
    settings = Settings(data_dir=tmp_path)
    text = generate_pipeline(settings, articles=[], test_mode=True)

    assert text.startswith("# ")
    assert (tmp_path / "latest_digest.md").exists()
    assert load_digest(tmp_path / "latest_digest.json")["trend"]
```

为 `send_pipeline` 增加 mock `FeishuClient` 或注入 client 的测试，断言传给 `send_posts` 的第一个 payload 的 `msg_type` 为 `post`，并断言缺少 `latest_digest.json` 时提示重新生成。

- [x] **Step 2: Run pipeline tests and confirm RED**

Run `python -m pytest tests/test_pipeline.py -q`。Expected: FAIL，因为 digest JSON 保存和 post 发送入口尚不存在。

- [x] **Step 3: Implement JSON persistence and post dispatch**

在 `generate_pipeline` 获得最终 digest 后先调用 `save_digest`，再调用现有 `format_digest` 写 Markdown。`send_pipeline` 在 Webhook 校验后读取 JSON；不存在时抛出中文 `FileNotFoundError`，提示先运行 `generate`。将 `split_message` 替换为 `format_feishu_posts`，按 `settings.feishu_max_chars` 传入，并使用 `FeishuClient.send_posts`。

`run` 现有流程无需改变：先生成 JSON/Markdown，再由 `send_pipeline` 读取 JSON；`--dry-run` 在发送前返回，因此不会触发任何 Feishu client。

- [x] **Step 4: Run pipeline tests and confirm GREEN**

Run `python -m pytest tests/test_pipeline.py -q`。Expected: all new pipeline tests pass。

---

### Task 4: 更新文档、配置说明并做全量验证

**Files:**
- Modify: `README.md`
- Modify: `tests/test_formatter.py` only if final payload assertions need exact stable wording

- [x] **Step 1: Update README**

在飞书发送章节说明当前使用 `post` 富文本消息、标题/重点/链接的展示效果，并说明 `generate` 会同时写入 `latest_digest.md` 与 `latest_digest.json`；强调先用 `python -m ai_daily_digest run --dry-run`，确认后再运行 `python -m ai_daily_digest run` 或 `send`。

- [x] **Step 2: Run the full local verification**

Run:

```bash
source .venv/bin/activate
python -m pytest
python -m compileall -q src tests
python -m ai_daily_digest --help
python -m ai_daily_digest --test-mode run --dry-run
```

Expected: all tests pass，compileall 返回 0，dry-run 生成早报并记录未调用飞书。

- [x] **Step 3: Review staged files and commit implementation**

确认不包含 `.env`、`.venv`、`.DS_Store`、真实密钥或真实早报缓存，然后执行：

```bash
git add src/ai_daily_digest/formatter.py src/ai_daily_digest/feishu.py src/ai_daily_digest/pipeline.py tests/test_formatter.py tests/test_feishu.py tests/test_pipeline.py README.md
git commit -m "Improve Feishu digest formatting"
```

不执行真实 Webhook、RSS、模型调用或强制 push。
