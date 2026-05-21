# Creative Cache Notes

Short handoff for the HTML creative preview/cache issue investigated on 2026-05-15.

## Creative Checked

- Creative ID: `207568338_274438518_banner_normal_9709`
- Buyer: `6574658621`
- Format: `HTML`
- Google live API now returns 404 for this creative, so `Refetch live` cannot recover a newer payload.
- Cached Google payload was collected at `2026-05-08T01:37:53Z`.

## Serving Window

From cached performance/precompute data:

- First seen serving: `2026-03-25`
- Last seen serving: `2026-04-23`
- Impressions: about `458,656`
- Spend: about `$18,999.16`

## Tracking

No AppsFlyer URL was found.

Also no Adjust, Branch, Kochava, Singular, Tenjin, or Firebase Dynamic Link was found.

Tracking present in the cached payload is AmazingMoboosts-owned:

- `s.amazingmoboosts.com`
- `m.amazingmoboosts.com/click`
- `rtb.amazingmoboosts.com`

The creative has a click macro:

- `%%CLICK_URL_UNESC%%`

Declared destination is Google Play:

- `com.wgames.en.neverlandcasino`

## What We Cache Today

We cache creative metadata and payloads in Postgres, mainly:

- `creatives.raw_data`
- HTML snippet
- declared click URLs
- dimensions
- approval state
- collected timestamp

For previews:

- Video thumbnails are generated as local JPGs with `ffmpeg`.
- HTML thumbnails currently mostly come from extracting static image URLs from HTML snippets.
- We do not currently archive rendered HTML5 creative screenshots or all remote JS/iframe/assets.

For buyer `6574658621`, production showed:

- `3,622` cached creatives
- all currently `HTML`
- `1,541` with static-image HTML thumbnail rows
- `141` failed with `no_image_found`
- `1,940` with no thumbnail row yet

## Why This Creative Has No Thumbnail

The HTML snippet is script-driven. It builds a full-screen iframe to AmazingMoboosts instead of exposing a simple static `<img src=...>`.

Our current HTML thumbnail extractor does not execute the creative. It only parses static image URLs. For this creative:

- extracted image URLs: `0`
- `creative_thumbnails.status`: `failed`
- `error_reason`: `no_image_found`

The preview modal also strips scripts and iframes for safety, so this kind of HTML creative becomes visually empty in the in-app preview.

## Why Language Detection Says No Text/Image

The error:

`No text or image content found in HTML creative`

comes from the older basic language analyzer. It strips scripts, looks for text, then looks for static image URLs. This creative has neither after script stripping.

There is already a better screenshot/OCR pipeline in:

- `services/creative_evidence_service.py`

That service uses Playwright screenshots and Gemini/Claude/Grok OCR for geo-linguistic analysis. It is not currently wired into:

- card thumbnail generation
- `/thumbnails/extract-html`
- the basic language analyzer path

Also, Playwright/Chromium is not installed in the production API runtime image today.

## Recommended Fixes

1. Add a Playwright/Chromium HTML screenshot thumbnail generator, analogous to the video `ffmpeg` thumbnail path.
2. Store generated HTML screenshots under `~/.catscan/thumbnails` or GCS and write their URL into `creative_thumbnails`.
3. Reuse those screenshots for Gemini OCR/language detection.
4. Use `raw_data.collectedAt`, not `creatives.updated_at`, for creative cache freshness.
5. Change `Refetch live` messaging to show actual Google 404: creative no longer available in live API.
