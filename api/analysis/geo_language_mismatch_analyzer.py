"""Geo-linguistic mismatch analysis using Google Gemini API.

Analyzes creative content (text, OCR, images) against serving countries
to detect language/currency/cultural mismatches that indicate waste.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

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


class GeminiGeoLinguisticAnalyzer:
    """Gemini-powered geo-linguistic mismatch detection."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or get_secrets_manager().get("GEMINI_API_KEY")
        self._model = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def model(self):
        """Lazy-load Gemini model."""
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
        """Analyze creative content for geo-linguistic mismatches.

        Args:
            serving_countries: List of country codes where the creative is served.
            text_content: Extracted text from the creative.
            ocr_texts: OCR-extracted text from screenshots/frames.
            image_paths: Paths to images for multimodal analysis.
            creative_metadata: Additional metadata (format, advertiser, etc.).
            timeout: API call timeout in seconds.
        """
        if not self.is_configured:
            return GeoLinguisticAnalysisResult(
                error="Gemini API not configured",
                decision="needs_review",
            )

        if not text_content and not ocr_texts and not image_paths:
            return GeoLinguisticAnalysisResult(
                error="No content to analyze",
                decision="needs_review",
            )

        prompt = self._build_prompt(
            serving_countries, text_content, ocr_texts or [], creative_metadata or {}
        )

        try:
            content_parts = [prompt]

            # Add images for multimodal analysis
            if image_paths:
                try:
                    import PIL.Image

                    for path in image_paths[:4]:  # Cap at 4 images
                        try:
                            img = PIL.Image.open(path)
                            content_parts.append(img)
                        except Exception as e:
                            logger.debug("Skipping image %s: %s", path, e)
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

            return self._parse_response(response.text, serving_countries)

        except Exception as e:
            logger.error("Geo-linguistic analysis failed: %s", e)
            return GeoLinguisticAnalysisResult(
                error=str(e),
                decision="needs_review",
            )

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

        # Truncate to save tokens
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
        self, response_text: str, serving_countries: list[str]
    ) -> GeoLinguisticAnalysisResult:
        """Parse Gemini response JSON into structured result."""
        raw = response_text.strip()
        result = GeoLinguisticAnalysisResult(raw_response=raw)

        # Try to extract JSON from response
        json_str = raw
        if "```" in json_str:
            # Strip markdown code fences
            import re

            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", json_str, re.DOTALL)
            if match:
                json_str = match.group(1)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("Failed to parse Gemini geo-linguistic response: %s", raw[:200])
            result.error = "Failed to parse response"
            result.decision = "needs_review"
            return result

        result.primary_languages = data.get("primary_languages", [])
        result.secondary_languages = data.get("secondary_languages", [])
        result.detected_currencies = data.get("detected_currencies", [])
        result.risk_score = min(1.0, max(0.0, float(data.get("risk_score", 0.0))))
        result.confidence = min(1.0, max(0.0, float(data.get("confidence", 0.0))))

        decision = data.get("decision", "needs_review")
        # Override to needs_review if confidence is low
        if decision == "mismatch" and result.confidence < 0.6:
            decision = "needs_review"
        result.decision = decision

        for f in data.get("findings", []):
            result.findings.append(
                GeoLinguisticFinding(
                    category=f.get("category", "unknown"),
                    severity=f.get("severity", "low"),
                    description=f.get("description", ""),
                    evidence=f.get("evidence", ""),
                )
            )

        return result
