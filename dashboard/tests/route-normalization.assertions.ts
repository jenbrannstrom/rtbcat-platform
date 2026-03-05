import assert from "node:assert/strict";
import { normalizeRoutePath } from "../src/lib/route-normalization";

type Case = {
  name: string;
  pathname: string;
  cookieBuyerId?: string | null;
  expected: {
    targetPathname: string | null;
    ensurePublishersTab: boolean;
  };
};

const cases: Case[] = [
  {
    name: "legacy creatives alias without cookie",
    pathname: "/creatives",
    expected: { targetPathname: "/clusters", ensurePublishersTab: false },
  },
  {
    name: "legacy creatives alias with cookie buyer",
    pathname: "/creatives",
    cookieBuyerId: "1111111111",
    expected: { targetPathname: "/1111111111/clusters", ensurePublishersTab: false },
  },
  {
    name: "legacy creatives alias with buyer prefix",
    pathname: "/1111111111/creatives",
    expected: { targetPathname: "/1111111111/clusters", ensurePublishersTab: false },
  },
  {
    name: "legacy uploads alias with cookie buyer",
    pathname: "/uploads",
    cookieBuyerId: "1111111111",
    expected: { targetPathname: "/1111111111/import", ensurePublishersTab: false },
  },
  {
    name: "legacy waste-analysis alias with cookie buyer",
    pathname: "/waste-analysis",
    cookieBuyerId: "1111111111",
    expected: { targetPathname: "/1111111111", ensurePublishersTab: false },
  },
  {
    name: "legacy pretargeting publishers route without buyer",
    pathname: "/pretargeting/666666666666/publishers",
    expected: { targetPathname: "/bill_id/666666666666", ensurePublishersTab: true },
  },
  {
    name: "legacy pretargeting publishers route with buyer",
    pathname: "/1111111111/pretargeting/666666666666/publishers",
    expected: {
      targetPathname: "/1111111111/bill_id/666666666666",
      ensurePublishersTab: true,
    },
  },
  {
    name: "strip buyer prefix from non-scoped settings route",
    pathname: "/1111111111/settings/accounts",
    expected: { targetPathname: "/settings/accounts", ensurePublishersTab: false },
  },
  {
    name: "inject buyer prefix for scoped campaigns route",
    pathname: "/campaigns",
    cookieBuyerId: "1111111111",
    expected: { targetPathname: "/1111111111/campaigns", ensurePublishersTab: false },
  },
  {
    name: "inject buyer prefix for scoped bill route",
    pathname: "/bill_id/666666666666",
    cookieBuyerId: "1111111111",
    expected: {
      targetPathname: "/1111111111/bill_id/666666666666",
      ensurePublishersTab: false,
    },
  },
  {
    name: "keep already scoped route unchanged",
    pathname: "/1111111111/campaigns",
    cookieBuyerId: "1111111111",
    expected: { targetPathname: null, ensurePublishersTab: false },
  },
  {
    name: "keep settings route unchanged without buyer prefix",
    pathname: "/settings/accounts",
    cookieBuyerId: "1111111111",
    expected: { targetPathname: null, ensurePublishersTab: false },
  },
];

for (const c of cases) {
  const result = normalizeRoutePath(c.pathname, c.cookieBuyerId);
  assert.equal(
    result.targetPathname,
    c.expected.targetPathname,
    `${c.name}: targetPathname mismatch`
  );
  assert.equal(
    result.ensurePublishersTab,
    c.expected.ensurePublishersTab,
    `${c.name}: ensurePublishersTab mismatch`
  );
}

console.log(`Route normalization assertions passed (${cases.length} cases).`);

