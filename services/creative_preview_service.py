"""Creative preview extraction helpers."""

from __future__ import annotations

import os
import re
from typing import Any, Optional


class CreativePreviewService:
    """Builds preview payloads for creatives."""

    def build_preview(
        self,
        creative: Any,
        slim: bool = False,
        html_thumbnail_url: Optional[str] = None,
    ) -> dict:
        """Extract preview data from creative raw_data based on format."""
        raw_data = creative.raw_data or {}
        result = {"video": None, "html": None, "native": None}

        if creative.format == "VIDEO":
            video_data = raw_data.get("video")
            if video_data:
                vast_xml = (
                    video_data.get("vastXml")
                    or video_data.get("videoVastXml")
                    or video_data.get("vast_xml")
                    or video_data.get("video_vast_xml")
                    or raw_data.get("vastXml")
                    or raw_data.get("videoVastXml")
                    or raw_data.get("vast_xml")
                    or raw_data.get("video_vast_xml")
                )
                video_url = (
                    video_data.get("videoUrl")
                    or video_data.get("video_url")
                    or raw_data.get("videoUrl")
                    or raw_data.get("video_url")
                )
                if not video_url and vast_xml:
                    video_url = self._extract_video_url_from_vast(vast_xml)
                local_thumb_path = video_data.get("localThumbnailPath")
                if local_thumb_path and os.path.exists(local_thumb_path):
                    thumbnail_url = f"/api/thumbnails/{creative.id}.jpg"
                else:
                    thumbnail_url = (
                        self._extract_thumbnail_from_vast(vast_xml) if vast_xml else None
                    )
                result["video"] = {
                    "video_url": video_url,
                    "thumbnail_url": thumbnail_url,
                    "vast_xml": None if slim else vast_xml,
                    "duration": video_data.get("duration"),
                }
            elif html_thumbnail_url:
                # Fallback path for slim list responses where raw_data is intentionally omitted.
                result["video"] = {
                    "video_url": None,
                    "thumbnail_url": html_thumbnail_url,
                    "vast_xml": None,
                    "duration": None,
                }

        elif creative.format == "HTML":
            html_data = raw_data.get("html")
            if html_data:
                result["html"] = {
                    "snippet": None if slim else html_data.get("snippet"),
                    "width": html_data.get("width"),
                    "height": html_data.get("height"),
                    "thumbnail_url": html_thumbnail_url,
                }
            elif html_thumbnail_url:
                # Keep thumbnail previews available even when html snippet payload is excluded.
                result["html"] = {
                    "snippet": None,
                    "width": None,
                    "height": None,
                    "thumbnail_url": html_thumbnail_url,
                }

        elif creative.format == "NATIVE":
            native_data = raw_data.get("native")
            if native_data:
                result["native"] = {
                    "headline": native_data.get("headline"),
                    "body": native_data.get("body"),
                    "call_to_action": native_data.get("callToAction"),
                    "click_link_url": native_data.get("clickLinkUrl"),
                    "image": native_data.get("image"),
                    "logo": native_data.get("logo"),
                }

        return result

    @staticmethod
    def _extract_video_url_from_vast(vast_xml: str) -> Optional[str]:
        """Extract video URL from VAST XML."""
        if not vast_xml:
            return None
        match = re.search(
            r"<MediaFile[^>]*>(?:<!\[CDATA\[)?(https?://[^\]<]+)",
            vast_xml,
            re.IGNORECASE,
        )
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_thumbnail_from_vast(vast_xml: str) -> Optional[str]:
        """Extract thumbnail URL from VAST XML CompanionAds."""
        if not vast_xml:
            return None
        patterns = [
            r'<StaticResource[^>]*creativeType="image/[^"]*"[^>]*><!\[CDATA\[(https?://[^\]]+)\]\]></StaticResource>',
            r'<StaticResource[^>]*creativeType="image/[^"]*"[^>]*>(https?://[^<]+)</StaticResource>',
            r'<Companion[^>]*>.*?<StaticResource[^>]*><!\[CDATA\[(https?://[^\]]+\.(?:jpg|jpeg|png|gif))\]\]>',
        ]
        for pattern in patterns:
            match = re.search(pattern, vast_xml, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        return None
