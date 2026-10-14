#!/usr/bin/env python3
"""Enrich an app CSV or one identity with live publisher evidence. No spend filter."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.publisher_profiles import PublisherProfilesClient
from services.publisher_lookup_service import PublisherLookupService


async def run(args) -> None:
    client = None
    if args.buyer_id:
        client = PublisherProfilesClient(args.buyer_id, args.credentials)
    service = PublisherLookupService()
    if args.input_csv:
        with args.input_csv.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            if args.app_id_column not in fields and not (
                args.domain_column and args.domain_column in fields
            ):
                raise ValueError(
                    "CSV must contain the specified app ID or domain column"
                )
            rows = list(reader)
    else:
        rows = [{args.app_id_column: args.app_id or "", "domain": args.domain or ""}]
        args.domain_column = "domain"
        fields = list(rows[0])
    results = []
    enriched = []
    for index, row in enumerate(rows, 1):
        app_id = (row.get(args.app_id_column) or "").strip() or None
        domain = (
            (row.get(args.domain_column) or "").strip() or None
            if args.domain_column
            else None
        )
        try:
            data = await service.lookup(
                app_id=app_id,
                domain=domain,
                publisher_name=args.publisher_name,
                google_client=client,
            )
        except ValueError as exc:
            data = {
                "status": (
                    "identity_required"
                    if not app_id and not domain
                    else "invalid_identity"
                ),
                "message": str(exc),
            }
        results.append({"row_number": index, "input": row, "lookup": data})
        marketplace = data.get("google_marketplace", {})
        profiles = marketplace.get("profiles", [])
        enriched.append(
            {
                **row,
                "lookup_checked_at": data.get("checked_at", ""),
                "lookup_status": data.get(
                    "status", "partial" if data.get("partial") else "ok"
                ),
                "lookup_manager_domains": "; ".join(
                    m["domain"] for m in data.get("managers", [])
                ),
                "lookup_manager_contacts": "; ".join(
                    m["contact_email"]
                    for m in data.get("managers", [])
                    if m.get("contact_email")
                ),
                "lookup_developer_name": data.get("app_store", {}).get("developer_name")
                or "",
                "lookup_developer_website": data.get("app_store", {}).get(
                    "developer_website"
                )
                or "",
                "lookup_support_contacts": "; ".join(
                    data.get("app_store", {}).get("support_contacts", [])
                ),
                "lookup_owner_domains": "; ".join(
                    data.get("ads_txt", {}).get("owner_domains", [])
                ),
                "lookup_google_status": marketplace.get("status", "not_requested"),
                "lookup_google_profiles": "; ".join(
                    p.get("displayName", "") for p in profiles
                ),
                "lookup_programmatic_contacts": "; ".join(
                    p.get("programmaticDealsContact", "")
                    for p in profiles
                    if p.get("programmaticDealsContact")
                ),
                "lookup_direct_deals_contacts": "; ".join(
                    p.get("directDealsContact", "")
                    for p in profiles
                    if p.get("directDealsContact")
                ),
                "lookup_evidence_url": data.get("ads_txt", {}).get("source_url", ""),
            }
        )
    args.output_json.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n"
    )
    if args.output_csv and enriched:
        with args.output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(enriched[0]))
            writer.writeheader()
            writer.writerows(enriched)
    print(f"Collected {len(results)} identity lookups into {args.output_json}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path)
    parser.add_argument("--app-id")
    parser.add_argument("--domain")
    parser.add_argument(
        "--publisher-name", help="Search Google profiles by company name"
    )
    parser.add_argument("--app-id-column", default="Mobile app ID")
    parser.add_argument("--domain-column")
    parser.add_argument(
        "--buyer-id", help="Enable Google Marketplace lookup for this buyer"
    )
    parser.add_argument(
        "--credentials", help="Service-account JSON path; never the key itself"
    )
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args()
    if not (args.input_csv or args.app_id or args.domain or args.publisher_name):
        parser.error("Provide --input-csv, --app-id, --domain or --publisher-name")
    if args.publisher_name and (args.input_csv or not args.buyer_id):
        parser.error(
            "--publisher-name requires --buyer-id and cannot accompany --input-csv"
        )
    if args.credentials and not args.buyer_id:
        parser.error("--credentials requires --buyer-id")
    if args.input_csv and any(
        p and p.resolve() == args.input_csv.resolve()
        for p in (args.output_json, args.output_csv)
    ):
        parser.error("Output must not overwrite the input CSV")
    if args.output_csv and args.output_csv.resolve() == args.output_json.resolve():
        parser.error("JSON and CSV outputs must be different files")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
