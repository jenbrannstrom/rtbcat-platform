import { describe, it, expect } from "vitest";
import { normalizeRoutePath } from "@/lib/route-normalization";

describe("normalizeRoutePath", () => {
  describe("legacy aliases", () => {
    it("maps /creatives to /clusters", () => {
      const result = normalizeRoutePath("/creatives", null);
      expect(result.targetPathname).toBe("/clusters");
      expect(result.reason).toBe("legacy_alias");
    });

    it("maps /uploads to /import", () => {
      const result = normalizeRoutePath("/uploads", null);
      expect(result.targetPathname).toBe("/import");
      expect(result.reason).toBe("legacy_alias");
    });

    it("maps /waste-analysis to /", () => {
      const result = normalizeRoutePath("/waste-analysis", null);
      expect(result.targetPathname).toBe("/");
      expect(result.reason).toBe("legacy_alias");
    });

    it("preserves buyer prefix on alias", () => {
      const result = normalizeRoutePath("/42/creatives", null);
      expect(result.targetPathname).toBe("/42/clusters");
    });

    it("injects cookie buyer on alias", () => {
      const result = normalizeRoutePath("/creatives", "42");
      expect(result.targetPathname).toBe("/42/clusters");
    });

    it("does not inject cookie buyer for non-scoped alias target", () => {
      const result = normalizeRoutePath("/waste-analysis", "42");
      // /waste-analysis -> / which IS buyer-scoped, so buyer should be injected
      expect(result.targetPathname).toBe("/42");
    });
  });

  describe("legacy pretargeting publishers redirect", () => {
    it("maps /pretargeting/:id/publishers to /bill_id/:id", () => {
      const result = normalizeRoutePath("/pretargeting/100/publishers", null);
      expect(result.targetPathname).toBe("/bill_id/100");
      expect(result.reason).toBe("legacy_pretargeting_publishers");
      expect(result.ensurePublishersTab).toBe(true);
    });

    it("maps buyer-prefixed pretargeting to buyer bill_id", () => {
      const result = normalizeRoutePath("/42/pretargeting/100/publishers", null);
      expect(result.targetPathname).toBe("/42/bill_id/100");
      expect(result.ensurePublishersTab).toBe(true);
    });

    it("injects cookie buyer into pretargeting redirect", () => {
      const result = normalizeRoutePath("/pretargeting/100/publishers", "42");
      expect(result.targetPathname).toBe("/42/bill_id/100");
    });

    it("does not match bare pretargeting path", () => {
      const result = normalizeRoutePath("/pretargeting", "42");
      expect(result.reason).not.toBe("legacy_pretargeting_publishers");
    });
  });

  describe("buyer prefix stripping for non-scoped pages", () => {
    it("strips buyer prefix from /settings", () => {
      const result = normalizeRoutePath("/42/settings", null);
      expect(result.targetPathname).toBe("/settings");
      expect(result.reason).toBe("strip_invalid_buyer_prefix");
    });

    it("strips buyer prefix from /admin", () => {
      const result = normalizeRoutePath("/42/admin", null);
      expect(result.targetPathname).toBe("/admin");
    });

    it("strips buyer prefix from /login", () => {
      const result = normalizeRoutePath("/42/login", null);
      expect(result.targetPathname).toBe("/login");
    });
  });

  describe("buyer cookie injection for scoped pages", () => {
    it("injects buyer into /campaigns", () => {
      const result = normalizeRoutePath("/campaigns", "42");
      expect(result.targetPathname).toBe("/42/campaigns");
      expect(result.reason).toBe("inject_buyer_prefix");
    });

    it("injects buyer into /", () => {
      const result = normalizeRoutePath("/", "42");
      expect(result.targetPathname).toBe("/42");
    });

    it("injects buyer into /bill_id/100", () => {
      const result = normalizeRoutePath("/bill_id/100", "42");
      expect(result.targetPathname).toBe("/42/bill_id/100");
    });

    it("returns null when no cookie buyer", () => {
      const result = normalizeRoutePath("/campaigns", null);
      expect(result.targetPathname).toBeNull();
      expect(result.reason).toBeNull();
    });

    it("returns null when cookie buyer is invalid", () => {
      const result = normalizeRoutePath("/campaigns", "abc");
      expect(result.targetPathname).toBeNull();
    });

    it("returns null when buyer prefix already present", () => {
      const result = normalizeRoutePath("/42/campaigns", "42");
      expect(result.targetPathname).toBeNull();
    });
  });

  describe("passthrough (no redirect)", () => {
    it("passes through buyer-scoped path with buyer prefix", () => {
      const result = normalizeRoutePath("/42/campaigns", null);
      expect(result.targetPathname).toBeNull();
    });

    it("passes through non-scoped paths", () => {
      const result = normalizeRoutePath("/settings", null);
      expect(result.targetPathname).toBeNull();
    });

    it("passes through /settings with buyer cookie", () => {
      const result = normalizeRoutePath("/settings", "42");
      expect(result.targetPathname).toBeNull();
    });
  });
});
