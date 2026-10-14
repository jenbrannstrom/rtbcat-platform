import assert from "node:assert/strict";
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { assessReport, validateException, verifyIntegrity } from "../scripts/audit-release.mjs";

const root = fileURLToPath(new URL("..", import.meta.url));
const policy = JSON.parse(readFileSync(resolve(root, "security/braces-exception.json")));
const now = Date.parse("2026-10-14T12:00:00Z");
function fixture() {
  const entry = {
    name: "braces", severity: "high", nodes: ["node_modules/braces"],
    via: [{ name: "braces", dependency: "braces", severity: "high", range: "<=3.0.3",
      url: "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm" }],
  };
  return {
    report: { auditReportVersion: 2, vulnerabilities: {
      braces: entry,
      micromatch: { name: "micromatch", severity: "high", nodes: ["node_modules/micromatch"], via: ["braces"] },
    }, metadata: { vulnerabilities: { info: 0, low: 0, moderate: 0, high: 2, critical: 0, total: 2 } } },
    lock: { packages: {
      "node_modules/braces": { version: "3.0.3", dev: true },
      "node_modules/micromatch": { version: "4.0.8", dev: true },
    } },
  };
}

test("only the single reviewed advisory and its development paths pass", () => {
  const { report, lock } = fixture();
  assert.deepEqual(assessReport(report, lock), ["braces", "micromatch"]);
  validateException(policy, now);
});

test("exception expires at the boundary and cannot exceed 30 days", () => {
  assert.throws(() => validateException(policy, Date.parse(policy.expiresAt)), /expired/);
  assert.throws(() => validateException(policy, Date.parse("2026-10-13")), /not yet valid/);
  assert.throws(() => validateException({ ...policy, expiresAt: "2026-11-14T00:00:00Z" }, now), /30 days/);
  assert.throws(() => validateException({ ...policy, expiresAt: "bad" }, now), /Invalid/);
  assert.throws(() => validateException({ ...policy, advisory: "GHSA-other" }, now));
});

test("production findings never receive an exception", () => {
  const { report, lock } = fixture();
  assert.throws(() => assessReport(report, lock, { production: true }), /Production audit is blocked/);
  lock.packages["node_modules/micromatch"].dev = false;
  assert.throws(() => assessReport(report, lock), /production package/);
});

test("new, changed, and critical advisories are blocked", () => {
  for (const change of [
    via => { via.url = "https://github.com/advisories/GHSA-other"; },
    via => { via.severity = "critical"; },
    via => { via.range = "*"; },
  ]) {
    const { report, lock } = fixture();
    change(report.vulnerabilities.braces.via[0]);
    assert.throws(() => assessReport(report, lock));
  }
  const { report, lock } = fixture();
  report.vulnerabilities.braces.via.push({ ...report.vulnerabilities.braces.via[0], url: "https://github.com/advisories/GHSA-new" });
  assert.throws(() => assessReport(report, lock), /Unapproved advisory/);
  report.vulnerabilities.micromatch.severity = "critical";
  report.metadata.vulnerabilities.high--;
  report.metadata.vulnerabilities.critical++;
  assert.throws(() => assessReport(report, lock));
});

test("missing and cyclic advisory paths fail closed", () => {
  for (const via of [[], ["missing"], ["micromatch"]]) {
    const { report, lock } = fixture();
    report.vulnerabilities.micromatch.via = via;
    assert.throws(() => assessReport(report, lock));
  }
});

test("audit errors, missing findings, and unknown schemas are blocked", () => {
  for (const report of [{}, { auditReportVersion: 2, error: {} }, { auditReportVersion: 1 }]) {
    assert.throws(() => assessReport(report, fixture().lock));
  }
  const { report, lock } = fixture();
  delete report.vulnerabilities.braces;
  assert.throws(() => assessReport(report, lock), /Incomplete audit/);
});

test("changed package versions and unlisted package paths are blocked", () => {
  const { report, lock } = fixture();
  lock.packages["node_modules/braces"].version = "3.0.2";
  assert.throws(() => assessReport(report, lock));
  lock.packages["node_modules/braces"].version = "3.0.3";
  report.vulnerabilities.braces.nodes.push("node_modules/other/node_modules/braces");
  assert.throws(() => assessReport(report, lock));
});

test("clean reports and lower-severity findings retain the high/critical threshold", () => {
  const { report, lock } = fixture();
  report.vulnerabilities = {};
  report.metadata.vulnerabilities = { info: 0, low: 0, moderate: 0, high: 0, critical: 0, total: 0 };
  assert.deepEqual(assessReport(report, lock, { production: true }), []);
  report.vulnerabilities.example = { name: "example", severity: "moderate" };
  report.metadata.vulnerabilities.moderate = 1;
  report.metadata.vulnerabilities.total = 1;
  assert.deepEqual(assessReport(report, lock), []);
});

test("real patch integrity rejects altered files, lock, patch, or manifest", () => {
  const temp = mkdtempSync(resolve(tmpdir(), "rtbcat-audit-test-"));
  try {
    for (const path of ["package-lock.json", "patches", "node_modules/braces"]) {
      cpSync(resolve(root, path), resolve(temp, path), { recursive: true });
    }
    const lock = JSON.parse(readFileSync(resolve(temp, "package-lock.json")));
    verifyIntegrity(temp, policy, lock);
    for (const path of ["node_modules/braces/lib/parse.js", "package-lock.json", "patches/braces+3.0.3.patch"]) {
      const file = resolve(temp, path);
      const original = readFileSync(file);
      writeFileSync(file, "tampered");
      assert.throws(() => verifyIntegrity(temp, policy, lock));
      writeFileSync(file, original);
    }
    assert.throws(() => verifyIntegrity(temp, { ...policy, installedFilesSha256: {} }, lock), /Incomplete/);
    lock.packages["node_modules/nested/node_modules/braces"] = { version: "3.0.3", dev: true };
    assert.throws(() => verifyIntegrity(temp, policy, lock), /installation paths/);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
});
