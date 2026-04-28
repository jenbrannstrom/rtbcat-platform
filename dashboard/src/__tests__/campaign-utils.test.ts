import { describe, expect, it } from "vitest";

import {
  getCampaignClicks,
  getCampaignImpressions,
  getCampaignSpendMicros,
} from "@/components/campaigns/utils";

describe("campaign metric helpers", () => {
  it("prefers campaign-level performance over missing or stale creative metrics", () => {
    const campaign = {
      id: "camp-1",
      name: "Redbrid 7Be14",
      creative_ids: ["197224"],
      created_at: null,
      updated_at: null,
      performance: {
        spend_micros: 537_470_000,
        impressions: 205_553,
        clicks: 12,
      },
    };
    const creatives = [
      {
        id: "197224",
        format: "HTML",
        performance: {
          total_spend_micros: 1,
          total_impressions: 1,
          total_clicks: 1,
        },
      },
    ];

    expect(getCampaignSpendMicros(campaign, creatives)).toBe(537_470_000);
    expect(getCampaignImpressions(campaign, creatives)).toBe(205_553);
    expect(getCampaignClicks(campaign, creatives)).toBe(12);
  });

  it("falls back to campaign spend dollars and then creative summaries", () => {
    const baseCampaign = {
      id: "camp-1",
      name: "Cluster",
      creative_ids: [],
      created_at: null,
      updated_at: null,
    };

    expect(
      getCampaignSpendMicros(
        { ...baseCampaign, performance: { spend: 12.34 } },
        [],
      ),
    ).toBe(12_340_000);

    expect(
      getCampaignSpendMicros(baseCampaign, [
        { id: "1", format: "HTML", performance: { total_spend_micros: 20 } },
        { id: "2", format: "VIDEO", performance: { total_spend_micros: 30 } },
      ]),
    ).toBe(50);
  });
});
