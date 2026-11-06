"""Look at a picture with the image model chosen in Settings. The main model reads text only, so when a task needs a picture it calls
`look_at_image`, which sends the file to this model (any chat model that accepts images, on an OpenAI-compatible endpoint) and returns
the text answer. The image itself never goes into the main model's context."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import httpx

MAX_BYTES = 8_000_000  # a larger picture is refused rather than sent
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def describe(base_url: str, api_key: str, model: str, path: Path, question: str, timeout: float = 180) -> str:
    """The image model's answer about one picture. Raises RuntimeError with a readable message when it cannot be done."""
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        raise RuntimeError("This is not a picture file (use png, jpg, gif or webp).")
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise RuntimeError(f"The picture is too large ({size // 1_000_000} MB; the limit is {MAX_BYTES // 1_000_000} MB).")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    url = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
    body = {
        "model": model,
        "stream": False,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": question.strip() or "Describe this picture in detail, including any labels, numbers and axis titles."},
                {"type": "image_url", "image_url": {"url": url}},
            ],
        }],
    }
    try:
        r = httpx.post(base_url.rstrip("/") + "/chat/completions", json=body, timeout=timeout,
                       headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    except httpx.HTTPError as e:
        raise RuntimeError(f"The image model could not be reached ({type(e).__name__}).") from e
    if r.status_code >= 400:
        raise RuntimeError(f"The image model refused the picture ({r.status_code}): {r.text[:200]}")
    try:
        content = r.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise RuntimeError("The image model returned an answer in an unexpected form.") from e
    text = content if isinstance(content, str) else str(content or "")
    return text.strip() or "The image model gave no answer."
