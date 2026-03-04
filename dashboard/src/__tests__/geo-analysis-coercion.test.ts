/**
 * Regression tests for GeoAnalysisSection numeric coercion.
 *
 * Incident: Geo QPS page showed impossible totals (e.g. "e+62B") and
 * 100.0% win rates. Root cause: API returned numeric fields as strings,
 * so reduce() did string concatenation ("0" + "50000" = "050000") and
 * sort comparisons were lexicographic.
 *
 * Fix: All numeric fields coerced via asNumber() before arithmetic/sorting.
 */

import { describe, it, expect } from "vitest";
import { asNumber } from "@/lib/utils";
import { formatNumber } from "@/components/waste-analyzer/FunnelCard";

// Simulates the GeoPerformance shape with string values (as API can return)
interface StringyGeo {
  country: string;
  reached_queries: unknown;
  bids: unknown;
  auctions_won: unknown;
  impressions: unknown;
  win_rate: unknown;
}

const stringGeos: StringyGeo[] = [
  { country: "US", reached_queries: "50000", bids: "30000", auctions_won: "15000", impressions: null, win_rate: "30.0" },
  { country: "DE", reached_queries: "20000", bids: "10000", auctions_won: null, impressions: "8000", win_rate: "40.0" },
  { country: "JP", reached_queries: "80000", bids: "60000", auctions_won: "40000", impressions: null, win_rate: "50.0" },
];

const mixedGeos: StringyGeo[] = [
  { country: "US", reached_queries: 50000, bids: 30000, auctions_won: 15000, impressions: null, win_rate: 30.0 },
  { country: "DE", reached_queries: "20000", bids: null, auctions_won: null, impressions: "8000", win_rate: "40.0" },
  { country: "JP", reached_queries: "80000", bids: undefined, auctions_won: "40000", impressions: null, win_rate: 50.0 },
];

describe("Geo QPS reduce — totalReached", () => {
  it("produces correct sum when all values are strings", () => {
    const total = stringGeos.reduce(
      (sum, g) => sum + asNumber(g.reached_queries),
      0
    );
    expect(total).toBe(150000);
    expect(typeof total).toBe("number");
  });

  it("produces correct sum with mixed string/number inputs", () => {
    const total = mixedGeos.reduce(
      (sum, g) => sum + asNumber(g.reached_queries),
      0
    );
    expect(total).toBe(150000);
  });

  it("would concatenate strings without asNumber (proving the bug)", () => {
    // This demonstrates the exact bug: without coercion, reduce concatenates
    const buggyTotal = stringGeos.reduce(
      (sum, g) => sum + (g.reached_queries as number),
      0 as unknown as number
    );
    // Result is "0500002000080000" — a string, not 150000
    expect(typeof buggyTotal).toBe("string");
    expect(buggyTotal).not.toBe(150000);
  });
});

describe("Geo QPS reduce — totalWins", () => {
  it("produces correct sum with auctions_won/impressions fallback", () => {
    const total = stringGeos.reduce(
      (sum, g) => sum + asNumber(g.auctions_won ?? g.impressions),
      0
    );
    // US=15000, DE=8000 (impressions fallback), JP=40000
    expect(total).toBe(63000);
  });

  it("handles null auctions_won by falling back to impressions", () => {
    const geo: StringyGeo = {
      country: "XX",
      reached_queries: "1000",
      bids: "500",
      auctions_won: null,
      impressions: "200",
      win_rate: "20.0",
    };
    expect(asNumber(geo.auctions_won ?? geo.impressions)).toBe(200);
  });

  it("handles both null by returning 0", () => {
    const geo: StringyGeo = {
      country: "XX",
      reached_queries: "1000",
      bids: "500",
      auctions_won: null,
      impressions: null,
      win_rate: "20.0",
    };
    expect(asNumber(geo.auctions_won ?? geo.impressions)).toBe(0);
  });
});

describe("Geo QPS sort — numeric ordering with string values", () => {
  it("sorts by reached_queries numerically, not lexicographically", () => {
    const sorted = [...stringGeos].sort(
      (a, b) => asNumber(b.reached_queries) - asNumber(a.reached_queries)
    );
    expect(sorted.map((g) => g.country)).toEqual(["JP", "US", "DE"]);
  });

  it("sorts by win_rate numerically", () => {
    const sorted = [...stringGeos].sort(
      (a, b) => asNumber(b.win_rate) - asNumber(a.win_rate)
    );
    expect(sorted.map((g) => g.country)).toEqual(["JP", "DE", "US"]);
  });

  it("sorts by bids with null/undefined values", () => {
    const sorted = [...mixedGeos].sort(
      (a, b) => asNumber(b.bids) - asNumber(a.bids)
    );
    // US=30000, DE=null→0, JP=undefined→0
    expect(sorted[0].country).toBe("US");
  });
});

describe("Geo QPS win rate clamping", () => {
  it("clamps string win_rate to 0-100", () => {
    expect(Math.min(100, Math.max(0, asNumber("30.0")))).toBe(30.0);
    expect(Math.min(100, Math.max(0, asNumber("150.0")))).toBe(100);
    expect(Math.min(100, Math.max(0, asNumber("-5.0")))).toBe(0);
  });

  it("handles null/undefined win_rate", () => {
    expect(Math.min(100, Math.max(0, asNumber(null)))).toBe(0);
    expect(Math.min(100, Math.max(0, asNumber(undefined)))).toBe(0);
  });

  it("handles NaN win_rate", () => {
    const rate = asNumber(NaN);
    expect(rate).toBe(0);
    expect(() => rate.toFixed(1)).not.toThrow();
  });
});

describe("Geo QPS overall win rate calculation", () => {
  it("computes correct overall win rate from string inputs", () => {
    const totalReached = stringGeos.reduce(
      (sum, g) => sum + asNumber(g.reached_queries),
      0
    );
    const totalWins = stringGeos.reduce(
      (sum, g) => sum + asNumber(g.auctions_won ?? g.impressions),
      0
    );
    const overallWinRate =
      totalReached > 0 ? Math.min(100, (totalWins / totalReached) * 100) : 0;

    expect(totalReached).toBe(150000);
    expect(totalWins).toBe(63000);
    expect(overallWinRate).toBeCloseTo(42.0, 1);
    expect(Number.isFinite(overallWinRate)).toBe(true);
  });

  it("returns 0 when totalReached is 0", () => {
    const geos: StringyGeo[] = [
      { country: "XX", reached_queries: "0", bids: "0", auctions_won: "0", impressions: null, win_rate: "0" },
    ];
    const totalReached = geos.reduce(
      (sum, g) => sum + asNumber(g.reached_queries),
      0
    );
    const overallWinRate =
      totalReached > 0 ? Math.min(100, (0 / totalReached) * 100) : 0;
    expect(overallWinRate).toBe(0);
  });
});

describe("Geo QPS formatNumber with coerced values", () => {
  it("formats large coerced numbers with K/M/B suffixes", () => {
    expect(formatNumber(asNumber("50000"))).toBe("50.0K");
    expect(formatNumber(asNumber("1500000"))).toBe("1.5M");
    expect(formatNumber(asNumber("2000000000"))).toBe("2.0B");
  });

  it("formats small coerced numbers without suffix", () => {
    expect(formatNumber(asNumber("999"))).toBe("999");
    expect(formatNumber(asNumber("0"))).toBe("0");
  });

  it("formats null/undefined as 0", () => {
    expect(formatNumber(asNumber(null))).toBe("0");
    expect(formatNumber(asNumber(undefined))).toBe("0");
  });

  it("never produces exponential notation strings", () => {
    const result = formatNumber(asNumber("80000"));
    expect(result).not.toMatch(/e\+/);
    expect(result).toBe("80.0K");
  });
});
