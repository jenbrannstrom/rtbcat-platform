import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join, relative } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const root = dirname(dirname(fileURLToPath(import.meta.url)));
const pluginRequire = createRequire(require.resolve("@next/eslint-plugin-next"));
const { getRootDirs } = pluginRequire("./utils/get-root-dirs.js");

// The replacement is scoped to Next 16.4.0's directory lookup, which uses
// globSync(pattern, { onlyDirectories: true }). It is not a global fast-glob alias.
test("Next uses the directory adapter without the vulnerable chain", () => {
  const lock = JSON.parse(readFileSync(join(root, "package-lock.json"), "utf8"));
  for (const [path, pkg] of Object.entries(lock.packages)) {
    assert(!/(^|\/)node_modules\/(braces|micromatch|patch-package)$/.test(path), `Removed dependency returned: ${path}`);
    assert.notEqual(pkg.name, "braces", `Renamed braces dependency: ${path}`);
    if (/(^|\/)node_modules\/fast-glob$/.test(path)) {
      assert.equal(pkg.link, true);
      assert.equal(pkg.resolved, "vendor/next-eslint-glob");
    }
  }
  const replacement = pluginRequire("fast-glob/package.json");
  assert.equal(replacement.name, "@rtbcat/next-eslint-glob");
  assert.equal(replacement.dependencies.tinyglobby, "0.2.17");
});

function fixture(t) {
  const dir = mkdtempSync(join(tmpdir(), "rtbcat-lint-roots-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  for (const name of ["apps/dashboard/pages", "apps/admin/pages", "other"]) {
    mkdirSync(join(dir, name), { recursive: true });
  }
  writeFileSync(join(dir, "apps", "not-a-directory"), "fixture");
  return dir;
}

function roots(cwd, rootDir) {
  return getRootDirs({ cwd, settings: { next: { rootDir } } }).sort();
}

test("Next retains its default app root", t => {
  const dir = fixture(t);
  assert.deepEqual(roots(dir), [dir]);
});

test("Next resolves workspace directories and excludes ordinary files", t => {
  const dir = fixture(t);
  assert.deepEqual(roots(dir, `${dir}/apps/*`), [join(dir, "apps/admin"), join(dir, "apps/dashboard")]);
});

test("Next supports brace patterns, explicit roots, root arrays and missing paths", t => {
  const dir = fixture(t);
  const expected = [join(dir, "apps/admin"), join(dir, "apps/dashboard")];
  assert.deepEqual(roots(dir, `${dir}/apps/{dashboard,admin}`), expected);
  assert.deepEqual(roots(dir, [expected[1], expected[0], 123]), expected);
  assert.deepEqual(roots(dir, `${dir}/missing/*`), []);
});

test("Next normalizes Windows path separators before directory lookup", t => {
  const dir = fixture(t);
  assert.deepEqual(roots(dir, `${dir}/apps/*`.replaceAll("/", "\\")), roots(dir, `${dir}/apps/*`));
});

test("Next's page-link rule still detects internal HTML links", async t => {
  const dir = fixture(t);
  writeFileSync(join(dir, "apps/dashboard/pages/about.tsx"), "export default function About() { return null; }");
  const { ESLint } = require("eslint");
  const eslint = new ESLint({
    cwd: root,
    overrideConfigFile: true,
    overrideConfig: [{
      files: ["**/*.jsx"],
      languageOptions: { parserOptions: { ecmaFeatures: { jsx: true } } },
      plugins: { "@next/next": require("@next/eslint-plugin-next") },
      settings: { next: { rootDir: `${dir}/apps/*` } },
      rules: { "@next/next/no-html-link-for-pages": "error" },
    }],
  });
  const [result] = await eslint.lintText('const link = <a href="/about">About</a>;', { filePath: "fixture.jsx" });
  assert.equal(result.errorCount, 1);
  assert.equal(result.messages[0].ruleId, "@next/next/no-html-link-for-pages");
});

test("Tailwind 4 class merging preserves local utility overrides", () => {
  const { twMerge } = require("tailwind-merge");
  assert.equal(twMerge("shadow-sm", "shadow-xs"), "shadow-xs");
  assert.equal(twMerge("rounded-sm", "rounded-lg"), "rounded-lg");
  assert.equal(twMerge("outline-hidden", "outline-none"), "outline-none");
  assert.equal(twMerge("shrink-0", "shrink"), "shrink");
});


test("the directory adapter refuses unsupported glob APIs", () => {
  const { globSync } = pluginRequire("fast-glob");
  assert.throws(() => globSync("src/*", { onlyFiles: true }), /Unsupported/);
  assert.throws(() => globSync(["src/*"], { onlyDirectories: true }), /Unsupported/);
});


test("Next preserves relative root paths without expanding their descendants", t => {
  const dir = fixture(t);
  const path = relative(process.cwd(), dir).replaceAll("\\", "/");
  assert.deepEqual(roots(dir, `${path}/apps/{dashboard,admin}`), [
    `${path}/apps/admin`, `${path}/apps/dashboard`,
  ]);
});
