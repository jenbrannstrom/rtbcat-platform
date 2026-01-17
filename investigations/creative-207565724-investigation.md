# Creative Investigation Report

**Date:** 2026-01-14
**Investigator:** Cat-Scan Platform
**Status:** Completed - No Malicious Activity Detected

---

## Creative Details

| Field | Value |
|-------|-------|
| Creative ID | `207565724_intertplmraidexp_274436175_1780729_banner_intertplmraidexp_7993` |
| Buyer | Amazing MobYoung |
| Format | HTML (MRAID Expandable) |
| Google Status | Approved |
| Target Region | Vietnam |

---

## Investigation Trigger

Suspected discrepancy between declared destination URL and actual behavior. The creative is an HTML-based ad that fetches content dynamically from a server, with the server configured to detect investigative actions.

---

## Investigation Methodology

### Environment Setup
- VPN configured for Vietnam IP
- Chromium browser with DevTools monitoring
- Network request inspection enabled
- localStorage monitoring

### Steps Performed

1. **Initial Load Analysis**
   - Loaded creative from Cat-Scan dashboard
   - Captured network requests during creative render

2. **Click-Through Analysis**
   - Observed creative behavior on user interaction
   - Tracked redirect chain to final destination

3. **Template Examination**
   - Analyzed prize wheel template (`wheelPink_296.html`)
   - Examined end card template (`ecCatYear_vi.html`)
   - Reviewed embedded JavaScript (HdAd SDK)

4. **Data Collection Audit**
   - Inspected POST requests to `s.soundwavevnm.com`
   - Examined localStorage entries
   - Catalogued all tracking parameters

5. **Malicious Behavior Checks**
   - Canvas fingerprinting: **Not detected**
   - WebGL fingerprinting: **Not detected**
   - Audio fingerprinting: **Not detected**
   - APK sideloading: **Not detected**
   - Premium SMS triggers: **Not detected**
   - Credential harvesting: **Not detected**
   - Crypto mining: **Not detected**

---

## Technical Findings

### Creative Flow

```
Ad Impression
    ↓
Prize Wheel Template (wheelPink_296.html)
    ↓
User "wins" (100% win rate - wrate:100)
    ↓
End Card (ecCatYear_vi.html)
    ↓
Phone number collection (Vietnam sweepstakes)
    ↓
Play Store redirect
```

### Data Collected

The creative collects standard RTB tracking data:

| Parameter | Description | Example Value |
|-----------|-------------|---------------|
| `uid` | User identifier | `817efd67-20e4-4145-bf0b-e27c7a088272` |
| `did` | Device identifier | `817efd67-20e4-4145-bf0b-e27c7a088272` |
| `model` | Device model | `rmx3834` |
| `brand` | Device brand | `realme` |
| `osv` | OS version | `14` |
| `bundle` | App package name | `com.gamovation.tileclub` |
| `session` | Session ID | `zXZPY8TWE6MqYbmBgvQd9A` |
| `width/height` | Screen dimensions | `360x740` |
| `lang` | Device language | `en-GB` |

**Assessment:** Data collection is within normal RTB industry practices. No excessive or sensitive data gathering detected.

### Phone Number Collection

- Form presented in Vietnamese: "Nhập số điện thoại để tham gia" (Enter phone number to participate)
- Prize amount displayed: "1000000 ₫"
- Privacy policy and disclosures present on `soundwavevnm.com`

**Assessment:** Phone number collection appears to be for Vietnam-specific sweepstakes marketing. Disclosures are present, though could be more prominent.

### Final Destination

| Field | Value |
|-------|-------|
| URL | `https://play.google.com/store/apps/details?id=com.webcam.streaming.live` |
| App Name | Live Street Camera View |
| Developer | Quality App Zone (usama latif, Dubai UAE) |
| Downloads | 5M+ |
| Rating | 3.8 (11.2K reviews) |
| Play Store Status | Active/Legitimate |

**Assessment:** Click-through leads to a legitimate Google Play Store listing. App is real with significant install base.

---

## Conclusion

**Finding: Aggressive but Legitimate CPI Marketing**

This creative represents a gamified Cost-Per-Install (CPI) advertising campaign targeting Vietnamese users. While the tactics are aggressive (prize wheel with 100% "win" rate, phone number collection), no malicious technical behavior was detected:

- ✅ No device fingerprinting beyond standard tracking
- ✅ No malware or APK sideloading
- ✅ No premium SMS fraud vectors
- ✅ No credential harvesting
- ✅ Final destination is legitimate Play Store app
- ✅ Creative is Google-approved

The creative uses gamification to drive engagement and collect phone numbers for marketing purposes. This is a common practice in Southeast Asian mobile advertising markets. Users voluntarily provide phone numbers for sweepstakes participation.

**Recommendation:** No action required. Monitor for any changes in behavior or user complaints.

---

## Appendix: Key URLs

- Creative CDN: `cdn.soundwavevnm.com`
- Tracking Server: `s.soundwavevnm.com`
- Prize Wheel: `https://cdn.soundwavevnm.com/tml/wheelPink_296.html`
- End Card: `https://cdn.soundwavevnm.com/tml/ecCatYear_vi.html`
- Destination: `https://play.google.com/store/apps/details?id=com.webcam.streaming.live`
