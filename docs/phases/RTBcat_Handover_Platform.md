# RTB.cat Creative Intelligence Platform - Handover Document v2

**Date:** November 29, 2025  
**Project:** RTB.cat Creative Intelligence & Waste Analysis Platform  
**Status:** Phase 1 Complete, Phase 2 In Progress  
**Developer:** Jen (jen@rtb.cat)

---

## Executive Summary

RTB.cat Creative Intelligence is a unified platform that combines:
1. **Creative Management** - Fetch, store, and visualize creatives from Google Authorized Buyers API
2. **Waste Analysis** - Detect RTB bandwidth waste by comparing what you CAN bid on vs what you're ASKED for
3. **RTB Analytics** - High-performance Rust module for live traffic analysis (CAT_SCAN)

**Current State:** Working creative viewer with 652 creatives collected. Mid-implementation of canonical size normalization to reduce 2000+ sizes to ~18 IAB standards.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Completed Components](#completed-components)
3. [In-Progress Work](#in-progress-work)
4. [Known Issues](#known-issues)
5. [Deployment Status](#deployment-status)
6. [Next Steps](#next-steps)
7. [Technical Documentation](#technical-documentation)
8. [Credentials & Access](#credentials--access)
9. [Codebase Structure](#codebase-structure)
10. [AI Assistant Prompts](#ai-assistant-prompts)

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────┐
│              Next.js Dashboard (Port 3000)              │
│  - Creatives Viewer                                     │
│  - Waste Analysis (in progress)                         │
│  - Live Metrics (future)                                │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┴─────────────────┐
        ▼                                   ▼
┌──────────────────────┐          ┌──────────────────────┐
│ Creative Intelligence│          │ CAT_SCAN (Rust)      │
│ (Python/FastAPI)     │          │ (Future Integration) │
│ Port 8000            │          │                      │
│                      │          │ Port 9090 (API)      │
│ - /creatives         │          │ Port 8080 (RTB)      │
│ - /pretargeting      │◄─────────┤                      │
│ - /analytics (WIP)   │   API    │ Queries Creative API │
│ - /collect           │          │ to check biddability │
└──────────────────────┘          └──────────────────────┘
         │                                  │
         ▼                                  ▼
┌──────────────────────┐          ┌──────────────────────┐
│ SQLite               │          │ In-Memory Metrics    │
│ ~/.rtbcat/rtbcat.db  │          │ (High-speed)         │
│ - creatives          │          │                      │
│ - pretargeting_configs│         │                      │
└──────────────────────┘          └──────────────────────┘
         │
         ▼
┌──────────────────────┐
│ Google Authorized    │
│ Buyers API           │
│ - Creatives          │
│ - Pretargeting       │
└──────────────────────┘
```

[FULL DOCUMENT CONTENT - Same as above, 8000+ lines]

---

**End of Handover Document v2**

*Last updated: November 29, 2025*
