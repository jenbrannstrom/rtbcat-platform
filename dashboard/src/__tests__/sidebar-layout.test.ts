import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const sidebarSource = readFileSync(
  new URL("../components/sidebar.tsx", import.meta.url),
  "utf8"
);
const popoverSource = readFileSync(
  new URL("../components/anchored-popover.tsx", import.meta.url),
  "utf8"
);

/**
 * Source-level regression guards for the sidebar shell.
 *
 * The 2026-08 overflow bug came from a footer label pushing the rail wider
 * than its fixed width; these assertions keep the shell invariants that
 * prevented it, without pinning the inner markup.
 */
describe("sidebar shell invariants", () => {
  it("keeps the rail fixed-width with vertical-only navigation scroll", () => {
    expect(sidebarSource).toMatch(
      /"flex min-h-0 shrink-0 flex-col overflow-hidden [^"]*"/
    );
    expect(sidebarSource).toContain('collapsed ? "w-16" : "w-64"');
    expect(sidebarSource).toMatch(
      /<nav\s+aria-label=\{[^}]+\}\s+className="[^"]*min-w-0[^"]*overflow-x-hidden[^"]*overflow-y-auto[^"]*"/
    );
  });

  it("renders the navigation as a flex column so the System group can pin to the bottom", () => {
    expect(sidebarSource).toMatch(/<nav[\s\S]*?className="[^"]*flex-col[^"]*"/);
    expect(sidebarSource).toContain('group.key === "system" && "mt-auto');
  });

  it("keeps the footer from growing the rail and truncates the version label", () => {
    expect(sidebarSource).toMatch(
      /className="shrink-0 overflow-hidden border-t border-gray-200 [^"]*"/
    );
    expect(sidebarSource).toMatch(/<VersionPopover\s+label=\{versionLabel\}/);
  });

  it("uses fixed-position popovers so the collapsed rail is not clipped", () => {
    expect(popoverSource).toContain('position: "fixed"');
    expect(sidebarSource).toContain('placement="right-start"');
  });

  it("persists only the collapsed state, not per-group expansion", () => {
    const storageKeys = sidebarSource.match(/localStorage\.(get|set)Item\(([A-Z_]+)/g) ?? [];
    const keyNames = new Set(storageKeys.map((m) => m.replace(/.*\(/, "")));
    expect([...keyNames]).toEqual(["SIDEBAR_COLLAPSED_KEY"]);
  });

  it("exposes active and expanded state to assistive tech", () => {
    expect(sidebarSource).toContain('aria-current={isActive ? "page" : undefined}');
    expect(sidebarSource).toContain("aria-expanded={isOpen}");
  });

  it("has no hard-coded English row labels", () => {
    expect(sidebarSource).not.toMatch(/"Click Macro Audit"|"Attribution Readiness"|"Collapse QPS section"/);
  });
});
