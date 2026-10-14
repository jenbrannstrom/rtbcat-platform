import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const ADVISORY = "GHSA-vfj7-8cjw-p6xm";
const BRACES_PATH = "node_modules/braces";
const SEVERITIES = ["info", "low", "moderate", "high", "critical"];
const FILES = ["index.js", "package.json", "lib/compile.js", "lib/constants.js",
  "lib/expand.js", "lib/parse.js", "lib/stringify.js", "lib/utils.js"];
const json = path => JSON.parse(readFileSync(path, "utf8"));
const sha256 = path => createHash("sha256").update(readFileSync(path)).digest("hex");

export function validateException(policy, now = Date.now()) {
  assert.equal(policy.advisory, ADVISORY, "Only the reviewed braces advisory is eligible");
  assert.equal(policy.package, "braces");
  assert.equal(policy.version, "3.0.3");
  const start = Date.parse(`${policy.approvedOn}T00:00:00Z`);
  const end = Date.parse(policy.expiresAt);
  assert(Number.isFinite(now) && Number.isFinite(start) && Number.isFinite(end), "Invalid exception dates");
  assert(end > start && end - start <= 30 * 86400000, "Exception must expire within 30 days");
  assert(now >= start && now < end, "braces exception is expired or not yet valid");
}

export function verifyIntegrity(root, policy, lock) {
  assert.equal(sha256(resolve(root, "package-lock.json")), policy.lockSha256, "Dependency lock changed; review exception");
  assert.equal(sha256(resolve(root, "patches/braces+3.0.3.patch")), policy.patchSha256, "Reviewed patch changed");
  const paths = Object.keys(lock.packages).filter(path => /(^|\/)node_modules\/braces$/.test(path));
  assert.deepEqual(paths, [BRACES_PATH], "Unexpected braces installation paths");
  assert.equal(lock.packages[BRACES_PATH].version, "3.0.3");
  assert.equal(lock.packages[BRACES_PATH].dev, true, "braces must be development-only");
  assert.deepEqual(Object.keys(policy.installedFilesSha256).sort(), [...FILES].sort(), "Incomplete patched-file manifest");
  for (const file of FILES) {
    assert.equal(sha256(resolve(root, BRACES_PATH, file)), policy.installedFilesSha256[file], `Patch missing or changed: ${file}`);
  }
}

export function assessReport(report, lock, { production = false } = {}) {
  assert.equal(report.auditReportVersion, 2, "Unsupported or failed npm audit response");
  assert(!report.error, "npm audit returned an error");
  assert(report.vulnerabilities && typeof report.vulnerabilities === "object" && !Array.isArray(report.vulnerabilities));
  const vulnerabilities = report.vulnerabilities;
  const counts = Object.fromEntries(SEVERITIES.map(severity => [severity, 0]));
  for (const [name, entry] of Object.entries(vulnerabilities)) {
    assert.equal(entry.name, name, "Malformed audit entry");
    assert(SEVERITIES.includes(entry.severity), "Unknown audit severity");
    counts[entry.severity]++;
  }
  assert.deepEqual(report.metadata?.vulnerabilities,
    { ...counts, total: Object.keys(vulnerabilities).length }, "Incomplete audit findings");

  // An indirect finding is eligible only if every path ends at this one advisory.
  function eligible(name, seen = new Set()) {
    assert(!seen.has(name), "Cyclic audit dependency path");
    const entry = vulnerabilities[name];
    assert(entry && entry.severity === "high", `Unapproved finding: ${name}`);
    assert(Array.isArray(entry.nodes) && entry.nodes.length > 0, "Missing affected package paths");
    for (const node of entry.nodes) {
      assert.equal(lock.packages[node]?.dev, true, `Exception cannot cover production package: ${node}`);
    }
    assert(Array.isArray(entry.via) && entry.via.length > 0, "Missing advisory provenance");
    for (const via of entry.via) {
      if (typeof via === "string") {
        eligible(via, new Set([...seen, name]));
      } else {
        assert.equal(name, "braces", `Unapproved direct advisory: ${name}`);
        assert.equal(via?.url, `https://github.com/advisories/${ADVISORY}`, "Unapproved advisory");
        assert.equal(via.name, "braces");
        assert.equal(via.dependency, "braces");
        assert.equal(via.severity, "high", "Changed advisory severity");
        assert.equal(via.range, "<=3.0.3", "Changed advisory range");
        assert.deepEqual(entry.nodes, [BRACES_PATH]);
        assert.equal(lock.packages[BRACES_PATH].version, "3.0.3");
      }
    }
  }

  const excepted = [];
  for (const [name, entry] of Object.entries(vulnerabilities)) {
    if (!["high", "critical"].includes(entry.severity)) continue;
    assert(!production, `Production audit is blocked: ${name}`);
    eligible(name);
    excepted.push(name);
  }
  return excepted;
}

function audit(root, production) {
  const args = ["audit", "--json", "--audit-level=high"];
  if (production) args.push("--omit=dev");
  const result = spawnSync("npm", args, { cwd: root, encoding: "utf8", timeout: 120000, maxBuffer: 16 * 1024 * 1024 });
  assert(!result.error && [0, 1].includes(result.status), `npm audit failed: ${result.error?.message || result.stderr}`);
  const report = JSON.parse(result.stdout);
  console.log(`${production ? "Production" : "Full"} npm audit: ${JSON.stringify(report.metadata?.vulnerabilities)}`);
  for (const [name, entry] of Object.entries(report.vulnerabilities || {})) {
    console.log(`  ${entry.severity}: ${name}`);
  }
  return report;
}

export function main() {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const policy = json(resolve(root, "security/braces-exception.json"));
  const lock = json(resolve(root, "package-lock.json"));
  validateException(policy);
  verifyIntegrity(root, policy, lock);
  const tests = spawnSync(process.execPath, ["--test", "tests/dependency-security.mjs"], { cwd: root, stdio: "inherit", timeout: 60000 });
  assert.equal(tests.status, 0, "Dependency attack and compatibility tests failed");
  assessReport(audit(root, true), lock, { production: true });
  const excepted = assessReport(audit(root, false), lock);
  console.log(`Release audit passed. ${ADVISORY}: ${excepted.length} development findings covered until ${policy.expiresAt}.`);
  console.log("All other high/critical findings block release. Raw npm audit continues to report the advisory.");
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try { main(); } catch (error) {
    console.error(`Release audit FAILED: ${error.message}`);
    process.exitCode = 1;
  }
}
