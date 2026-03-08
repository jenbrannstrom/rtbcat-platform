# Cat-Scan Roadmap

Last updated: March 7, 2026

This roadmap is forward-looking. It is not an internal incident diary.

## What is already built

These are not roadmap items anymore.

Built and in repo:
- Gmail and manual CSV ingestion for the five core Authorized Buyers report types
- creative sync, seat sync, endpoint sync, and pretargeting management
- QPS analysis by publisher, geo, and size
- waste analysis and campaign clustering
- multi-user auth, roles, audit log, and seat-scoped access
- import tracking, retention controls, and runtime health tooling
- click-macro audit and AppsFlyer readiness diagnostics
- conversion ingestion foundations and attribution join storage
- optional AI-assisted language detection and geo-linguistic mismatch analysis

## Current priorities

### 1. Conversion-driven optimization

This is the most important missing layer.

Why:
- today the optimizer mainly follows bids, spend, win rate, and related proxy signals
- that is useful, but it is still a proxy system
- once conversion data and value data are connected, the recommendations can move from "traffic looks wasteful" to "traffic is low-value" or "traffic is worth keeping"

Current state:
- conversion ingestion exists
- AppsFlyer is the most mature path in the repo
- readiness diagnostics exist in the UI
- exact attribution depends on `clickid` coverage in creative links
- broad production proof across buyers is still missing

Next steps:
- validate AppsFlyer on real buyer data end to end
- finish exact and fallback join reporting in production workflows
- feed conversion and value evidence into optimizer scoring
- keep hard automation gated behind confidence and coverage thresholds

### 2. Language analysis as a real optional subsystem

Current state:
- the UI and API paths exist
- the feature is optional
- it is disabled by default in the GCP deploy path
- provider selection and key management exist for Gemini, Claude, and Grok

Next steps:
- keep provider selection coherent across UI, API, and docs
- evaluate provider quality and failure behavior in real operator workflows
- keep the feature optional and explicitly configured
- preserve manual override and operator review in the creative flow

### 3. Better operator proof, not bigger claims

Current state:
- the product is useful
- we do not yet have enough public evidence to claim a typical percentage uplift

Next steps:
- collect deployment-level before/after evidence where customers allow it
- measure exact improvements in areas we can prove
- keep public claims narrow until the evidence exists

### 4. Cleaner onboarding for self-hosted users

Current state:
- the install path works
- the docs were partly stale and are being corrected
- some advanced features still assume an operator who understands RTB and GCP well

Next steps:
- make the install path more linear
- keep dangerous credentials out of the early setup path
- improve first-run checks and failure messages
- make conversion setup less opaque

## Conversion and connector status

Safe current statement:
- AppsFlyer is the first-class attribution path in this repo
- other connector types are partly supported in code and taxonomy, but they are not equally proven in production

That means:
- do not present every connector as equally mature
- do not treat readiness diagnostics as proof of live attribution quality
- do not enable optimizer automation from fuzzy joins without strong evidence

## Not on the roadmap anymore

These items are removed from the active roadmap because they are already built or because they belonged in changelog or incident notes instead:
- old deployment incident notes
- old runtime blocker logs
- old translation audit snapshots that were true at the time but are no longer true
- completed route and seat-switch stabilization work
- completed OSS release hardening work

## Open questions

These still need real-world proof, not opinion:
- how much extra value remains after Google has already reduced obvious waste
- which buyers gain most from operator-side control versus bidder-side logic alone
- how much incremental value appears when conversion and lifetime value data are connected
- which language-analysis providers are reliable enough for production use

## Decision rule

A feature moves from roadmap to "built" only when these are all true:
- the code path exists
- the operator can use it without guesswork
- tests cover the main behavior
- the docs describe it accurately
- public claims about it are no stronger than the evidence
