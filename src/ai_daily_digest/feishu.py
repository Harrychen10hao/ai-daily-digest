from __future__ import annotations

import logging
import time
from typing import Any

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
        payloads = [
            {"msg_type": "text", "content": {"text": message}}
            for message in messages
        ]
        self._send_payloads(payloads)

    def send_posts(self, payloads: list[dict[str, Any]]) -> None:
        self._send_payloads(payloads)

    def _send_payloads(self, payloads: list[dict[str, Any]]) -> None:
        for index, payload in enumerate(payloads, start=1):
            last_error: Exception | None = None
            for attempt in range(self.retries + 1):
                try:
                    response = self.client.post(self.webhook_url, json=payload)
                    response.raise_for_status()
                    response_payload = response.json()
                    if response_payload.get("code", 0) not in (0, None) or response_payload.get("StatusCode", 0) not in (0, None):
                        raise FeishuSendError(f"飞书返回错误: {response_payload}")
                    logger.info("飞书消息发送成功 (%d/%d)", index, len(payloads))
                    break
                except (httpx.HTTPError, ValueError, FeishuSendError) as exc:
                    last_error = exc
                    logger.warning("飞书消息发送失败 (%d/%d)，第 %d 次: %s", index, len(payloads), attempt + 1, exc)
                    if attempt < self.retries:
                        time.sleep(self.backoff_seconds * (2**attempt))
            else:
                raise FeishuSendError(f"飞书消息发送失败 (%d/%d): %s" % (index, len(payloads), last_error)) from last_error
