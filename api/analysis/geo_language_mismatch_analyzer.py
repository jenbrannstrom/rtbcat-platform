"""Geo-linguistic mismatch analysis using configurable AI providers.

Analyzes creative content (text, OCR, images) against serving countries to detect
language/currency/cultural mismatches that indicate waste.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from services.language_ai_config import normalize_language_ai_provider
from services.secrets_manager import get_secrets_manager

logger = logging.getLogger(__name__)


@dataclass
class GeoLinguisticFinding:
    """A single mismatch finding."""

    category: str  # language_mismatch, currency_mismatch, cultural_mismatch
    severity: str  # high, medium, low
    description: str
    evidence: str = ""


@dataclass
class GeoLinguisticAnalysisResult:
    """Full result of a geo-linguistic analysis."""

    primary_languages: list[str] = field(default_factory=list)
    secondary_languages: list[str] = field(default_factory=list)
    detected_currencies: list[str] = field(default_factory=list)
    findings: list[GeoLinguisticFinding] = field(default_factory=list)
    risk_score: float = 0.0  # 0.0 (no risk) to 1.0 (definite mismatch)
    decision: str = "match"  # match, mismatch, needs_review
    confidence: float = 0.0
    raw_response: str = ""
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict:
        return {
            "primary_languages": self.primary_languages,
            "secondary_languages": self.secondary_languages,
            "detected_currencies": self.detected_currencies,
            "findings": [
                {
                    "category": f.category,
                    "severity": f.severity,
                    "description": f.description,
                    "evidence": f.evidence,
                }
                for f in self.findings
            ],
            "risk_score": self.risk_score,
            "decision": self.decision,
            "confidence": self.confidence,
            "error": self.error,
        }


class GeoLinguisticAnalyzer:
    """Provider-agnostic geo-linguistic mismatch detection."""

    def __init__(
        self,
        provider: str = "gemini",
        api_key: Optional[str] = None,
    ) -> None:
        self.provider = normalize_language_ai_provider(provider)
        if api_key:
            self.api_key = api_key
        else:
            if self.provider == "gemini":
                self.api_key = get_secrets_manager().get("GEMINI_API_KEY")
            elif self.provider == "claude":
                self.api_key = get_secrets_manager().get("ANTHROPIC_API_KEY")
            else:
                self.api_key = get_secrets_manager().get("XAI_API_KEY")
        self._model = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def model(self):
        """Lazy-load Gemini model."""
        if self.provider != "gemini":
            raise ValueError(f"{self.provider} does not use local Gemini SDK model")
        if self._model is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY not configured")
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel("gemini-1.5-flash")
        return self._model

    def analyze(
        self,
        serving_countries: list[str],
        text_content: str = "",
        ocr_texts: list[str] | None = None,
        image_paths: list[str] | None = None,
        creative_metadata: dict | None = None,
        timeout: float = 30.0,
    ) -> GeoLinguisticAnalysisResult:
        """Analyze creative content for geo-linguistic mismatches."""
        if not self.is_configured:
            return GeoLinguisticAnalysisResult(
                error=f"{self.provider.capitalize()} API not configured",
                decision="needs_review",
            )

        if not text_content and not ocr_texts and not image_paths:
            return GeoLinguisticAnalysisResult(
                error="No content to analyze",
                decision="needs_review",
            )

        prompt = self._build_prompt(
            serving_countries,
            text_content,
            ocr_texts or [],
            creative_metadata or {},
        )

        try:
            if self.provider == "gemini":
                response_text = self._analyze_with_gemini(prompt, image_paths, timeout)
            elif self.provider == "claude":
                response_text = self._analyze_with_claude(prompt, image_paths, timeout)
            elif self.provider == "grok":
                response_text = self._analyze_with_grok(prompt, image_paths, timeout)
            else:
                return GeoLinguisticAnalysisResult(
                    error=f"Unsupported provider: {self.provider}",
                    decision="needs_review",
                )

            return self._parse_response(response_text, serving_countries)

        except Exception as exc:
            logger.error("Geo-linguistic analysis failed (%s): %s", self.provider, exc)
            return GeoLinguisticAnalysisResult(
                error=str(exc),
                decision="needs_review",
            )

    def _analyze_with_gemini(
        self,
        prompt: str,
        image_paths: list[str] | None,
        timeout: float,
    ) -> str:
        content_parts: list = [prompt]
        if image_paths:
            try:
                import PIL.Image

                for path in image_paths[:4]:
                    try:
                        img = PIL.Image.open(path)
                        content_parts.append(img)
                    except Exception as exc:
                        logger.debug("Skipping image %s: %s", path, exc)
            except ImportError:
                logger.debug("PIL not available, skipping image analysis")

        response = self.model.generate_content(
            content_parts,
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 1500,
            },
            request_options={"timeout": timeout},
        )
        return str(getattr(response, "text", "")).strip()

    def _analyze_with_claude(
        self,
        prompt: str,
        image_paths: list[str] | None,
        timeout: float,
    ) -> str:
        model = os.getenv("CATSCAN_CLAUDE_MODEL", "claude-3-5-sonnet-latest")
        content: list[dict] = [{"type": "text", "text": prompt}]
        for image in (image_paths or [])[:4]:
            encoded = self._load_image_base64(image)
            if not encoded:
                continue
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": encoded["media_type"],
                        "data": encoded["data"],
                    },
                }
            )

        payload = {
            "model": model,
            "max_tokens": 1500,
            "temperature": 0,
            "messages": [{"role": "user", "content": content}],
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
        content_blocks = response_data.get("content", [])
        for block in content_blocks:
            if block.get("type") == "text" and block.get("text"):
                return str(block["text"]).strip()
        raise RuntimeError("Claude response did not contain text content")

    def _analyze_with_grok(
        self,
        prompt: str,
        image_paths: list[str] | None,
        timeout: float,
    ) -> str:
        model = os.getenv("CATSCAN_GROK_MODEL", "grok-2-latest")
        content: list[dict] = [{"type": "text", "text": prompt}]
        for image in (image_paths or [])[:4]:
            encoded = self._load_image_base64(image)
            if not encoded:
                continue
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": (
                            f"data:{encoded['media_type']};base64,{encoded['data']}"
                        )
                    },
                }
            )

        payload = {
            "model": model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an ad geo-linguistic mismatch analyzer. "
                        "Return only valid JSON."
                    ),
                },
                {"role": "user", "content": content},
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
        choices = response_data.get("choices", [])
        if not choices:
            raise RuntimeError("Grok response did not contain choices")
        message = choices[0].get("message", {})
        response_content = message.get("content")
        if isinstance(response_content, str):
            return response_content.strip()
        if isinstance(response_content, list):
            text_parts = []
            for part in response_content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(str(part.get("text", "")))
            merged = "\n".join(p for p in text_parts if p).strip()
            if merged:
                return merged
        raise RuntimeError("Grok response message content is empty")

    @staticmethod
    def _load_image_base64(path: str) -> Optional[dict[str, str]]:
        try:
            data = Path(path).read_bytes()
        except Exception as exc:
            logger.debug("Failed reading image %s: %s", path, exc)
            return None

        mime_type, _ = mimetypes.guess_type(path)
        media_type = mime_type or "image/png"
        encoded = base64.b64encode(data).decode("utf-8")
        return {"media_type": media_type, "data": encoded}

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

    def _build_prompt(
        self,
        serving_countries: list[str],
        text_content: str,
        ocr_texts: list[str],
        metadata: dict,
    ) -> str:
        countries_str = ", ".join(serving_countries) if serving_countries else "unknown"
        all_text = text_content
        if ocr_texts:
            all_text += "\n\nOCR-extracted text:\n" + "\n".join(ocr_texts)

        if len(all_text) > 2000:
            all_text = all_text[:2000] + "..."

        format_info = metadata.get("format", "unknown")
        advertiser = metadata.get("advertiser_name", "")

        return f"""Analyze this advertisement for geo-linguistic mismatches.

SERVING COUNTRIES: {countries_str}
CREATIVE FORMAT: {format_info}
ADVERTISER: {advertiser}

CREATIVE TEXT CONTENT:
{all_text}

If images are provided, also analyze visible text, logos, currencies, and cultural elements in them.

INSTRUCTIONS:
1. Identify the primary and secondary languages in the creative text and images.
2. Identify any currencies shown (symbols or codes).
3. Compare detected languages/currencies against the serving countries.
4. Flag mismatches: e.g., German text served in India, AED currency in US traffic.
5. Consider that some countries are multilingual (e.g., Singapore: EN/ZH/MS/TA).
6. English is acceptable as secondary language globally (ignore as mismatch unless it's the ONLY language in a non-English market).
7. A risk_score of 0.0 means perfect match; 1.0 means definite mismatch.
8. If confidence is below 0.6, set decision to "needs_review" instead of "mismatch".

Return ONLY valid JSON (no markdown, no explanation) in this exact format:
{{
  "primary_languages": ["English"],
  "secondary_languages": [],
  "detected_currencies": ["$"],
  "findings": [
    {{
      "category": "language_mismatch",
      "severity": "high",
      "description": "German text served in India",
      "evidence": "Text contains 'Jetzt kaufen' which is German"
    }}
  ],
  "risk_score": 0.8,
  "decision": "mismatch",
  "confidence": 0.9
}}"""

    def _parse_response(
        self,
        response_text: str,
        serving_countries: list[str],
    ) -> GeoLinguisticAnalysisResult:
        """Parse provider response JSON into structured result."""
        del serving_countries  # reserved for future deterministic guardrails

        raw = response_text.strip()
        result = GeoLinguisticAnalysisResult(raw_response=raw)

        json_str = raw
        if "```" in json_str:
            import re

            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", json_str, re.DOTALL)
            if match:
                json_str = match.group(1)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning(
                "Failed to parse %s geo-linguistic response: %s",
                self.provider,
                raw[:200],
            )
            result.error = "Failed to parse response"
            result.decision = "needs_review"
            return result

        result.primary_languages = data.get("primary_languages", [])
        result.secondary_languages = data.get("secondary_languages", [])
        result.detected_currencies = data.get("detected_currencies", [])
        result.risk_score = min(1.0, max(0.0, float(data.get("risk_score", 0.0))))
        result.confidence = min(1.0, max(0.0, float(data.get("confidence", 0.0))))

        decision = data.get("decision", "needs_review")
        if decision == "mismatch" and result.confidence < 0.6:
            decision = "needs_review"
        result.decision = decision

        for finding in data.get("findings", []):
            result.findings.append(
                GeoLinguisticFinding(
                    category=finding.get("category", "unknown"),
                    severity=finding.get("severity", "low"),
                    description=finding.get("description", ""),
                    evidence=finding.get("evidence", ""),
                )
            )

        return result


# Backward-compatible alias used by existing callers/tests.
GeminiGeoLinguisticAnalyzer = GeoLinguisticAnalyzer

