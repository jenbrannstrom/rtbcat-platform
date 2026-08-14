import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const sidebarSource = readFileSync(
  new URL("../components/sidebar.tsx", import.meta.url),
  "utf8"
);

describe("sidebar overflow regression", () => {
  it("keeps the sidebar fixed-width and navigation vertical-only", () => {
    expect(sidebarSource).toMatch(
      /"flex min-h-0 flex-shrink-0 flex-col overflow-hidden [^"]*"/
    );
    expect(sidebarSource).toContain('collapsed ? "w-16" : "w-64"');
    expect(sidebarSource).toMatch(
      /<nav className="[^"]*min-w-0[^"]*overflow-x-hidden[^"]*overflow-y-auto[^"]*">/
    );
  });

  it("truncates the build label without shrinking the adjacent controls", () => {
    expect(sidebarSource).toContain(
      'className="flex-shrink-0 overflow-hidden px-2 py-3 border-t border-gray-200"'
    );
    expect(sidebarSource).toMatch(
      /<span\s+className="min-w-0 flex-1 truncate"\s+title=\{versionTitle\}/
    );
    expect(sidebarSource).toContain(
      'className="flex-shrink-0 whitespace-nowrap hover:text-primary-600 transition-colors"'
    );
    expect(sidebarSource).toMatch(
      /<button\s+onClick=\{toggleCollapsed\}\s+className="[^"]*flex-shrink-0"/
    );
  });
});
