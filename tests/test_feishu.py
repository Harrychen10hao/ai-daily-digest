import json

import httpx

from ai_daily_digest.feishu import FeishuClient, split_message


def test_split_message_never_returns_empty_chunks():
    assert split_message("abc", max_chars=2) == ["ab", "c"]


def test_feishu_client_retries_after_transient_error():
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if len(attempts) == 1:
            return httpx.Response(500, request=request, text="temporary")
        return httpx.Response(200, request=request, json={"code": 0})

    client = FeishuClient("https://example.com/hook", transport=httpx.MockTransport(handler), backoff_seconds=0)
    client.send(["早报"])
    assert len(attempts) == 2


def test_feishu_client_sends_interactive_card_payload():
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
        "msg_type": "interactive",
        "card": {"config": {"wide_screen_mode": True}, "elements": [{"tag": "hr"}]},
    }])

    assert len(requests) == 1
    assert json.loads(requests[0].content)["msg_type"] == "interactive"
