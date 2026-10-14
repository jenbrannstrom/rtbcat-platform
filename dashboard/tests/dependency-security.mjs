import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const braces = require("braces");

function nested(depth, open = "{", close = "}") {
  return open.repeat(depth) + "a,b" + close.repeat(depth);
}

function ast(depth) {
  let node = { type: "text", value: "a" };
  for (let i = 0; i < depth; i++) {
    const parent = { type: "brace", nodes: [node] };
    node.parent = parent;
    node = parent;
  }
  const root = { type: "root", nodes: [node] };
  node.parent = root;
  return root;
}

for (const method of ["parse", "compile", "expand", "stringify"]) {
  test(`${method} rejects excessive string nesting before stack exhaustion`, () => {
    for (const depth of [101, 1000, 4998]) {
      for (const [open, close] of [["{", "}"], ["(", ")"]]) {
        assert.throws(() => braces[method](nested(depth, open, close)), /exceeds max depth/);
      }
    }
  });
}

for (const method of ["compile", "expand", "stringify"]) {
  test(`${method} rejects excessive direct AST nesting`, () => {
    assert.throws(() => braces[method](ast(10000)), /exceeds max depth/);
  });
}

test("depth boundaries and custom limits remain bounded", () => {
  assert.doesNotThrow(() => braces.parse(nested(100)));
  assert.throws(() => braces.parse(nested(101)), /exceeds max depth/);
  assert.throws(() => braces.parse(nested(2), { maxDepth: 1.5 }), /exceeds max depth/);
  for (const maxDepth of [101, 10000, Infinity, NaN]) {
    assert.throws(() => braces.parse(nested(101), { maxDepth }), /exceeds max depth/);
  }
});

test("stringification keeps published escapeInvalid behavior", () => {
  for (const pattern of ["{{a}}", "{a,{b}}", "{{x}y}", "{a,{b,{c}}", "{}{a}", "{1..8}"]) {
    assert.equal(braces.stringify(pattern, { escapeInvalid: true }), pattern);
  }
});

test("ordinary expansion and literal escaped braces remain compatible", () => {
  assert.deepEqual(braces.expand("src/{app,components}/*.{ts,tsx}"), [
    "src/app/*.ts", "src/app/*.tsx", "src/components/*.ts", "src/components/*.tsx",
  ]);
  assert.deepEqual(braces.expand("item-{01..03}"), ["item-01", "item-02", "item-03"]);
  assert.equal(braces.stringify("\\{".repeat(200)), "{".repeat(200));
});

test("expansion rejects cyclic parent links", () => {
  const node = { type: "paren", nodes: [] };
  node.parent = node;
  assert.throws(() => braces.expand(node), /parent chain contains a cycle/);
});

test("glob consumers still match dashboard source files", () => {
  const micromatch = require("micromatch");
  const fastGlob = require("fast-glob");
  const paths = ["src/app/page.tsx", "src/components/card.tsx", "src/lib/utils.ts"];
  assert.deepEqual(micromatch(paths, "src/{app,components}/**/*.{ts,tsx}"), paths.slice(0, 2));
  assert.ok(fastGlob.sync("src/app/{page,layout}.tsx").includes("src/app/page.tsx"));
  assert.throws(() => micromatch.braces(nested(101)), /exceeds max depth/);
});
