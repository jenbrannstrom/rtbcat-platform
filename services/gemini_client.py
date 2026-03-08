"""Shared Gemini helpers built on the maintained google-genai SDK."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Optional


DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


def get_gemini_model_name() -> str:
    """Return the configured Gemini model name."""
    return os.getenv("CATSCAN_GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()


def generate_gemini_content(
    prompt: str,
    api_key: str,
    *,
    image_paths: Optional[list[str]] = None,
    temperature: float = 0.1,
    max_output_tokens: int = 100,
    timeout: Optional[float] = None,
) -> str:
    """Generate Gemini output from text plus optional local images."""
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise ImportError(
            "google-genai package not installed. "
            "Run: pip install -r requirements-ai.txt"
        ) from exc

    contents: list[object] = [prompt]
    for image_path in image_paths or []:
        path = Path(image_path)
        contents.append(
            types.Part.from_bytes(
                data=path.read_bytes(),
                mime_type=mimetypes.guess_type(path.name)[0] or "image/png",
            )
        )

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=max(1, int(timeout)))
        if timeout
        else None,
    )
    response = client.models.generate_content(
        model=get_gemini_model_name(),
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=temperature,
            maxOutputTokens=max_output_tokens,
        ),
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini response did not contain text content")
    return str(text).strip()
