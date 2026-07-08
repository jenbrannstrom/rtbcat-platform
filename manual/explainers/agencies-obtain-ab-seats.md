# How smaller agencies and restricted entities obtain and operate Google Authorized Buyers seats

**Atomic fact:** Many agencies that are "too small," based in certain jurisdictions (including Chinese citizens and entities), or simply lack existing relationships cannot obtain a direct Google Authorized Buyers contract on their own.

This is not a minor paperwork issue. It is a structural barrier in the Authorized Buyers program.

## The real barriers

Google Authorized Buyers is not a self-serve product like Google Ads. Approval involves:

- Minimum spend and history requirements that newer or smaller agencies rarely meet.
- Compliance and KYC reviews that can be difficult or impossible for entities in certain countries.
- The need for existing relationships or warm introductions.
- Technical and operational readiness checks that most agencies only discover after they have the seat.

RTB.cat's core business is helping exactly these agencies obtain and then successfully operate the connection. Clients bring their own bidder. RTB.cat supplies the Authorized Buyers pipe (and increasingly direct OpenRTB endpoints such as TrueCaller) and takes a percentage of the media spend for management and optimization.

## What "operating the seat" actually requires after you have the contract

Getting the seat is only the first step. Day-to-day operation surfaces the problems documented throughout these explainers:

- The five incompatible CSV reports and the need to join them.
- The hard limit of 10 pretargeting configurations.
- The complete absence of safe change tooling in the native UI.
- Publisher deal ID procurement (RTB.cat has secured deal IDs with publishers including GCASH, Twitter, and JAZZ in Pakistan).
- Creative hygiene at scale.
- QPS waste that the bidder cannot fix because the traffic never should have been sent.

Most agencies that finally receive a seat are surprised by how much operational work remains on their side of the exchange.

## Why the Cat-Scan platform exists

Cat-Scan (the open-source QPS control plane) was built because the author needed these capabilities while running real seats and could not find them elsewhere. It is deliberately not a bidder. It is the missing control and visibility layer on top of an existing Authorized Buyers (or direct OpenRTB) connection.

Publishing the platform as open source serves two purposes:
1. It is a concrete, auditable demonstration of deep operational competence.
2. It is a lead magnet for the exact class of sophisticated but constrained agencies that need both the connection and the tooling.

## Related services

- Google Authorized Buyers connection for agencies that cannot obtain it directly.
- TrueCaller direct OpenRTB endpoint supply.
- Publisher deal ID introductions and management.
- Ongoing seat operation and optimization (using Cat-Scan or equivalent tooling).
- Technical consulting for teams that want to build or improve their own control planes.

Contact: [rtb.cat](https://rtb.cat) — WeChat: jenbrannstrom

**Last updated:** June 2026  
Part of the RTB.cat / Cat-Scan technical explainers.