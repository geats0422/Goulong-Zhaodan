from __future__ import annotations

from typing import Any

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

import main


def _request(messages: list[dict[str, Any]]) -> Request:
    async def receive() -> dict[str, Any]:
        return messages.pop(0)

    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/test",
            "raw_path": b"/test",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
        },
        receive,
    )


async def _consume_body(request: Request) -> JSONResponse:
    body = b""
    async for chunk in request.stream():
        body += chunk
    return JSONResponse({"size": len(body)})


@pytest.mark.asyncio
async def test_max_body_size_rejects_invalid_content_length() -> None:
    request = _request([])
    request.scope["headers"] = [(b"content-length", b"not-a-number")]
    called = False

    async def call_next(_: Request) -> JSONResponse:
        nonlocal called
        called = True
        return JSONResponse({})

    response = await main.max_body_size_middleware(request, call_next)

    assert response.status_code == 400
    assert called is False


@pytest.mark.asyncio
async def test_max_body_size_rejects_declared_oversize_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "_MAX_CONTENT_LENGTH", 5)
    request = _request([])
    request.scope["headers"] = [(b"content-length", b"6")]
    called = False

    async def call_next(_: Request) -> JSONResponse:
        nonlocal called
        called = True
        return JSONResponse({})

    response = await main.max_body_size_middleware(request, call_next)

    assert response.status_code == 413
    assert called is False


@pytest.mark.asyncio
async def test_max_body_size_stops_stream_when_received_body_exceeds_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "_MAX_CONTENT_LENGTH", 5)
    messages = [
        {"type": "http.request", "body": b"hello", "more_body": True},
        {"type": "http.request", "body": b"!", "more_body": True},
        {"type": "http.request", "body": b"unread", "more_body": False},
    ]
    request = _request(messages)

    response = await main.max_body_size_middleware(request, _consume_body)

    assert response.status_code == 413
    assert len(messages) == 1


@pytest.mark.asyncio
async def test_max_body_size_allows_normal_streamed_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "_MAX_CONTENT_LENGTH", 5)
    request = _request(
        [
            {"type": "http.request", "body": b"he", "more_body": True},
            {"type": "http.request", "body": b"llo", "more_body": False},
        ]
    )

    response = await main.max_body_size_middleware(request, _consume_body)

    assert response.status_code == 200
    assert response.body == b'{"size":5}'
