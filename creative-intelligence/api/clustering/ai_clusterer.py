"""AI-Powered Campaign Clustering using Claude API.

This module uses Claude to analyze pre-clustered creatives and:
1. Refine cluster boundaries (merge/split suggestions)
2. Generate descriptive campaign names
3. Provide confidence scores for groupings
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from .rule_based import get_cluster_summary

logger = logging.getLogger(__name__)


class AICampaignClusterer:
    """Claude-powered campaign naming and cluster refinement."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the AI clusterer.

        Args:
            api_key: Anthropic API key. If not provided, uses ANTHROPIC_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None

    @property
    def client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
        return self._client

    def analyze_and_name_clusters(
        self,
        clusters: dict[str, list[dict]],
    ) -> dict[str, Any]:
        """Use Claude to analyze clusters and generate campaign names.

        Args:
            clusters: Dict mapping cluster keys to lists of creative dicts

        Returns:
            Dict with:
                - campaigns: List of refined campaign definitions
                - splits: List of clusters to split
                - merges: List of cluster merges to perform
        """
        if not clusters:
            return {"campaigns": [], "splits": [], "merges": []}

        # Generate summaries for Claude
        cluster_summaries = []
        for cluster_key, creatives in clusters.items():
            summary = get_cluster_summary(cluster_key, creatives)
            cluster_summaries.append(summary)

        # Build prompt
        prompt = self._build_analysis_prompt(cluster_summaries)

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            result = self._parse_claude_response(response.content[0].text)
            return result

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            # Fallback to rule-based naming
            return self._fallback_naming(clusters)

    def _build_analysis_prompt(self, summaries: list[dict]) -> str:
        """Build the analysis prompt for Claude."""
        return f"""You are analyzing advertising creative clusters to identify campaigns.

Here are {len(summaries)} clusters of creatives from an RTB (Real-Time Bidding) advertising platform:

{json.dumps(summaries, indent=2, default=str)}

For each cluster, analyze the domains, URLs, and patterns to determine:
1. A descriptive campaign name (e.g., "Holiday Shopping Campaign", "Mobile Gaming Q4")
2. Confidence score (0-1) that these creatives belong together
3. Which clusters could be merged (same advertiser/campaign, different placements)
4. Which clusters should be split (unrelated creatives grouped together)

Consider these signals:
- Same domain = likely same advertiser/campaign
- Similar URL patterns (promo, sale, campaign) = related
- Week-based clusters are fallback groupings, often contain unrelated creatives
- Look for advertiser brand names in domains

Respond ONLY with valid JSON in this exact format:
{{
  "campaigns": [
    {{
      "cluster_keys": ["domain:example.com"],
      "name": "Example Brand Campaign",
      "description": "Creatives promoting Example brand products",
      "confidence": 0.85,
      "reasoning": "All creatives point to same advertiser domain"
    }}
  ],
  "merges": [
    {{
      "keys_to_merge": ["domain:shop.brand.com", "domain:brand.com"],
      "merged_name": "Brand E-commerce Campaign",
      "reason": "Same brand, different subdomains"
    }}
  ],
  "splits": [
    {{
      "cluster_key": "week:2025-W45",
      "reason": "Contains unrelated advertisers, should not be grouped by time alone"
    }}
  ]
}}

Be concise. Focus on actionable groupings. Generate meaningful campaign names.
If a cluster has unclear purpose, give it a descriptive name based on the domain/content."""

    def _parse_claude_response(self, text: str) -> dict[str, Any]:
        """Parse JSON from Claude's response."""
        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        try:
            result = json.loads(text.strip())
            # Ensure required keys exist
            result.setdefault("campaigns", [])
            result.setdefault("merges", [])
            result.setdefault("splits", [])
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response: {e}")
            logger.debug(f"Response text: {text[:500]}")
            return {"campaigns": [], "merges": [], "splits": []}

    def _fallback_naming(self, clusters: dict[str, list[dict]]) -> dict[str, Any]:
        """Fallback to rule-based naming when AI is unavailable."""
        from .rule_based import generate_cluster_name

        campaigns = []
        for cluster_key, creatives in clusters.items():
            name = generate_cluster_name(cluster_key, creatives)
            campaigns.append({
                "cluster_keys": [cluster_key],
                "name": name,
                "description": None,
                "confidence": 0.5,  # Lower confidence for rule-based
                "reasoning": "Generated by rule-based fallback",
            })

        return {
            "campaigns": campaigns,
            "merges": [],
            "splits": [],
        }

    def generate_campaign_name(
        self,
        domain: Optional[str] = None,
        urls: Optional[list[str]] = None,
        format_types: Optional[list[str]] = None,
    ) -> str:
        """Generate a single campaign name for quick naming.

        Args:
            domain: Primary domain for the campaign
            urls: Sample URLs from the campaign
            format_types: Creative formats in the campaign

        Returns:
            Generated campaign name string
        """
        if not domain and not urls:
            return "Untitled Campaign"

        # Quick prompt for single name generation
        context_parts = []
        if domain:
            context_parts.append(f"Domain: {domain}")
        if urls:
            context_parts.append(f"Sample URLs: {', '.join(urls[:3])}")
        if format_types:
            context_parts.append(f"Formats: {', '.join(format_types)}")

        context = "\n".join(context_parts)

        prompt = f"""Generate a short, descriptive campaign name (3-5 words) for these advertising creatives:

{context}

Return ONLY the campaign name, nothing else. Examples of good names:
- "Holiday Shopping Promo"
- "Mobile Gaming Q4 Launch"
- "Brand Awareness Campaign"
"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}]
            )
            name = response.content[0].text.strip().strip('"').strip("'")
            return name[:100]  # Limit length
        except Exception as e:
            logger.warning(f"AI naming failed: {e}")
            # Fallback
            if domain:
                return f"{domain.split('.')[0].title()} Campaign"
            return "Untitled Campaign"


def apply_ai_suggestions(
    clusters: dict[str, list[dict]],
    ai_result: dict[str, Any],
) -> list[dict]:
    """Apply AI suggestions to create final campaign definitions.

    Args:
        clusters: Original clusters from rule-based clustering
        ai_result: AI analysis result with campaigns, merges, splits

    Returns:
        List of campaign definitions ready to save to database
    """
    campaigns = []

    # Track which cluster keys have been processed
    processed_keys = set()

    # First, apply merges
    for merge in ai_result.get("merges", []):
        keys_to_merge = merge.get("keys_to_merge", [])
        if not keys_to_merge:
            continue

        merged_creatives = []
        for key in keys_to_merge:
            if key in clusters:
                merged_creatives.extend(clusters[key])
                processed_keys.add(key)

        if merged_creatives:
            campaigns.append({
                "name": merge.get("merged_name", "Merged Campaign"),
                "description": merge.get("reason"),
                "creative_ids": [c["id"] for c in merged_creatives],
                "ai_confidence": 0.7,
                "clustering_method": "ai_merge",
            })

    # Then, process individual campaigns
    for campaign_def in ai_result.get("campaigns", []):
        cluster_keys = campaign_def.get("cluster_keys", [])

        all_creatives = []
        for key in cluster_keys:
            if key in clusters and key not in processed_keys:
                all_creatives.extend(clusters[key])
                processed_keys.add(key)

        if all_creatives:
            campaigns.append({
                "name": campaign_def.get("name", "Unnamed Campaign"),
                "description": campaign_def.get("description"),
                "creative_ids": [c["id"] for c in all_creatives],
                "ai_confidence": campaign_def.get("confidence", 0.5),
                "clustering_method": "ai",
            })

    # Finally, handle any remaining unprocessed clusters
    # (including splits which should stay separate)
    for cluster_key, creatives in clusters.items():
        if cluster_key not in processed_keys:
            from .rule_based import generate_cluster_name

            campaigns.append({
                "name": generate_cluster_name(cluster_key, creatives),
                "description": None,
                "creative_ids": [c["id"] for c in creatives],
                "ai_confidence": 0.3,  # Low confidence for unprocessed
                "clustering_method": cluster_key.split(":")[0],  # domain, url, week
            })

    return campaigns
