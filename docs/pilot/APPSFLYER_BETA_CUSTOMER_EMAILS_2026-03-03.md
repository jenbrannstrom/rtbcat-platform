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

## Internal: Create Local-Admin Users (Martin and Siu)

Goal: grant seat-scoped local-admin only (not sudo).

UI steps:
1. Open `/admin/users` as a sudo operator.
2. Create user:
   - Email: (customer email)
   - Display name: `Martin` or `Siu`
   - Role: `admin` (local-admin role)
   - Auth method: `oauth-precreate` (or local-password if requested)
3. In the same user record, add Seat Permission:
   - Martin -> buyer `6574658621`, access level `admin`
   - Siu -> buyer `6634662463`, access level `admin`
4. Ensure there are no extra seats assigned.
5. Ensure no global sudo/admin escalation permissions are granted.
6. Ask user to log in and verify they can manage only their assigned seat.

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

中文版本（置顶）

主题：请协助开启 AppsFlyer 到 Cat-Scan 的回传（Beta）

Hi Dea，

我们已准备好为你们的 Cat-Scan 席位开启闭环转化归因。  
请在 AppsFlyer 中添加以下回传地址：

`https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=299038253`

请求设置：
- Method: `POST`
- Header: `X-Webhook-Secret: {{SECRET_SHARED_SEPARATELY}}`
- Content-Type: `application/json`

AppsFlyer 导航路径：
1. 选择应用（`com.drop.frenzy.bubbly`, `com.btools.bloods.statrs`）。
2. 首选：**Configuration** -> **Push API**（或 **Export/Raw Data Export** -> **Push API**）。
3. 备选：**Configuration** -> **Integrated Partners** -> partner -> **Postbacks**。
4. 填入上方 endpoint URL 与 secret header 后保存。

请先发送 1 条测试转化，并回复：
- UTC timestamp
- App ID
- Event name

我们验证通过后，会确认正式开启 beta。  

谢谢，  
{{Your Name}}

English version

Subject: Action needed: enable AppsFlyer postback to Cat-Scan (beta)

Hi Dea,

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

中文版本（置顶）

主题：邀请加入 Cat-Scan 的 AppsFlyer 归因 Beta

Hi Alan，

我们正在为你们的席位接入 Cat-Scan 归因 Beta。  
请在 AppsFlyer 中配置以下回传地址：

`https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=1487810529`

请求设置：
- Method: `POST`
- Header: `X-Webhook-Secret: {{SECRET_SHARED_SEPARATELY}}`
- Content-Type: `application/json`

AppsFlyer 导航路径：
1. 选择目标应用。
2. 首选：**Configuration** -> **Push API**。
3. 备选：**Configuration** -> **Integrated Partners** -> partner -> **Postbacks**。
4. 填入 endpoint URL 与 secret header 后保存。

请先发送 1 条测试转化，并回复：
- UTC timestamp
- App ID
- Event name

如果你们的点击链接还不是 AppsFlyer 链接，请回复我们，我们会提供简短迁移模板。  

谢谢，  
{{Your Name}}

English version

Subject: Invitation: AppsFlyer attribution beta for your Cat-Scan seat

Hi Alan,

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

中文版本（置顶）

主题：Cat-Scan Beta：可选接入 AppsFlyer 转化回传

Hi Martin，

我们正在为你们的席位开放 Cat-Scan 归因 Beta。  
我们现在正式启动 `scan.rtb.cat` 的 Beta 阶段，目标是帮助你们提升投放效率、减少浪费并提高利润空间。  
如果你们使用 AppsFlyer，请配置以下地址：

`https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=6574658621`

请求设置：
- Method: `POST`
- Header: `X-Webhook-Secret: {{SECRET_SHARED_SEPARATELY}}`
- Content-Type: `application/json`

AppsFlyer 导航路径：
1. 选择目标应用。
2. 首选：**Configuration** -> **Push API**。
3. 备选：**Configuration** -> **Integrated Partners** -> partner -> **Postbacks**。
4. 填入 endpoint URL 与 secret header 后保存。

请发送 1 条测试转化，并回复时间/app/event 供我们验证。  
如果暂未使用 AppsFlyer，请直接回复 “no AppsFlyer”，我们会提供替代 beta 接入路径。  

谢谢，  
{{Your Name}}

English version

Subject: Cat-Scan beta: optional AppsFlyer conversion feed setup

Hi Martin,

We are opening Cat-Scan attribution beta for your seat.
We are now launching the `scan.rtb.cat` beta, designed to increase efficiency, reduce waste, and improve profitability.

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

中文版本（置顶）

主题：Cat-Scan Beta 接入：转化归因数据输入

Hi Siu，

我们正在为你们的席位接入 Cat-Scan 转化归因 Beta。  
我们现在正式启动 `scan.rtb.cat` 的 Beta 阶段，目标是帮助你们提升投放效率、减少浪费并提高利润空间。  
如果你们使用 AppsFlyer，请配置以下地址：

`https://scan.rtb.cat/api/conversions/appsflyer/postback?buyer_id=6634662463`

请求设置：
- Method: `POST`
- Header: `X-Webhook-Secret: {{SECRET_SHARED_SEPARATELY}}`
- Content-Type: `application/json`

AppsFlyer 导航路径：
1. 选择目标应用。
2. 首选：**Configuration** -> **Push API**。
3. 备选：**Configuration** -> **Integrated Partners** -> partner -> **Postbacks**。
4. 填入 endpoint URL 与 secret header 后保存。

请发送 1 条测试转化，并回复：
- UTC timestamp
- App ID
- Event name

如果暂未使用 AppsFlyer，请回复我们，我们会提供非 AppsFlyer 的 beta 方案。  

谢谢，  
{{Your Name}}

English version

Subject: Cat-Scan beta onboarding: conversion attribution input

Hi Siu,

We are onboarding your seat to Cat-Scan conversion attribution beta.
We are now launching the `scan.rtb.cat` beta, designed to increase efficiency, reduce waste, and improve profitability.

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
