"""RTB Funnel Analyzer for Cat-Scan.

Parses Google Authorized Buyers bidding metrics CSVs and provides
funnel analysis: Bid Requests → Reached Queries → Impressions
"""

import csv
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# Default paths for RTB data files
DOCS_PATH = Path(__file__).parent.parent.parent / "docs"
BIDS_PER_PUB_FILE = DOCS_PATH / "Bids-per-Pub.csv"
ADX_BIDDING_METRICS_FILE = DOCS_PATH / "ADX bidding metrics Yesterday (2).csv"


@dataclass
class PublisherStats:
    """Performance metrics for a single publisher."""
    publisher_id: str
    publisher_name: str
    bids: int = 0
    bid_requests: int = 0
    reached_queries: int = 0
    successful_responses: int = 0
    impressions: int = 0

    @property
    def pretargeting_filter_rate(self) -> float:
        """Percentage of bid requests filtered by pretargeting."""
        if self.bid_requests == 0:
            return 0.0
        return ((self.bid_requests - self.reached_queries) / self.bid_requests) * 100

    @property
    def win_rate(self) -> float:
        """Win rate = impressions / reached queries."""
        if self.reached_queries == 0:
            return 0.0
        return (self.impressions / self.reached_queries) * 100

    @property
    def bid_rate(self) -> float:
        """Bid rate = bids / reached queries."""
        if self.reached_queries == 0:
            return 0.0
        return (self.bids / self.reached_queries) * 100


@dataclass
class GeoStats:
    """Performance metrics for a geographic region."""
    country: str
    bids: int = 0
    reached_queries: int = 0
    bids_in_auction: int = 0
    auctions_won: int = 0
    creative_count: int = 0

    @property
    def win_rate(self) -> float:
        """Win rate = auctions won / reached queries."""
        if self.reached_queries == 0:
            return 0.0
        return (self.auctions_won / self.reached_queries) * 100

    @property
    def auction_participation_rate(self) -> float:
        """Rate of bids making it to auction."""
        if self.bids == 0:
            return 0.0
        return (self.bids_in_auction / self.bids) * 100


@dataclass
class CreativeStats:
    """Performance metrics for a single creative."""
    creative_id: str
    bids: int = 0
    reached_queries: int = 0
    bids_in_auction: int = 0
    auctions_won: int = 0
    countries: list = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        """Win rate = auctions won / reached queries."""
        if self.reached_queries == 0:
            return 0.0
        return (self.auctions_won / self.reached_queries) * 100


@dataclass
class FunnelSummary:
    """High-level RTB funnel metrics."""
    total_bid_requests: int = 0
    total_reached_queries: int = 0
    total_bids: int = 0
    total_impressions: int = 0
    total_successful_responses: int = 0

    # Derived metrics
    @property
    def pretargeting_filter_rate(self) -> float:
        """Percentage of requests filtered by pretargeting (intentional)."""
        if self.total_bid_requests == 0:
            return 0.0
        return ((self.total_bid_requests - self.total_reached_queries) / self.total_bid_requests) * 100

    @property
    def reach_rate(self) -> float:
        """Percentage of requests that reached the bidder."""
        if self.total_bid_requests == 0:
            return 0.0
        return (self.total_reached_queries / self.total_bid_requests) * 100

    @property
    def win_rate(self) -> float:
        """Win rate on reached traffic."""
        if self.total_reached_queries == 0:
            return 0.0
        return (self.total_impressions / self.total_reached_queries) * 100

    @property
    def bid_rate(self) -> float:
        """Bid rate on reached traffic."""
        if self.total_reached_queries == 0:
            return 0.0
        return (self.total_bids / self.total_reached_queries) * 100


class RTBFunnelAnalyzer:
    """Analyzes RTB funnel data from Google Authorized Buyers exports."""

    def __init__(
        self,
        bids_per_pub_path: Optional[str] = None,
        adx_metrics_path: Optional[str] = None
    ):
        self.bids_per_pub_path = Path(bids_per_pub_path) if bids_per_pub_path else BIDS_PER_PUB_FILE
        self.adx_metrics_path = Path(adx_metrics_path) if adx_metrics_path else ADX_BIDDING_METRICS_FILE

        self._publishers: dict[str, PublisherStats] = {}
        self._geos: dict[str, GeoStats] = {}
        self._creatives: dict[str, CreativeStats] = {}
        self._funnel: Optional[FunnelSummary] = None
        self._data_loaded = False

    def _parse_int(self, value: str) -> int:
        """Parse integer, handling commas and empty strings."""
        if not value or value.strip() == "":
            return 0
        try:
            return int(value.replace(",", "").strip())
        except ValueError:
            return 0

    def _load_bids_per_pub(self) -> None:
        """Load publisher-level data from Bids-per-Pub.csv."""
        if not self.bids_per_pub_path.exists():
            logger.warning(f"Bids-per-Pub file not found: {self.bids_per_pub_path}")
            return

        try:
            with open(self.bids_per_pub_path, "r", encoding="utf-8") as f:
                # Skip the header comment if present
                reader = csv.DictReader(f)
                for row in reader:
                    # Handle the #Publisher ID header format
                    pub_id = row.get("#Publisher ID", row.get("Publisher ID", ""))
                    pub_name = row.get("Publisher name", pub_id)

                    if not pub_id:
                        continue

                    self._publishers[pub_id] = PublisherStats(
                        publisher_id=pub_id,
                        publisher_name=pub_name,
                        bids=self._parse_int(row.get("Bids", "0")),
                        bid_requests=self._parse_int(row.get("Bid requests", "0")),
                        reached_queries=self._parse_int(row.get("Reached queries", "0")),
                        successful_responses=self._parse_int(row.get("Successful responses", "0")),
                        impressions=self._parse_int(row.get("Impressions", "0")),
                    )

            logger.info(f"Loaded {len(self._publishers)} publishers from Bids-per-Pub.csv")
        except Exception as e:
            logger.error(f"Failed to load Bids-per-Pub.csv: {e}")

    def _load_adx_metrics(self) -> None:
        """Load creative/geo data from ADX bidding metrics CSV."""
        if not self.adx_metrics_path.exists():
            logger.warning(f"ADX metrics file not found: {self.adx_metrics_path}")
            return

        try:
            with open(self.adx_metrics_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Handle the #Creative ID header format
                    creative_id = row.get("#Creative ID", row.get("Creative ID", ""))
                    country = row.get("Country", "")

                    if not creative_id:
                        continue

                    bids = self._parse_int(row.get("Bids", "0"))
                    reached = self._parse_int(row.get("Reached queries", "0"))
                    in_auction = self._parse_int(row.get("Bids in auction", "0"))
                    won = self._parse_int(row.get("Auctions won", "0"))

                    # Aggregate by creative
                    if creative_id not in self._creatives:
                        self._creatives[creative_id] = CreativeStats(
                            creative_id=creative_id,
                            countries=[]
                        )

                    creative = self._creatives[creative_id]
                    creative.bids += bids
                    creative.reached_queries += reached
                    creative.bids_in_auction += in_auction
                    creative.auctions_won += won
                    if country and country not in creative.countries:
                        creative.countries.append(country)

                    # Aggregate by geo
                    if country:
                        if country not in self._geos:
                            self._geos[country] = GeoStats(country=country)

                        geo = self._geos[country]
                        geo.bids += bids
                        geo.reached_queries += reached
                        geo.bids_in_auction += in_auction
                        geo.auctions_won += won
                        geo.creative_count = len(set(
                            c.creative_id for c in self._creatives.values()
                            if country in c.countries
                        ))

            logger.info(f"Loaded {len(self._creatives)} creatives, {len(self._geos)} geos from ADX metrics")
        except Exception as e:
            logger.error(f"Failed to load ADX metrics CSV: {e}")

    def _calculate_funnel(self) -> None:
        """Calculate overall funnel metrics from publisher data."""
        self._funnel = FunnelSummary()

        for pub in self._publishers.values():
            self._funnel.total_bid_requests += pub.bid_requests
            self._funnel.total_reached_queries += pub.reached_queries
            self._funnel.total_bids += pub.bids
            self._funnel.total_impressions += pub.impressions
            self._funnel.total_successful_responses += pub.successful_responses

    def load_data(self) -> None:
        """Load all data from CSV files."""
        if self._data_loaded:
            return

        self._load_bids_per_pub()
        self._load_adx_metrics()
        self._calculate_funnel()
        self._data_loaded = True

    def get_funnel_summary(self) -> dict:
        """Get the high-level RTB funnel summary."""
        self.load_data()

        if not self._funnel:
            return {
                "has_data": False,
                "message": "No RTB data available. Import bidding metrics from Google Authorized Buyers."
            }

        return {
            "has_data": True,
            "total_bid_requests": self._funnel.total_bid_requests,
            "total_reached_queries": self._funnel.total_reached_queries,
            "total_bids": self._funnel.total_bids,
            "total_impressions": self._funnel.total_impressions,
            "pretargeting_filter_rate": round(self._funnel.pretargeting_filter_rate, 2),
            "reach_rate": round(self._funnel.reach_rate, 4),
            "win_rate": round(self._funnel.win_rate, 2),
            "bid_rate": round(self._funnel.bid_rate, 2),
        }

    def get_publisher_performance(self, limit: int = 20) -> list[dict]:
        """Get top publishers by impressions with win rate analysis."""
        self.load_data()

        # Sort by impressions (active publishers first)
        sorted_pubs = sorted(
            self._publishers.values(),
            key=lambda p: p.impressions,
            reverse=True
        )

        return [
            {
                "publisher_id": p.publisher_id,
                "publisher_name": p.publisher_name,
                "bid_requests": p.bid_requests,
                "reached_queries": p.reached_queries,
                "bids": p.bids,
                "impressions": p.impressions,
                "pretargeting_filter_rate": round(p.pretargeting_filter_rate, 2),
                "win_rate": round(p.win_rate, 2),
                "bid_rate": round(p.bid_rate, 2),
            }
            for p in sorted_pubs[:limit]
        ]

    def get_geo_performance(self, limit: int = 20) -> list[dict]:
        """Get geographic performance breakdown."""
        self.load_data()

        # Sort by auctions won
        sorted_geos = sorted(
            self._geos.values(),
            key=lambda g: g.auctions_won,
            reverse=True
        )

        return [
            {
                "country": g.country,
                "bids": g.bids,
                "reached_queries": g.reached_queries,
                "bids_in_auction": g.bids_in_auction,
                "auctions_won": g.auctions_won,
                "win_rate": round(g.win_rate, 2),
                "auction_participation_rate": round(g.auction_participation_rate, 2),
                "creative_count": g.creative_count,
            }
            for g in sorted_geos[:limit]
        ]

    def get_creative_performance(self, limit: int = 20) -> list[dict]:
        """Get creative-level performance breakdown."""
        self.load_data()

        # Sort by auctions won
        sorted_creatives = sorted(
            self._creatives.values(),
            key=lambda c: c.auctions_won,
            reverse=True
        )

        return [
            {
                "creative_id": c.creative_id,
                "bids": c.bids,
                "reached_queries": c.reached_queries,
                "bids_in_auction": c.bids_in_auction,
                "auctions_won": c.auctions_won,
                "win_rate": round(c.win_rate, 2),
                "countries": c.countries[:5],  # Top 5 countries
            }
            for c in sorted_creatives[:limit]
        ]

    def get_full_analysis(self) -> dict:
        """Get complete RTB funnel analysis."""
        self.load_data()

        return {
            "funnel": self.get_funnel_summary(),
            "publishers": self.get_publisher_performance(limit=30),
            "geos": self.get_geo_performance(limit=30),
            "creatives": self.get_creative_performance(limit=30),
            "data_sources": {
                "bids_per_pub_available": self.bids_per_pub_path.exists(),
                "adx_metrics_available": self.adx_metrics_path.exists(),
                "publishers_count": len(self._publishers),
                "geos_count": len(self._geos),
                "creatives_count": len(self._creatives),
            }
        }


def get_rtb_funnel_data() -> dict:
    """Convenience function to get RTB funnel data."""
    analyzer = RTBFunnelAnalyzer()
    return analyzer.get_full_analysis()
