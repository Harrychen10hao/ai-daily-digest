from __future__ import annotations

import logging
import time

import httpx

from .formatter import split_message

logger = logging.getLogger(__name__)


class FeishuSendError(RuntimeError):
    pass


class FeishuClient:
    def __init__(self, webhook_url: str, timeout: float = 20.0, retries: int = 2, backoff_seconds: float = 0.5, transport: httpx.BaseTransport | None = None):
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.retries = retries
        self.backoff_seconds = backoff_seconds
        self.client = httpx.Client(timeout=timeout, transport=transport)

    def close(self) -> None:
        self.client.close()

    def send(self, messages: list[str]) -> None:
        for index, message in enumerate(messages, start=1):
            last_error: Exception | None = None
            for attempt in range(self.retries + 1):
                try:
                    response = self.client.post(self.webhook_url, json={"msg_type": "text", "content": {"text": message}})
                    response.raise_for_status()
                    payload = response.json()
                    if payload.get("code", 0) not in (0, None) or payload.get("StatusCode", 0) not in (0, None):
                        raise FeishuSendError(f"飞书返回错误: {payload}")
                    logger.info("飞书消息发送成功 (%d/%d)", index, len(messages))
                    break
                except (httpx.HTTPError, ValueError, FeishuSendError) as exc:
                    last_error = exc
                    logger.warning("飞书消息发送失败 (%d/%d)，第 %d 次: %s", index, len(messages), attempt + 1, exc)
                    if attempt < self.retries:
                        time.sleep(self.backoff_seconds * (2**attempt))
            else:
                raise FeishuSendError(f"飞书消息发送失败 (%d/%d): %s" % (index, len(messages), last_error)) from last_error
