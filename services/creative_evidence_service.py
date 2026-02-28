"""Creative Evidence Service - Collects evidence from creatives for analysis.

Extracts text, images, screenshots, and video frames from creatives
to feed into the geo-linguistic mismatch analyzer.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

logger = logging.getLogger(__name__)


@dataclass
class EvidenceResult:
    """Collected evidence from a creative."""

    text_content: str = ""
    image_urls: list[str] = field(default_factory=list)
    screenshot_path: Optional[str] = None
    video_frames: list[str] = field(default_factory=list)
    ocr_texts: list[str] = field(default_factory=list)
    currencies: list[str] = field(default_factory=list)
    cta_phrases: list[str] = field(default_factory=list)


# Common currency symbols/codes to detect
_CURRENCY_PATTERNS = re.compile(
    r"(?:[$€£¥₹₩₱₫₺₽₸₮]|"
    r"\b(?:USD|EUR|GBP|JPY|INR|KRW|AED|SAR|MYR|SGD|THB|IDR|PHP|VND|BRL|AUD|CAD|CNY)\b)",
    re.IGNORECASE,
)

# CTA patterns (common across languages)
_CTA_PATTERNS = re.compile(
    r"\b(?:buy now|shop now|sign up|subscribe|download|learn more|get started|"
    r"order now|add to cart|register|apply now|book now|try free|claim|"
    r"install|play now|join|enquire|contact us)\b",
    re.IGNORECASE,
)


class CreativeEvidenceService:
    """Orchestrates evidence collection from creatives."""

    def __init__(self) -> None:
        self._evidence_dir: Optional[Path] = None

    @property
    def evidence_dir(self) -> Path:
        if self._evidence_dir is None:
            self._evidence_dir = Path.home() / ".catscan" / "evidence"
            self._evidence_dir.mkdir(parents=True, exist_ok=True)
        return self._evidence_dir

    def _creative_dir(self, creative_id: str) -> Path:
        d = self.evidence_dir / creative_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def collect_evidence(
        self,
        creative_id: str,
        raw_data: dict,
        creative_format: str,
        ai_provider: str = "gemini",
        ai_api_key: Optional[str] = None,
    ) -> EvidenceResult:
        """Collect all available evidence from a creative."""
        result = EvidenceResult()

        if creative_format == "HTML":
            self._collect_html_evidence(
                creative_id,
                raw_data,
                result,
                ai_provider=ai_provider,
                ai_api_key=ai_api_key,
            )
        elif creative_format == "VIDEO":
            self._collect_video_evidence(
                creative_id,
                raw_data,
                result,
                ai_provider=ai_provider,
                ai_api_key=ai_api_key,
            )
        elif creative_format == "NATIVE":
            self._collect_native_evidence(creative_id, raw_data, result)
        elif creative_format == "IMAGE":
            self._collect_image_evidence(creative_id, raw_data, result)

        # Extract currencies and CTAs from all collected text
        all_text = " ".join([result.text_content] + result.ocr_texts)
        result.currencies = list(set(_CURRENCY_PATTERNS.findall(all_text)))
        result.cta_phrases = list(set(_CTA_PATTERNS.findall(all_text.lower())))

        return result

    # ==================== Format-specific collectors ====================

    def _collect_html_evidence(
        self,
        creative_id: str,
        raw_data: dict,
        result: EvidenceResult,
        ai_provider: str = "gemini",
        ai_api_key: Optional[str] = None,
    ) -> None:
        html_data = raw_data.get("html", {})
        snippet = html_data.get("snippet", "")

        if snippet:
            result.text_content = self._strip_html_tags(snippet)
            result.image_urls = self._extract_image_urls_from_html(snippet)

            # Try Playwright screenshot (graceful degradation)
            screenshot_path = self._take_html_screenshot(creative_id, snippet)
            if screenshot_path:
                result.screenshot_path = screenshot_path
                ocr_text = self._ocr_image(
                    screenshot_path,
                    ai_provider=ai_provider,
                    ai_api_key=ai_api_key,
                )
                if ocr_text:
                    result.ocr_texts.append(ocr_text)

        # Check advertiser name
        advertiser = raw_data.get("advertiserName", "")
        if advertiser:
            result.text_content = f"{result.text_content} {advertiser}".strip()

    def _collect_video_evidence(
        self,
        creative_id: str,
        raw_data: dict,
        result: EvidenceResult,
        ai_provider: str = "gemini",
        ai_api_key: Optional[str] = None,
    ) -> None:
        video_data = raw_data.get("video", {})
        vast_xml = video_data.get("vastXml", "")

        if vast_xml:
            result.text_content = self._extract_text_from_vast(vast_xml)
            video_url = self._extract_video_url_from_vast(vast_xml)

            if video_url:
                frames = self._extract_video_frames(creative_id, video_url)
                result.video_frames = frames

                # OCR each extracted frame
                for frame_path in frames:
                    ocr_text = self._ocr_image(
                        frame_path,
                        ai_provider=ai_provider,
                        ai_api_key=ai_api_key,
                    )
                    if ocr_text:
                        result.ocr_texts.append(ocr_text)

        advertiser = raw_data.get("advertiserName", "")
        if advertiser:
            result.text_content = f"{result.text_content} {advertiser}".strip()

    def _collect_native_evidence(
        self, creative_id: str, raw_data: dict, result: EvidenceResult
    ) -> None:
        native_data = raw_data.get("native", {})
        text_parts = []

        for field_name in ["headline", "body", "callToAction", "advertiserName"]:
            value = native_data.get(field_name, "")
            if value:
                text_parts.append(value)

        # Extract image URLs
        for img_field in ["image", "logo", "appIcon"]:
            img_data = native_data.get(img_field, {})
            if isinstance(img_data, dict):
                url = img_data.get("url", "")
                if url:
                    result.image_urls.append(url)
            elif isinstance(img_data, str) and img_data.startswith("http"):
                result.image_urls.append(img_data)

        advertiser = raw_data.get("advertiserName", "")
        if advertiser and advertiser not in text_parts:
            text_parts.append(advertiser)

        result.text_content = " ".join(text_parts)

    def _collect_image_evidence(
        self, creative_id: str, raw_data: dict, result: EvidenceResult
    ) -> None:
        # IMAGE creatives may have direct image URLs
        image_data = raw_data.get("image", {})
        if isinstance(image_data, dict):
            url = image_data.get("url", "")
            if url:
                result.image_urls.append(url)

        advertiser = raw_data.get("advertiserName", "")
        if advertiser:
            result.text_content = advertiser

    # ==================== HTML helpers ====================

    def _strip_html_tags(self, html: str) -> str:
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", html)
        text = text.replace("&nbsp;", " ").replace("&amp;", "&")
        text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _extract_image_urls_from_html(self, html: str) -> list[str]:
        urls = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
        return [u for u in urls if u.startswith("http")]

    def _take_html_screenshot(self, creative_id: str, snippet: str) -> Optional[str]:
        """Take a screenshot of HTML using Playwright. Returns path or None."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.debug("Playwright not installed, skipping HTML screenshot")
            return None

        output_path = str(self._creative_dir(creative_id) / "screenshot.png")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1024, "height": 768})
                page.set_content(snippet, wait_until="domcontentloaded")
                page.wait_for_timeout(1000)
                page.screenshot(path=output_path, full_page=True)
                browser.close()
            return output_path
        except Exception as e:
            logger.warning("HTML screenshot failed for %s: %s", creative_id, e)
            return None

    # ==================== VAST / Video helpers ====================

    def _extract_text_from_vast(self, vast_xml: str) -> str:
        text_parts = []
        title_match = re.search(
            r"<AdTitle[^>]*>(?:<!\[CDATA\[)?([^\]<]+)", vast_xml, re.IGNORECASE
        )
        if title_match:
            text_parts.append(title_match.group(1).strip())

        desc_match = re.search(
            r"<Description[^>]*>(?:<!\[CDATA\[)?([^\]<]+)", vast_xml, re.IGNORECASE
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

    def _extract_video_url_from_vast(self, vast_xml: str) -> Optional[str]:
        try:
            root = ElementTree.fromstring(vast_xml)
            for path in [
                ".//MediaFile",
                ".//MediaFiles/MediaFile",
                ".//Creative/Linear/MediaFiles/MediaFile",
            ]:
                for mf in root.findall(path):
                    url = mf.text.strip() if mf.text else None
                    if url and url.startswith("http"):
                        return url
        except Exception:
            pass

        match = re.search(r"https?://[^\s<>\"]+\.mp4", vast_xml)
        return match.group(0) if match else None

    def _get_video_duration(self, video_url: str) -> Optional[float]:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return None
        try:
            result = subprocess.run(
                [
                    ffprobe, "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    video_url,
                ],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
        except Exception as e:
            logger.warning("ffprobe failed: %s", e)
        return None

    def _extract_video_frames(
        self, creative_id: str, video_url: str, max_frames: int = 4
    ) -> list[str]:
        """Extract evenly-spaced frames from a video. Returns list of file paths."""
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            logger.debug("ffmpeg not available, skipping video frame extraction")
            return []

        duration = self._get_video_duration(video_url)
        if not duration or duration <= 0:
            # Fall back to single frame at 1s
            timestamps = [1.0]
        else:
            n = min(max_frames, max(1, int(duration)))
            timestamps = [duration * (i + 1) / (n + 1) for i in range(n)]

        out_dir = self._creative_dir(creative_id)
        frames = []

        for i, ts in enumerate(timestamps):
            output_path = out_dir / f"frame_{i:02d}.jpg"
            try:
                cmd = [
                    ffmpeg_path, "-y",
                    "-i", video_url,
                    "-ss", f"{ts:.2f}",
                    "-frames:v", "1",
                    "-q:v", "2",
                    "-update", "1",
                    str(output_path),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if result.returncode == 0 and output_path.exists():
                    frames.append(str(output_path))
            except Exception as e:
                logger.warning("Frame extraction failed at %.1fs for %s: %s", ts, creative_id, e)

        return frames

    # ==================== OCR ====================

    def _ocr_image(
        self,
        image_path: str,
        ai_provider: str = "gemini",
        ai_api_key: Optional[str] = None,
    ) -> Optional[str]:
        """Extract text from image using selected provider."""
        provider = (ai_provider or "gemini").strip().lower()
        if not ai_api_key:
            return None

        try:
            if provider == "gemini":
                text = self._ocr_with_gemini(image_path, ai_api_key)
            elif provider == "claude":
                text = self._ocr_with_claude(image_path, ai_api_key)
            elif provider == "grok":
                text = self._ocr_with_grok(image_path, ai_api_key)
            else:
                return None
            return text if text and text != "EMPTY" else None
        except Exception as e:
            logger.warning("OCR failed for %s: %s", image_path, e)
            return None

    @staticmethod
    def _ocr_with_gemini(image_path: str, api_key: str) -> str:
        import google.generativeai as genai
        import PIL.Image

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        img = PIL.Image.open(image_path)
        response = model.generate_content(
            [
                "Extract ALL visible text from this image. "
                "Return only the extracted text, nothing else. "
                "If there is no text, return EMPTY.",
                img,
            ],
            generation_config={"temperature": 0.1, "max_output_tokens": 500},
        )
        return str(getattr(response, "text", "")).strip()

    def _ocr_with_claude(self, image_path: str, api_key: str) -> str:
        encoded = self._load_image_base64(image_path)
        if not encoded:
            return ""
        payload = {
            "model": "claude-3-5-sonnet-latest",
            "max_tokens": 500,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract ALL visible text from this image. "
                                "Return only extracted text. If no text, return EMPTY."
                            ),
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": encoded["media_type"],
                                "data": encoded["data"],
                            },
                        },
                    ],
                }
            ],
        }
        response_data = self._post_json(
            url="https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            payload=payload,
            timeout=20.0,
        )
        for block in response_data.get("content", []):
            if block.get("type") == "text" and block.get("text"):
                return str(block["text"]).strip()
        return ""

    def _ocr_with_grok(self, image_path: str, api_key: str) -> str:
        encoded = self._load_image_base64(image_path)
        if not encoded:
            return ""
        payload = {
            "model": "grok-2-latest",
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract ALL visible text from this image. "
                                "Return only extracted text. If no text, return EMPTY."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    f"data:{encoded['media_type']};base64,{encoded['data']}"
                                )
                            },
                        },
                    ],
                }
            ],
        }
        response_data = self._post_json(
            url="https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            payload=payload,
            timeout=20.0,
        )
        choices = response_data.get("choices", [])
        if not choices:
            return ""
        content = choices[0].get("message", {}).get("content")
        return str(content).strip() if content else ""

    @staticmethod
    def _load_image_base64(path: str) -> Optional[dict[str, str]]:
        try:
            data = Path(path).read_bytes()
        except Exception as exc:
            logger.debug("Failed to read OCR image %s: %s", path, exc)
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
