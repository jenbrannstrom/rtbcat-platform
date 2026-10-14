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
consumer behavior. The release checks run these tests independently of audit.

The original package name and version remain unchanged. Consequently, `npm
audit` still reports the advisory. No advisory is suppressed and the existing
high/critical release gate remains in force. A stable release still needs an
official fixed dependency or an explicitly reviewed change to that policy.
Replace this backport when an official compatible release is available.

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
- Production-only npm audit: zero findings. Full audit remains blocked by the
  one braces advisory and its dependent-package paths. The parser advisory is
  resolved by official version 7.1.6.
