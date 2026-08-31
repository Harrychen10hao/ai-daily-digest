from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .config import Settings
from .models import Article
from .pipeline import fetch_pipeline, generate_pipeline, load_articles, save_articles, send_pipeline

logger = logging.getLogger("ai_daily_digest")


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")


def _fixture_articles(path: Path) -> list[Article]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Article.from_dict(item) for item in payload]


def _test_fixture_path() -> Path:
    return Path(__file__).resolve().parents[2] / "fixtures" / "sample_articles.json"


def cmd_fetch(settings: Settings, test_mode: bool = False) -> int:
    if test_mode:
        articles = _fixture_articles(_test_fixture_path())
        save_articles(articles, settings.data_dir / "latest_articles.json")
        logger.info("测试模式：保存 %d 条样例文章", len(articles))
    else:
        fetch_pipeline(settings)
    return 0


def cmd_generate(settings: Settings, test_mode: bool = False) -> int:
    text = generate_pipeline(settings, test_mode=test_mode)
    print(text)
    return 0


def cmd_send(settings: Settings) -> int:
    send_pipeline(settings)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI 产品与 UX 科技早报工具")
    parser.add_argument("--test-mode", action="store_true", help="使用本地样例数据并跳过模型调用")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("fetch", help="抓取并保存文章")
    subparsers.add_parser("generate", help="生成并保存早报")
    subparsers.add_parser("send", help="发送已生成的早报")
    run_parser = subparsers.add_parser("run", help="执行抓取、生成和发送")
    run_parser.add_argument("--dry-run", action="store_true", help="只生成早报，不发送飞书")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    try:
        if args.command == "fetch":
            return cmd_fetch(settings, args.test_mode)
        if args.command == "generate":
            return cmd_generate(settings, args.test_mode)
        if args.command == "send":
            return cmd_send(settings)
        if args.command == "run":
            cmd_fetch(settings, args.test_mode)
            text = generate_pipeline(settings, test_mode=args.test_mode)
            print(text)
            if args.dry_run:
                logger.info("dry-run：未调用飞书 Webhook")
                return 0
            send_pipeline(settings, text)
            return 0
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 2
    except Exception as exc:
        logger.exception("任务失败: %s", exc)
        return 1
    return 2
