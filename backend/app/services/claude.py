"""Claude API service — same model and pattern as the Telegram bot's joe.py."""

from __future__ import annotations

import json
import re

import anthropic

from app import config

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def call_claude(system_prompt: str, user_message: str, max_tokens: int = 4096) -> str:
    client = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def call_claude_json(system_prompt: str, user_message: str, max_tokens: int = 4096) -> dict:
    """Call Claude and parse response as JSON, stripping markdown fences if present."""
    raw = call_claude(system_prompt, user_message, max_tokens)
    return parse_json_response(raw)


def parse_json_response(raw: str) -> dict:
    """Extract JSON from Claude response, handling markdown fences."""
    text = raw.strip()
    # Strip ```json ... ``` or ``` ... ```
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    return json.loads(text)
