"""Language detection using Google Gemini API.

This module detects the language of creative content (HTML, VAST, Native)
using Google's Gemini API to support geo-mismatch alerts.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


def get_gemini_api_key_sync(db_path: Optional[str] = None) -> Optional[str]:
    """Get Gemini API key from environment variable.

    Args:
        db_path: Deprecated, not used. Kept for backward compatibility.

    Returns:
        API key if configured, None otherwise.
    """
    # Environment variable is the only supported source
    return os.environ.get("GEMINI_API_KEY")


@dataclass
class LanguageDetectionResult:
    """Result of language detection analysis."""

    language: Optional[str] = None  # e.g., "German", "English"
    language_code: Optional[str] = None  # ISO 639-1: "de", "en"
    confidence: float = 0.0  # 0.0 to 1.0
    source: str = "gemini"  # "gemini" or "manual"
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Return True if detection was successful."""
        return self.language is not None and self.error is None


class GeminiLanguageAnalyzer:
    """Gemini-powered language detection for creative content."""

    def __init__(self, api_key: Optional[str] = None, db_path: Optional[str] = None):
        """Initialize the language analyzer.

        Args:
            api_key: Google Gemini API key. If not provided, checks database then env var.
            db_path: Path to database file to check for stored API key.
        """
        self.api_key = api_key or get_gemini_api_key_sync(db_path)
        self._client = None
        self._model = None

    @property
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)

    @property
    def model(self):
        """Lazy-load Gemini model."""
        if self._model is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY not configured")
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel("gemini-1.5-flash")
            except ImportError:
                raise ImportError(
                    "google-generativeai package not installed. "
                    "Run: pip install google-generativeai"
                )
        return self._model

    def extract_text_from_creative(self, raw_data: dict, creative_format: str) -> Optional[str]:
        """Extract analyzable text content from creative raw_data.

        Args:
            raw_data: The creative's raw_data dict containing format-specific content
            creative_format: Creative format (HTML, VIDEO, NATIVE)

        Returns:
            Extracted text content suitable for language detection, or None
        """
        if not raw_data:
            return None

        text_parts = []

        if creative_format == "HTML":
            html_data = raw_data.get("html", {})
            snippet = html_data.get("snippet", "")
            if snippet:
                # Strip HTML tags to get plain text
                text = self._strip_html_tags(snippet)
                if text:
                    text_parts.append(text)

        elif creative_format == "VIDEO":
            video_data = raw_data.get("video", {})
            vast_xml = video_data.get("vastXml", "")
            if vast_xml:
                # Extract text from VAST XML (ad title, description, etc.)
                text = self._extract_text_from_vast(vast_xml)
                if text:
                    text_parts.append(text)

        elif creative_format == "NATIVE":
            native_data = raw_data.get("native", {})
            # Extract all text fields from native ad
            for field in ["headline", "body", "callToAction", "advertiserName"]:
                value = native_data.get(field, "")
                if value:
                    text_parts.append(value)

        # Also check declared advertiser name
        advertiser = raw_data.get("advertiserName", "")
        if advertiser and advertiser not in text_parts:
            text_parts.append(advertiser)

        if not text_parts:
            return None

        return " ".join(text_parts)

    def _strip_html_tags(self, html: str) -> str:
        """Remove HTML tags and extract plain text."""
        # Remove script and style content
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        # Decode common HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_text_from_vast(self, vast_xml: str) -> str:
        """Extract text content from VAST XML."""
        text_parts = []

        # Look for AdTitle
        title_match = re.search(
            r'<AdTitle[^>]*>(?:<!\[CDATA\[)?([^\]<]+)',
            vast_xml,
            re.IGNORECASE
        )
        if title_match:
            text_parts.append(title_match.group(1).strip())

        # Look for Description
        desc_match = re.search(
            r'<Description[^>]*>(?:<!\[CDATA\[)?([^\]<]+)',
            vast_xml,
            re.IGNORECASE
        )
        if desc_match:
            text_parts.append(desc_match.group(1).strip())

        # Look for CompanionAds text
        companion_text = re.findall(
            r'<HTMLResource[^>]*>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</HTMLResource>',
            vast_xml,
            re.IGNORECASE | re.DOTALL
        )
        for html in companion_text:
            stripped = self._strip_html_tags(html)
            if stripped:
                text_parts.append(stripped)

        return " ".join(text_parts)

    def detect_language(
        self,
        text: str,
        timeout: float = 10.0,
    ) -> LanguageDetectionResult:
        """Detect the language of the given text using Gemini.

        Args:
            text: Text content to analyze
            timeout: Request timeout in seconds

        Returns:
            LanguageDetectionResult with detected language or error
        """
        if not text or len(text.strip()) < 3:
            return LanguageDetectionResult(
                error="Insufficient text content for language detection"
            )

        if not self.is_configured:
            return LanguageDetectionResult(
                error="GEMINI_API_KEY not configured"
            )

        # Truncate very long text to avoid unnecessary API costs
        max_chars = 1000
        if len(text) > max_chars:
            text = text[:max_chars]

        prompt = f"""Analyze the following advertising creative text and detect its primary language.

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

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,  # Low temperature for consistent results
                    "max_output_tokens": 100,
                }
            )

            result_text = response.text.strip()
            return self._parse_response(result_text)

        except Exception as e:
            logger.error(f"Gemini API error during language detection: {e}")
            return LanguageDetectionResult(error=str(e))

    def _parse_response(self, text: str) -> LanguageDetectionResult:
        """Parse JSON response from Gemini."""
        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        try:
            data = json.loads(text.strip())

            language = data.get("language")
            language_code = data.get("language_code")
            confidence = float(data.get("confidence", 0.0))

            # Validate confidence range
            confidence = max(0.0, min(1.0, confidence))

            if not language or not language_code:
                return LanguageDetectionResult(
                    error="Could not determine language from content"
                )

            return LanguageDetectionResult(
                language=language,
                language_code=language_code.lower(),
                confidence=confidence,
                source="gemini",
            )

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            logger.debug(f"Response text: {text[:200]}")
            return LanguageDetectionResult(
                error=f"Failed to parse API response: {e}"
            )

    async def analyze_creative(
        self,
        creative_id: str,
        raw_data: dict,
        creative_format: str,
    ) -> LanguageDetectionResult:
        """Analyze a creative and detect its language.

        This is a convenience method that extracts text and runs detection.

        Args:
            creative_id: Creative ID for logging
            raw_data: Creative's raw_data dict
            creative_format: Creative format (HTML, VIDEO, NATIVE)

        Returns:
            LanguageDetectionResult with detection results
        """
        text = self.extract_text_from_creative(raw_data, creative_format)

        if not text:
            return LanguageDetectionResult(
                error=f"No text content found in {creative_format} creative"
            )

        logger.debug(f"Analyzing language for creative {creative_id}: {text[:100]}...")

        return self.detect_language(text)


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
