# AppsFlyer Beta Customer Emails (Pilot Pack)

Date: March 3, 2026  
Owner: Cat-Scan Ops

## Send Notes

- Share webhook secret separately (not in email body).
- Ask for exactly 1 test event first.
- Include UI navigation steps so the customer knows exactly where to configure this.
- After customer confirms, validate with:
  - `scripts/run_appsflyer_phase_a_audit.sh --buyer-id <id> --from-db --db-since-days 30`
  - `scripts/run_conversion_attribution_phase_b_report.sh --buyer-id <id> --source-type appsflyer --days 14`

## AppsFlyer UI Navigation (copy into each email)

Use this block in customer instructions:

### Preferred route: Push API endpoint screen

1. Log in to AppsFlyer and select the target app.
2. Open **Configuration**.
3. Open **Push API** (sometimes shown under **Export** or **Raw Data Export** in some accounts).
4. Add a new endpoint/subscription.
5. Set:
   - Endpoint URL: `https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=<BUYER_ID>`
   - Method: `POST`
   - Header: `X-Webhook-Secret: <SECRET>`
   - Content-Type: `application/json`
6. Save and send one test event.

### Fallback route: Integrated Partner postback screen

1. Log in to AppsFlyer and select the target app.
2. Open **Configuration** -> **Integrated Partners**.
3. Add/select the partner used for this media source setup.
4. Go to the **Postbacks** tab.
5. Set partner/default postback URL to:  
   `https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=<BUYER_ID>`
6. Add header `X-Webhook-Secret: <SECRET>` if the screen supports custom headers.
7. Save and send one test event.

Notes:
- Repeat per app if they run multiple app IDs.
- AppsFlyer menu labels can differ slightly by account tier; if they cannot find Push API, use the Integrated Partner route.

---

## 1) Tuky Display (Buyer 299038253)

Subject: Action needed: enable AppsFlyer postback to Cat-Scan (beta)

Hi {{Name}},

We are ready to enable closed-loop conversion attribution for your Cat-Scan seat.

Please add this AppsFlyer postback endpoint:

`https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=299038253`

Request settings:
- Method: `POST`
- Header: `X-Webhook-Secret: {{SECRET_SHARED_SEPARATELY}}`
- Content-Type: `application/json`

Navigation in AppsFlyer:
1. Select app (`com.drop.frenzy.bubbly`, `com.btools.bloods.statrs`).
2. Preferred: **Configuration** -> **Push API** (or **Export/Raw Data Export** -> **Push API**).
3. Fallback: **Configuration** -> **Integrated Partners** -> partner -> **Postbacks**.
4. Add the endpoint URL above and secret header.

Please send one test conversion first and reply with:
- UTC timestamp
- App ID
- Event name

After we validate ingestion, we will confirm production beta enablement.

Thanks,  
{{Your Name}}

---

## 2) Amazing Design Tools LLC (Buyer 1487810529)

Subject: Invitation: AppsFlyer attribution beta for your Cat-Scan seat

Hi {{Name}},

We are onboarding your seat to Cat-Scan attribution beta.

Please configure this AppsFlyer postback endpoint:

`https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=1487810529`

Request settings:
- Method: `POST`
- Header: `X-Webhook-Secret: {{SECRET_SHARED_SEPARATELY}}`
- Content-Type: `application/json`

Navigation in AppsFlyer:
1. Select target app.
2. Preferred: **Configuration** -> **Push API**.
3. Fallback: **Configuration** -> **Integrated Partners** -> partner -> **Postbacks**.
4. Add endpoint URL and secret header, then save.

Please send one test conversion first and share:
- UTC timestamp
- App ID
- Event name

If your click URLs are not yet AppsFlyer-based, reply and we will send a short migration template.

Thanks,  
{{Your Name}}

---

## 3) Amazing Moboost (Buyer 6574658621)

Subject: Cat-Scan beta: optional AppsFlyer conversion feed setup

Hi {{Name}},

We are opening Cat-Scan attribution beta for your seat.

If you use AppsFlyer, please configure:

`https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=6574658621`

Request settings:
- Method: `POST`
- Header: `X-Webhook-Secret: {{SECRET_SHARED_SEPARATELY}}`
- Content-Type: `application/json`

Navigation in AppsFlyer:
1. Select target app.
2. Preferred: **Configuration** -> **Push API**.
3. Fallback: **Configuration** -> **Integrated Partners** -> partner -> **Postbacks**.
4. Add endpoint URL and secret header, then save.

Please send one test conversion and reply with timestamp/app/event so we can validate.

If you do not use AppsFlyer today, reply "no AppsFlyer" and we will enroll you through alternate beta conversion input.

Thanks,  
{{Your Name}}

---

## 4) Amazing MobYoung (Buyer 6634662463)

Subject: Cat-Scan beta onboarding: conversion attribution input

Hi {{Name}},

We are onboarding your seat to Cat-Scan conversion attribution beta.

If you use AppsFlyer, please configure:

`https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=6634662463`

Request settings:
- Method: `POST`
- Header: `X-Webhook-Secret: {{SECRET_SHARED_SEPARATELY}}`
- Content-Type: `application/json`

Navigation in AppsFlyer:
1. Select target app.
2. Preferred: **Configuration** -> **Push API**.
3. Fallback: **Configuration** -> **Integrated Partners** -> partner -> **Postbacks**.
4. Add endpoint URL and secret header, then save.

Please send one test conversion and share:
- UTC timestamp
- App ID
- Event name

If AppsFlyer is not in use, reply and we will provide the non-AppsFlyer beta path.

Thanks,  
{{Your Name}}

---

## 48-Hour Follow-Up (No Response)

Subject: Follow-up: AppsFlyer beta setup for your Cat-Scan seat

Hi {{Name}},

Quick follow-up on the AppsFlyer beta setup.

Can you confirm one of the following:
1. "Configured" (and share one test event timestamp), or
2. "Need help", or
3. "No AppsFlyer in use"

Once we receive your test event, we will validate and confirm seat activation.

Thanks,  
{{Your Name}}
