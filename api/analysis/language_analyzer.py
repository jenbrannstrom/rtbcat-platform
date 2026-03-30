"""Language detection using configurable AI providers.

Supports Gemini, Claude, and Grok for creative language detection.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from services.gemini_client import generate_gemini_content
from services.language_ai_config import (
    get_provider_env_key,
    normalize_language_ai_provider,
)
from services.secrets_manager import get_secrets_manager

logger = logging.getLogger(__name__)


def get_provider_api_key_sync(
    provider: str = "gemini",
    db_path: Optional[str] = None,  # kept for backward compatibility
) -> Optional[str]:
    """Get provider API key from configured secrets backend/env."""
    del db_path  # compatibility no-op
    env_key = get_provider_env_key(provider)
    return get_secrets_manager().get(env_key)


def get_gemini_api_key_sync(db_path: Optional[str] = None) -> Optional[str]:
    """Backward-compatible helper for legacy callers."""
    return get_provider_api_key_sync("gemini", db_path=db_path)


@dataclass
class LanguageDetectionResult:
    """Result of language detection analysis."""

    language: Optional[str] = None  # e.g., "German", "English"
    language_code: Optional[str] = None  # ISO 639-1: "de", "en"
    confidence: float = 0.0  # 0.0 to 1.0
    source: str = "gemini"  # gemini/claude/grok/manual
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Return True if detection was successful."""
        return self.language is not None and self.error is None


class LanguageAnalyzer:
    """Provider-agnostic language detection for creative content."""

    def __init__(
        self,
        provider: str = "gemini",
        api_key: Optional[str] = None,
        db_path: Optional[str] = None,
    ) -> None:
        self.provider = normalize_language_ai_provider(provider)
        self.api_key = api_key or get_provider_api_key_sync(self.provider, db_path)

    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)

    def extract_text_from_creative(
        self,
        raw_data: dict,
        creative_format: str,
    ) -> Optional[str]:
        """Extract analyzable text content from creative raw_data."""
        if not raw_data:
            return None

        text_parts: list[str] = []

        if creative_format == "HTML":
            html_data = raw_data.get("html", {})
            snippet = html_data.get("snippet", "")
            if snippet:
                text = self._strip_html_tags(snippet)
                if text:
                    text_parts.append(text)

        elif creative_format == "VIDEO":
            video_data = raw_data.get("video", {})
            vast_xml = video_data.get("vastXml", "")
            if vast_xml:
                text = self._extract_text_from_vast(vast_xml)
                if text:
                    text_parts.append(text)

        elif creative_format == "NATIVE":
            native_data = raw_data.get("native", {})
            for field in ["headline", "body", "callToAction", "advertiserName"]:
                value = native_data.get(field, "")
                if value:
                    text_parts.append(value)

        advertiser = raw_data.get("advertiserName", "")
        if advertiser and advertiser not in text_parts:
            text_parts.append(advertiser)

        if not text_parts:
            return None
        return " ".join(text_parts)

    def _strip_html_tags(self, html: str) -> str:
        """Remove HTML tags and extract plain text."""
        html = re.sub(
            r"<script[^>]*>.*?</script>",
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        html = re.sub(
            r"<style[^>]*>.*?</style>",
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        text = re.sub(r"<[^>]+>", " ", html)
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _extract_text_from_vast(self, vast_xml: str) -> str:
        """Extract text content from VAST XML."""
        text_parts: list[str] = []

        title_match = re.search(
            r"<AdTitle[^>]*>(?:<!\[CDATA\[)?([^\]<]+)",
            vast_xml,
            re.IGNORECASE,
        )
        if title_match:
            text_parts.append(title_match.group(1).strip())

        desc_match = re.search(
            r"<Description[^>]*>(?:<!\[CDATA\[)?([^\]<]+)",
            vast_xml,
            re.IGNORECASE,
        )
        if desc_match:
            text_parts.append(desc_match.group(1).strip())

        companion_text = re.findall(
            r"<HTMLResource[^>]*>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</HTMLResource>",
            vast_xml,
            re.IGNORECASE | re.DOTALL,
        )
        for html in companion_text:
            stripped = self._strip_html_tags(html)
            if stripped:
                text_parts.append(stripped)

        return " ".join(text_parts)

    def detect_language(
        self,
        text: str,
        timeout: float = 12.0,
    ) -> LanguageDetectionResult:
        """Detect language using selected provider."""
        if not text or len(text.strip()) < 3:
            return LanguageDetectionResult(
                source=self.provider,
                error="Insufficient text content for language detection",
            )

        if not self.is_configured:
            return LanguageDetectionResult(
                source=self.provider,
                error=f"{self.provider.capitalize()} API key not configured",
            )

        max_chars = 1000
        if len(text) > max_chars:
            text = text[:max_chars]

        prompt = self._build_prompt(text)

        try:
            if self.provider == "gemini":
                return self._detect_with_gemini(prompt, timeout=timeout)
            if self.provider == "claude":
                return self._detect_with_claude(prompt, timeout=timeout)
            if self.provider == "grok":
                return self._detect_with_grok(prompt, timeout=timeout)
            return LanguageDetectionResult(
                source=self.provider,
                error=f"Unsupported language AI provider: {self.provider}",
            )
        except Exception as exc:
            logger.error(
                "Provider error during language detection (%s): %s",
                self.provider,
                exc,
            )
            return LanguageDetectionResult(source=self.provider, error=str(exc))

    def _build_prompt(self, text: str) -> str:
        return f"""Analyze the following advertising creative text and detect its primary language.

Text to analyze:
"{text}"

Respond ONLY with valid JSON in this exact format:
{{
  "language": "English",
  "language_code": "en",
  "confidence": 0.95
}}

Rules:
- "language" should be the full English name of the language (e.g., "German", "French", "Spanish")
- "language_code" should be the ISO 639-1 two-letter code (e.g., "de", "fr", "es")
- "confidence" should be between 0.0 and 1.0
- If the text is too short or ambiguous, set confidence below 0.5
- If you cannot determine the language, respond with: {{"language": null, "language_code": null, "confidence": 0.0}}
"""

    def _detect_with_gemini(
        self,
        prompt: str,
        timeout: float,
    ) -> LanguageDetectionResult:
        response_text = generate_gemini_content(
            prompt,
            self.api_key or "",
            temperature=0.1,
            max_output_tokens=100,
            timeout=timeout,
        )
        return self._parse_response(response_text)

    def _detect_with_claude(
        self,
        prompt: str,
        timeout: float,
    ) -> LanguageDetectionResult:
        model = os.getenv("CATSCAN_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        payload = {
            "model": model,
            "max_tokens": 200,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        response_data = self._post_json(
            url="https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key or "",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            payload=payload,
            timeout=timeout,
        )
        text = self._extract_claude_text(response_data)
        return self._parse_response(text)

    def _detect_with_grok(
        self,
        prompt: str,
        timeout: float,
    ) -> LanguageDetectionResult:
        model = os.getenv("CATSCAN_GROK_MODEL", "grok-2-latest")
        payload = {
            "model": model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a language detection engine. "
                        "Return only valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        response_data = self._post_json(
            url="https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload=payload,
            timeout=timeout,
        )
        text = self._extract_grok_text(response_data)
        return self._parse_response(text)

    @staticmethod
    def _post_json(
        url: str,
        headers: dict[str, str],
        payload: dict,
        timeout: float,
    ) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code}: {body[:500]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Provider request failed: {exc}") from exc

    @staticmethod
    def _extract_claude_text(response_data: dict) -> str:
        content = response_data.get("content", [])
        for block in content:
            if block.get("type") == "text" and block.get("text"):
                return str(block["text"]).strip()
        raise RuntimeError("Claude response did not contain text content")

    @staticmethod
    def _extract_grok_text(response_data: dict) -> str:
        choices = response_data.get("choices", [])
        if not choices:
            raise RuntimeError("Grok response did not contain choices")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise RuntimeError("Grok response message content is empty")
        return str(content).strip()

    def _parse_response(self, text: str) -> LanguageDetectionResult:
        """Parse JSON response from provider."""
        if "```json" in text:
            text = text.split("```json", maxsplit=1)[1].split("```", maxsplit=1)[0]
        elif "```" in text:
            text = text.split("```", maxsplit=1)[1].split("```", maxsplit=1)[0]

        try:
            data = json.loads(text.strip())
            language = data.get("language")
            language_code = data.get("language_code")
            confidence = float(data.get("confidence", 0.0))
            confidence = max(0.0, min(1.0, confidence))

            if not language or not language_code:
                return LanguageDetectionResult(
                    source=self.provider,
                    error="Could not determine language from content",
                )

            return LanguageDetectionResult(
                language=language,
                language_code=str(language_code).lower(),
                confidence=confidence,
                source=self.provider,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Failed to parse %s response: %s", self.provider, exc)
            logger.debug("Response text: %s", text[:200])
            return LanguageDetectionResult(
                source=self.provider,
                error=f"Failed to parse API response: {exc}",
            )

    def _resolve_image_for_creative(
        self,
        creative_id: str,
        raw_data: dict,
        creative_format: str,
    ) -> Optional[str]:
        """Find an image source (local path or URL) for vision-based detection."""
        if creative_format == "VIDEO":
            thumb = Path.home() / ".catscan" / "thumbnails" / f"{creative_id}.jpg"
            if thumb.exists():
                return str(thumb)

        if creative_format == "HTML":
            snippet = (raw_data.get("html") or {}).get("snippet", "")
            if snippet:
                from utils.html_thumbnail import extract_image_urls_from_html
                urls = extract_image_urls_from_html(snippet)
                if urls:
                    return urls[0]

        if creative_format == "IMAGE":
            image_data = raw_data.get("image", {})
            if isinstance(image_data, dict):
                url = image_data.get("url", "")
                if url and url.startswith("http"):
                    return url

        return None

    @staticmethod
    def _load_image_base64(source: str) -> Optional[tuple[str, str]]:
        """Load image from local path or URL, return (media_type, base64_data)."""
        try:
            if source.startswith("http"):
                req = urllib.request.Request(source, headers={"User-Agent": "CatScan/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read(5 * 1024 * 1024)  # 5MB cap
                    content_type = resp.headers.get("Content-Type", "image/jpeg")
                    media_type = content_type.split(";")[0].strip()
            else:
                path = Path(source)
                if not path.exists():
                    return None
                data = path.read_bytes()
                ext = path.suffix.lower()
                media_type = {"jpg": "image/jpeg", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}.get(ext, "image/jpeg")
            return media_type, base64.b64encode(data).decode("ascii")
        except Exception as exc:
            logger.debug("Failed to load image %s: %s", source, exc)
            return None

    def _build_vision_prompt(self) -> str:
        return """Analyze this advertising creative image and detect the primary language of any visible text.

Respond ONLY with valid JSON in this exact format:
{
  "language": "English",
  "language_code": "en",
  "confidence": 0.95
}

Rules:
- "language" should be the full English name of the language (e.g., "German", "French", "Spanish")
- "language_code" should be the ISO 639-1 two-letter code (e.g., "de", "fr", "es")
- "confidence" should be between 0.0 and 1.0
- If you cannot see any text in the image, respond with: {"language": null, "language_code": null, "confidence": 0.0}
"""

    def detect_language_from_image(
        self,
        image_source: str,
        timeout: float = 15.0,
    ) -> LanguageDetectionResult:
        """Detect language from an image using vision API."""
        if not self.is_configured:
            return LanguageDetectionResult(
                source=self.provider,
                error=f"{self.provider.capitalize()} API key not configured",
            )

        img = self._load_image_base64(image_source)
        if not img:
            return LanguageDetectionResult(
                source=self.provider,
                error="Could not load image for vision analysis",
            )
        media_type, b64_data = img
        prompt = self._build_vision_prompt()

        try:
            if self.provider == "claude":
                return self._detect_vision_claude(prompt, media_type, b64_data, timeout)
            if self.provider == "gemini":
                return self._detect_vision_gemini(prompt, media_type, b64_data, timeout)
            if self.provider == "grok":
                return self._detect_vision_grok(prompt, media_type, b64_data, timeout)
            return LanguageDetectionResult(
                source=self.provider,
                error=f"Vision not supported for provider: {self.provider}",
            )
        except Exception as exc:
            logger.error("Vision detection error (%s): %s", self.provider, exc)
            return LanguageDetectionResult(source=self.provider, error=str(exc))

    def _detect_vision_claude(self, prompt: str, media_type: str, b64_data: str, timeout: float) -> LanguageDetectionResult:
        model = os.getenv("CATSCAN_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        payload = {
            "model": model,
            "max_tokens": 200,
            "temperature": 0,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64_data}},
                    {"type": "text", "text": prompt},
                ],
            }],
        }
        response_data = self._post_json(
            url="https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.api_key or "", "anthropic-version": "2023-06-01", "content-type": "application/json"},
            payload=payload,
            timeout=timeout,
        )
        text = self._extract_claude_text(response_data)
        result = self._parse_response(text)
        if result.source:
            result.source = f"{self.provider}_vision"
        return result

    def _detect_vision_gemini(self, prompt: str, media_type: str, b64_data: str, timeout: float) -> LanguageDetectionResult:
        payload = {
            "contents": [{"parts": [
                {"inline_data": {"mime_type": media_type, "data": b64_data}},
                {"text": prompt},
            ]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 200},
        }
        model = os.getenv("CATSCAN_GEMINI_MODEL", "gemini-2.0-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
        response_data = self._post_json(url=url, headers={"Content-Type": "application/json"}, payload=payload, timeout=timeout)
        candidates = response_data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini vision returned no candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = parts[0].get("text", "") if parts else ""
        result = self._parse_response(text)
        if result.source:
            result.source = f"{self.provider}_vision"
        return result

    def _detect_vision_grok(self, prompt: str, media_type: str, b64_data: str, timeout: float) -> LanguageDetectionResult:
        model = os.getenv("CATSCAN_GROK_MODEL", "grok-2-latest")
        data_url = f"data:{media_type};base64,{b64_data}"
        payload = {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": "You are a language detection engine. Return only valid JSON."},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ]},
            ],
        }
        response_data = self._post_json(
            url="https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            payload=payload,
            timeout=timeout,
        )
        text = self._extract_grok_text(response_data)
        result = self._parse_response(text)
        if result.source:
            result.source = f"{self.provider}_vision"
        return result

    async def analyze_creative(
        self,
        creative_id: str,
        raw_data: dict,
        creative_format: str,
    ) -> LanguageDetectionResult:
        """Analyze a creative and detect its language.

        Tries text extraction first, falls back to vision-based detection
        when text content is insufficient (common for image-based HTML ads
        and video creatives).
        """
        text = self.extract_text_from_creative(raw_data, creative_format)

        if text:
            logger.debug("Analyzing language for creative %s with %s (text)", creative_id, self.provider)
            result = self.detect_language(text)
            if result.success:
                return result

        # Vision fallback: use thumbnail or extracted image URL
        image_source = self._resolve_image_for_creative(creative_id, raw_data, creative_format)
        if image_source:
            logger.debug("Falling back to vision for creative %s with %s", creative_id, self.provider)
            result = self.detect_language_from_image(image_source)
            if result.success:
                return result

        return LanguageDetectionResult(
            source=self.provider,
            error=f"No text or image content found in {creative_format} creative",
        )


# Backward-compatible alias used by existing imports.
GeminiLanguageAnalyzer = LanguageAnalyzer


# ISO 639-1 language codes with English names
LANGUAGE_CODES = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "hi": "Hindi",
    "tr": "Turkish",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "ms": "Malay",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "fi": "Finnish",
    "cs": "Czech",
    "el": "Greek",
    "he": "Hebrew",
    "hu": "Hungarian",
    "ro": "Romanian",
    "uk": "Ukrainian",
}


def get_language_name(code: str) -> str:
    """Get the English name for a language code."""
    return LANGUAGE_CODES.get(code.lower(), code.upper())
