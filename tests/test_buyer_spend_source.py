from importers.flexible_mapper import canonical_source_report, map_columns


def test_buyer_auction_report_is_the_canonical_spend_source():
    mapping = map_columns([
        "#Day", "Hour", "Country", "Creative ID", "Buyer account ID",
        "Bids in auction", "Auctions won", "Bids", "Reached queries",
        "Impressions", "Spend (buyer currency)",
    ])

    assert canonical_source_report(mapping, "performance_detail") == "buyer_spend"


def test_billing_quality_spend_is_not_tagged_as_buyer_spend():
    mapping = map_columns([
        "#Billing ID", "Creative ID", "Country", "Creative size",
        "Creative format", "Day", "Hour", "Publisher ID", "Publisher name",
        "Impressions", "Spend (buyer currency)", "Active view viewable",
        "Active view measurable", "Reached queries",
    ])

    assert canonical_source_report(mapping, "performance_detail") == "performance_detail"
