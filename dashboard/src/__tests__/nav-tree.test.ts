import { describe, expect, it } from "vitest";
import { buildNavTree, readLabel, resolveActiveNav, type NavLeaf } from "@/lib/nav-tree";
import { en } from "@/lib/i18n";

const sudo = { restricted: false, hasSeatAdminAccess: true, isSudo: true };
const seatAdmin = { restricted: false, hasSeatAdminAccess: true, isSudo: false };
const readOnly = { restricted: false, hasSeatAdminAccess: false, isSudo: false };
const restricted = { restricted: true, hasSeatAdminAccess: false, isSudo: false };

function flatten(groups: ReturnType<typeof buildNavTree>) {
  return groups.flatMap((g) =>
    g.items.flatMap((i) => (i.kind === "leaf" ? [i.key] : [i.key, ...i.children.map((c) => c.key)])),
  );
}

describe("buildNavTree", () => {
  it("gives sudo all three groups with both system parents", () => {
    const groups = buildNavTree(sudo);
    expect(groups.map((g) => g.key)).toEqual(["optimize", "creatives", "system"]);
    const system = groups[2].items.map((i) => i.key);
    expect(system).toEqual(["settings", "admin"]);
  });

  it("gives a seat admin Settings but not Administration", () => {
    const groups = buildNavTree(seatAdmin);
    expect(groups[2].items.map((i) => i.key)).toEqual(["settings"]);
  });

  it("omits the System group entirely for a read-only user", () => {
    const groups = buildNavTree(readOnly);
    expect(groups.map((g) => g.key)).toEqual(["optimize", "creatives"]);
  });

  it("leaves a restricted user with the overview only", () => {
    const groups = buildNavTree(restricted);
    expect(flatten(groups)).toEqual(["overview"]);
  });

  it("nests the three creative audits under one parent", () => {
    const creatives = buildNavTree(readOnly)[1];
    const audits = creatives.items.find((i) => i.key === "audits");
    expect(audits?.kind).toBe("parent");
    expect(audits && audits.kind === "parent" ? audits.children.map((c) => c.key) : []).toEqual([
      "clickMacros",
      "languageFlags",
      "attributionReadiness",
    ]);
  });

  it("has no duplicate icons or keys across the sudo tree", () => {
    const groups = buildNavTree(sudo);
    const keys = flatten(groups);
    expect(new Set(keys).size).toBe(keys.length);
    const icons = groups.flatMap((g) =>
      g.items.flatMap((i) => (i.kind === "leaf" ? [i.icon] : [i.icon, ...i.children.map((c) => c.icon)])),
    );
    expect(new Set(icons).size).toBe(icons.length);
  });

  it("resolves every label key to an English string", () => {
    const groups = buildNavTree(sudo);
    for (const group of groups) {
      expect(readLabel(en, group.labelKey)).not.toBe(group.labelKey);
      for (const item of group.items) {
        expect(readLabel(en, item.labelKey)).not.toBe(item.labelKey);
        if (item.kind === "parent") {
          if (item.tagKey) expect(readLabel(en, item.tagKey)).not.toBe(item.tagKey);
          for (const child of item.children) {
            expect(readLabel(en, child.labelKey)).not.toBe(child.labelKey);
          }
        }
      }
    }
  });

  it("keeps settings and admin leaves out of buyer scoping", () => {
    const system = buildNavTree(sudo)[2];
    const leaves = system.items.flatMap((i) => (i.kind === "parent" ? i.children : [i as NavLeaf]));
    expect(leaves.every((l) => l.buyerScoped === false)).toBe(true);
  });
});

describe("resolveActiveNav", () => {
  const groups = buildNavTree(sudo);

  it("matches the overview on / only", () => {
    expect(resolveActiveNav("/", groups).itemKey).toBe("overview");
    expect(resolveActiveNav("/qps/geo", groups).itemKey).toBe("geoQps");
  });

  it("highlights one audit, not the library, on an audit page", () => {
    const active = resolveActiveNav("/creatives/click-macros", groups);
    expect(active.itemKey).toBe("clickMacros");
    expect(active.parentKey).toBe("audits");
    expect(active.groupKey).toBe("creatives");
  });

  it("highlights the library only on /creatives itself", () => {
    expect(resolveActiveNav("/creatives", groups).itemKey).toBe("library");
  });

  it("treats /clusters and /uploads as aliases", () => {
    expect(resolveActiveNav("/clusters", groups).itemKey).toBe("clusters");
    expect(resolveActiveNav("/campaigns/123", groups).itemKey).toBe("clusters");
    expect(resolveActiveNav("/uploads", groups).itemKey).toBe("import");
  });

  it("makes the Settings parent itself active on its index page", () => {
    const active = resolveActiveNav("/settings", groups);
    expect(active.itemKey).toBe("settings");
    expect(active.parentKey).toBeNull();
  });

  it("makes a settings child active with Settings as its parent", () => {
    const active = resolveActiveNav("/settings/accounts", groups);
    expect(active.itemKey).toBe("connectedAccounts");
    expect(active.parentKey).toBe("settings");
    expect(resolveActiveNav("/connect", groups).itemKey).toBe("connectedAccounts");
  });

  it("maps the legacy /admin/settings redirect onto Configuration", () => {
    expect(resolveActiveNav("/admin/settings", groups).itemKey).toBe("configuration");
  });

  it("returns nothing for unknown paths", () => {
    expect(resolveActiveNav("/setup", groups)).toEqual({ itemKey: null, parentKey: null, groupKey: null });
  });
});
