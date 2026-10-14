# Dependency security

## Release policy

Run `npm ci` and `npm run audit:release` in `dashboard/` before release.
The release check runs dependency contract tests and standard `npm audit`.
All reported vulnerabilities block release. There is no advisory allowlist,
patched-package exception or expiry date. An audit service error also fails the
check. CI and the manual image build use the same command.

## Removal of braces in 0.10.1

Version 0.10.0 included a local `braces` patch and a temporary exception for
[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).
Version 0.10.1 removes the dependency, patch and exception. It does not rename
`braces` or change its version to hide an audit finding.

Two dependency changes remove the affected code:

1. Tailwind CSS 4.3.3 and its PostCSS plugin replace Tailwind 3. The class names
   and CSS configuration use the new syntax. The existing colour palette,
   border defaults, placeholder colours and button cursors are preserved.
   `tailwind-merge` 3.7.0 handles the new utility names.
2. A scoped npm override replaces only the directory-search dependency of
   `@next/eslint-plugin-next` 16.4.0. The local package at
   `dashboard/vendor/next-eslint-glob` calls official `tinyglobby` 0.2.17. It
   preserves the directory matching and path format used by the Next.js rule.
   It contains no `fast-glob`, `micromatch` or `braces` code. This small adapter
   is maintained by RTBcat, not by Next.js. Other fast-glob APIs are not supported.

All Next.js lint rules remain enabled as configured before this change.
Contract tests verify directory patterns, multiple roots, path normalization,
and detection of an invalid internal HTML link. They also check that the removed
packages do not return to the lock file. Review this adapter when upgrading the
Next.js ESLint plugin; keep the override scoped to the tested version.

The old patch installer is no longer needed and is removed. Install scripts do
not modify third-party source files.

## Browser requirements

Tailwind 4 requires Safari 16.4 or later, Chrome 111 or later, and Firefox 128 or
later. See the [Tailwind upgrade guide](https://tailwindcss.com/docs/upgrade-guide).
Older browsers require a separate compatibility decision.

## Validation

The release requires a clean install, dependency contract tests, the full npm
audit, dashboard tests, lint, TypeScript, a production build, and browser checks
of the migrated styles. Python bundles retain their existing `pip-audit` gates.
