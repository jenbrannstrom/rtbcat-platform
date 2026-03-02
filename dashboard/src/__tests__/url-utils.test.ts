import { describe, expect, it } from "vitest";

import {
  extractClickDestinationsFromHtmlSnippet,
  parseDestinationUrls,
} from "@/lib/url-utils";

describe("extractClickDestinationsFromHtmlSnippet", () => {
  it("extracts click destination from macro-prefixed href and ignores image asset URL", () => {
    const snippet = `
      <a href="%%CLICK_URL_UNESC%%https://example.com/landing?page=1">
        <img src="https://cdn.example.com/creative/banner.png" />
      </a>
    `;

    const urls = extractClickDestinationsFromHtmlSnippet(snippet);
    expect(urls).toEqual(["https://example.com/landing?page=1"]);
  });

  it("returns empty list when snippet only has unresolved click macro and asset URL", () => {
    const snippet = `
      <a href="%%CLICK_URL_UNESC%%">
        <img src="https://cdn.example.com/creative/banner.jpg" />
      </a>
    `;

    const urls = extractClickDestinationsFromHtmlSnippet(snippet);
    expect(urls).toEqual([]);
  });
});

describe("parseDestinationUrls", () => {
  it("filters asset URLs when real destination URLs are present", () => {
    const parsed = parseDestinationUrls(
      "https://cdn.example.com/creative/banner.png https://example.com/offer",
    );

    expect(parsed.map((p) => p.url)).toEqual(["https://example.com/offer"]);
    expect(parsed[0].isPrimary).toBe(true);
  });

  it("keeps asset URL when it is the only available URL", () => {
    const parsed = parseDestinationUrls("https://cdn.example.com/creative/banner.webp");
    expect(parsed).toHaveLength(1);
    expect(parsed[0].url).toBe("https://cdn.example.com/creative/banner.webp");
  });
});

