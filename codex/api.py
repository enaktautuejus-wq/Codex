from __future__ import annotations
import json
import urllib.error
import urllib.request
from typing import Any

class APIError(RuntimeError):
    pass

def post_json(endpoint: str, api_key: str, payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Codex-Termux-Agent/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
            message = parsed.get("error", {}).get("message") or parsed.get("message") or body
        except json.JSONDecodeError:
            message = body or str(exc.reason)
        raise APIError(f"HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise APIError(f"Koneksi gagal: {exc.reason}") from exc
    except TimeoutError as exc:
        raise APIError("Request timeout.") from exc

def extract_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return "[Respons API tidak memiliki choices.]"
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "".join(parts)
    return str(content or "")
