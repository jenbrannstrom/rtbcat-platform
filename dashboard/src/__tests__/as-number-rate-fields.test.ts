/**
 * Regression tests for asNumber() — the guard that prevents .toFixed() crashes
 * when API returns numeric fields as string, null, or undefined.
 *
 * Incident: commit e799687 fixed production crash:
 *   Uncaught TypeError: e.win_rate.toFixed is not a function
 *
 * Fields affected: win_rate, ctr, cpm, waste_rate, impressions, spend.
 * Components using asNumber: campaign-card, pretargeting-config-card,
 * config-breakdown-panel, PublisherPerformanceSection, campaigns/[id]/page.
 */

import { describe, it, expect } from "vitest";
import { asNumber } from "@/lib/utils";

describe("asNumber", () => {
  // --- Normal numeric values ---
  it("passes through a normal number", () => {
    expect(asNumber(54.5)).toBe(54.5);
  });

  it("passes through zero", () => {
    expect(asNumber(0)).toBe(0);
  });

  it("passes through negative numbers", () => {
    expect(asNumber(-12.3)).toBe(-12.3);
  });

  // --- String coercion (API sometimes returns strings) ---
  it("coerces a numeric string to number", () => {
    expect(asNumber("54.5")).toBe(54.5);
  });

  it("coerces integer string to number", () => {
    expect(asNumber("100")).toBe(100);
  });

  it("coerces '0' to 0", () => {
    expect(asNumber("0")).toBe(0);
  });

  // --- Null / undefined / missing fields ---
  it("returns fallback for null", () => {
    expect(asNumber(null)).toBe(0);
  });

  it("returns fallback for undefined", () => {
    expect(asNumber(undefined)).toBe(0);
  });

  // --- Invalid string values ---
  it("returns fallback for 'N/A'", () => {
    expect(asNumber("N/A")).toBe(0);
  });

  it("returns fallback for empty string", () => {
    expect(asNumber("")).toBe(0);
  });

  it("returns fallback for non-numeric string", () => {
    expect(asNumber("abc")).toBe(0);
  });

  // --- Edge cases ---
  it("returns fallback for NaN", () => {
    expect(asNumber(NaN)).toBe(0);
  });

  it("returns fallback for Infinity", () => {
    expect(asNumber(Infinity)).toBe(0);
  });

  it("returns fallback for -Infinity", () => {
    expect(asNumber(-Infinity)).toBe(0);
  });

  it("returns fallback for boolean true (coerces to 1 but we accept it)", () => {
    // Number(true) === 1, which is finite
    expect(asNumber(true)).toBe(1);
  });

  it("returns fallback for boolean false (coerces to 0)", () => {
    expect(asNumber(false)).toBe(0);
  });

  it("returns fallback for object", () => {
    expect(asNumber({})).toBe(0);
  });

  it("returns fallback for array", () => {
    expect(asNumber([])).toBe(0);
  });

  // --- Custom fallback ---
  // Note: Number(null) === 0 and Number(false) === 0, both finite, so fallback is NOT used.
  // Fallback only applies when Number(value) is NaN or Infinity.
  it("uses custom fallback for NaN-producing values", () => {
    expect(asNumber("N/A", 99.9)).toBe(99.9);
    expect(asNumber({}, -1)).toBe(-1);
    expect(asNumber(undefined, 42)).toBe(42);
  });

  it("does NOT use fallback for null (Number(null) === 0 is finite)", () => {
    expect(asNumber(null, -1)).toBe(0);
  });
});

/**
 * Simulate the exact patterns used in components to prove no crash.
 * These replicate the real render expressions:
 *   asNumber(perf.win_rate).toFixed(2)
 *   asNumber(config.waste_rate).toFixed(1)
 */
describe("asNumber().toFixed() — the crash pattern", () => {
  const shapes = [
    { label: "number", value: 54.5 },
    { label: "numeric string", value: "54.5" },
    { label: "null", value: null },
    { label: "undefined", value: undefined },
    { label: "invalid string 'N/A'", value: "N/A" },
    { label: "empty string", value: "" },
    { label: "NaN", value: NaN },
    { label: "Infinity", value: Infinity },
    { label: "object", value: {} },
  ];

  for (const { label, value } of shapes) {
    it(`win_rate=${label}: asNumber(value).toFixed(2) does not throw`, () => {
      expect(() => asNumber(value).toFixed(2)).not.toThrow();
      const result = asNumber(value).toFixed(2);
      expect(typeof result).toBe("string");
    });

    it(`ctr=${label}: asNumber(value).toFixed(2) does not throw`, () => {
      expect(() => asNumber(value).toFixed(2)).not.toThrow();
    });

    it(`waste_rate=${label}: asNumber(value).toFixed(1) does not throw`, () => {
      expect(() => asNumber(value).toFixed(1)).not.toThrow();
    });
  }

  it("number produces correct formatted output", () => {
    expect(asNumber(54.567).toFixed(2)).toBe("54.57");
  });

  it("numeric string produces correct formatted output", () => {
    expect(asNumber("54.567").toFixed(2)).toBe("54.57");
  });

  it("null produces zero fallback output", () => {
    expect(asNumber(null).toFixed(2)).toBe("0.00");
  });

  it("undefined produces zero fallback output", () => {
    expect(asNumber(undefined).toFixed(2)).toBe("0.00");
  });

  it("'N/A' produces zero fallback output", () => {
    expect(asNumber("N/A").toFixed(2)).toBe("0.00");
  });
});
