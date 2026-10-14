# Development dependency mitigation

## braces / GHSA-vfj7-8cjw-p6xm

As of 2026-10-14, npm publishes `braces` 3.0.3 with no official fixed release.
The dashboard receives it through Tailwind and the Next.js ESLint plugin.
`patch-package`, used to apply the fix, also has a dependency path to the same
deduplicated package. These are development dependencies.

`dashboard/patches/braces+3.0.3.patch` backports the five library changes from
[upstream PR 72](https://github.com/micromatch/braces/pull/72), reviewed at commit
`28d440b5dd449dbf1fe6f3506cf94ecca4d02660`. The PR is closed and unmerged; this is
a local mitigation, not an upstream release or maintainer endorsement.

The patch limits parser and AST traversal depth to 100, caps caller-supplied
depth limits, preserves the published `escapeInvalid` behavior, and rejects
cyclic parent chains in expansion. Normal patterns remain compatible. Very
deep patterns now fail with an explicit exception instead of exhausting the
JavaScript call stack. This does not establish unlimited expansion safety.

The patch runs during `npm ci` through a failing-on-error postinstall hook.
Docker copies the patch before installation. Installations using
`--ignore-scripts` must run `npm run postinstall` before using the toolchain.
Run `npm run test:dependency-security` to verify the attack cases and ordinary
consumer behavior. The release audit runs these tests before it applies the
exception below.

The original package name and version remain unchanged. Raw `npm audit` still
reports the advisory. The project owner approved a temporary release exception
on 2026-10-14. It expires at **2026-11-13 00:00 UTC**. This exception covers only
`GHSA-vfj7-8cjw-p6xm` in the patched development copy of `braces` 3.0.3 and its
indirect dependency paths. It does not certify the package as free of defects.

Run `npm run audit:release` from `dashboard/` after `npm ci`. This command:

1. Checks the expiry date and the reviewed dependency lock and patch hashes.
2. Checks every installed braces JavaScript file and its package metadata.
3. Runs the attack and compatibility tests.
4. Runs a production audit. No high or critical finding is allowed.
5. Runs the full audit. Each excepted finding must trace only to the specified
   advisory. Every affected package must be marked as development-only.

All other high or critical findings block release. Audit errors, missing patch
files, changed dependencies, extra braces copies and expired approval also block
release. The gate prints the findings and the exception expiry. CI and the
manual image build use this same gate. Expiry blocks future releases and builds;
it does not stop the running app.

The review record is `dashboard/security/braces-exception.json`. Tests in
`dashboard/tests/audit-release.mjs` check that unsafe and incomplete inputs fail.
The patch limits stack exhaustion from nested patterns. It does not establish
unlimited expansion safety. Development tools must use trusted build inputs.
Remove the exception and backport when an official compatible fix is available.
Before expiry, update the dependency or complete a new explicit risk review.

## postcss-selector-parser

An override selects official version 7.1.6 throughout the development tree.
This removes the advisory for the old parser used by Tailwind/PostCSS. Dashboard
tests, lint, type checking and the production build verify compatibility.

## Validation on 2026-10-14

- Clean `npm ci` applies the patch successfully.
- Published braces 3.0.3 suite at `74b2db2938fad48a2ea54a9c8bf27a37a62c350d`:
  764 tests pass with the patched library files.
- Local attack and compatibility regressions: 12 tests pass.
- Dashboard: 204 tests pass; lint with zero warnings, TypeScript and the
  production build pass.
- Production-only npm audit: zero findings. Raw full audit reports nine affected
  development packages from the one braces advisory. The release gate accepts
  only those paths under the temporary exception. All nine audit-policy tests
  pass. The parser advisory is resolved by official version 7.1.6.
