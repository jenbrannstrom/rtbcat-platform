/**
 * Audit locale translation parity against EN source.
 * Usage: node scripts/audit_locale_parity.mjs [locale]
 * If no locale specified, audits all target locales (es, nl, zh).
 */
import { readFileSync, readdirSync, existsSync } from 'fs';
import { join, basename } from 'path';

const ROOT = new URL('..', import.meta.url).pathname;
const I18N = join(ROOT, 'dashboard/src/lib/i18n/translations');

// ── helpers ──────────────────────────────────────────────────────────────────

/**
 * Extract all dot-separated key paths from a TS object literal.
 * Handles multi-line values like:
 *   keyName:
 *     'some long value',
 */
function extractKeys(src) {
  // Strip block comments
  src = src.replace(/\/\*[\s\S]*?\*\//g, '');

  const keys = [];
  const stack = [];
  const lines = src.split('\n');

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    // Strip inline comments (but not inside strings)
    const trimmed = line.replace(/\/\/.*$/, '').trim();
    if (!trimmed) continue;

    // Closing brace - pop stack
    if (/^},?\s*$/.test(trimmed) || trimmed === '}') {
      stack.pop();
      continue;
    }

    // Key with string value on same line: key: 'value' or key: "value" or key: `value`
    const strMatch = trimmed.match(/^(\w+)\s*:\s*['"`]/);
    if (strMatch) {
      keys.push([...stack, strMatch[1]].join('.'));
      continue;
    }

    // Key with nested object
    const objMatch = trimmed.match(/^(\w+)\s*:\s*\{/);
    if (objMatch) {
      if (trimmed.includes('}')) {
        // Single-line nested
        const inner = trimmed.match(/\{([^}]*)\}/);
        if (inner) {
          const innerKeys = inner[1].match(/(\w+)\s*:/g);
          if (innerKeys) {
            for (const ik of innerKeys) {
              keys.push([...stack, objMatch[1], ik.replace(':', '').trim()].join('.'));
            }
          }
        }
      } else {
        stack.push(objMatch[1]);
      }
      continue;
    }

    // Key with value on NEXT line (multi-line):
    //   keyName:
    //     'value on next line',
    const keyOnlyMatch = trimmed.match(/^(\w+)\s*:\s*$/);
    if (keyOnlyMatch) {
      // Look ahead to see if next non-empty line starts with a quote
      for (let j = i + 1; j < lines.length && j <= i + 3; j++) {
        const nextTrimmed = lines[j].replace(/\/\/.*$/, '').trim();
        if (!nextTrimmed) continue;
        if (/^['"`]/.test(nextTrimmed)) {
          keys.push([...stack, keyOnlyMatch[1]].join('.'));
        }
        break;
      }
      continue;
    }
  }

  return keys;
}

/** Extract {placeholder} tokens from string values */
function extractPlaceholders(src) {
  src = src.replace(/\/\*[\s\S]*?\*\//g, '');

  const result = {};
  const stack = [];
  const lines = src.split('\n');

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.replace(/\/\/.*$/, '').trim();
    if (!trimmed) continue;

    if (/^},?\s*$/.test(trimmed) || trimmed === '}') {
      stack.pop();
      continue;
    }

    // Same-line value
    const strMatch = trimmed.match(/^(\w+)\s*:\s*['"`](.*?)['"`]/);
    if (strMatch) {
      const key = [...stack, strMatch[1]].join('.');
      const placeholders = strMatch[2].match(/\{(\w+)\}/g);
      if (placeholders) result[key] = placeholders.sort();
      continue;
    }

    const objMatch = trimmed.match(/^(\w+)\s*:\s*\{/);
    if (objMatch && !trimmed.includes('}')) {
      stack.push(objMatch[1]);
      continue;
    }

    // Multi-line: key on one line, value on next
    const keyOnlyMatch = trimmed.match(/^(\w+)\s*:\s*$/);
    if (keyOnlyMatch) {
      for (let j = i + 1; j < lines.length && j <= i + 3; j++) {
        const nextTrimmed = lines[j].replace(/\/\/.*$/, '').trim();
        if (!nextTrimmed) continue;
        const valMatch = nextTrimmed.match(/^['"`](.*?)['"`]/);
        if (valMatch) {
          const key = [...stack, keyOnlyMatch[1]].join('.');
          const placeholders = valMatch[1].match(/\{(\w+)\}/g);
          if (placeholders) result[key] = placeholders.sort();
        }
        break;
      }
      continue;
    }
  }

  return result;
}

// ── load EN keys per namespace ───────────────────────────────────────────────

function loadNamespaceKeys(dir) {
  const result = {};
  for (const file of readdirSync(dir)) {
    if (file === 'index.ts') continue;
    const ns = basename(file, '.ts');
    const src = readFileSync(join(dir, file), 'utf8');
    result[ns] = extractKeys(src);
  }
  return result;
}

function loadNamespacePlaceholders(dir) {
  const result = {};
  for (const file of readdirSync(dir)) {
    if (file === 'index.ts') continue;
    const ns = basename(file, '.ts');
    const src = readFileSync(join(dir, file), 'utf8');
    const ph = extractPlaceholders(src);
    for (const [k, v] of Object.entries(ph)) {
      result[`${ns}.${k}`] = v;
    }
  }
  return result;
}

// ── audit ────────────────────────────────────────────────────────────────────

function auditLocale(locale, enKeys, enPlaceholders) {
  console.log(`\n${'═'.repeat(60)}`);
  console.log(`  LOCALE: ${locale.toUpperCase()}`);
  console.log('═'.repeat(60));

  const dirPath = join(I18N, locale);
  if (!existsSync(dirPath) || !existsSync(join(dirPath, 'index.ts'))) {
    console.log(`  ERROR: No directory structure found for ${locale}`);
    return null;
  }

  const localeKeys = loadNamespaceKeys(dirPath);
  const localePlaceholders = loadNamespacePlaceholders(dirPath);

  let totalMissing = 0;
  let totalExtra = 0;
  let totalPresent = 0;
  let phMismatches = 0;

  const enNs = Object.keys(enKeys).sort();
  const localeNs = new Set(Object.keys(localeKeys));
  const missingNs = enNs.filter(ns => !localeNs.has(ns));

  if (missingNs.length > 0) {
    console.log(`\n  MISSING NAMESPACES (${missingNs.length}):`);
    for (const ns of missingNs) {
      console.log(`    - ${ns} (${enKeys[ns].length} keys)`);
      totalMissing += enKeys[ns].length;
    }
  }

  for (const ns of enNs) {
    if (!localeNs.has(ns)) continue;

    const enKeySet = new Set(enKeys[ns]);
    const locKeySet = new Set(localeKeys[ns]);

    const missing = [...enKeySet].filter(k => !locKeySet.has(k));
    const extra = [...locKeySet].filter(k => !enKeySet.has(k));

    totalPresent += localeKeys[ns].length - extra.length;

    if (missing.length > 0) {
      console.log(`\n  ${ns}: ${missing.length} missing key(s)`);
      for (const k of missing) {
        console.log(`    - ${k}`);
      }
      totalMissing += missing.length;
    }

    if (extra.length > 0) {
      console.log(`\n  ${ns}: ${extra.length} extra key(s)`);
      for (const k of extra) {
        console.log(`    ⚠ ${k}`);
      }
      totalExtra += extra.length;
    }
  }

  // Placeholder checks
  for (const [key, enPh] of Object.entries(enPlaceholders)) {
    const locPh = localePlaceholders[key];
    if (!locPh) {
      // Check if key exists in locale
      const [ns, ...rest] = key.split('.');
      const leafKey = rest.join('.');
      if (localeKeys[ns] && localeKeys[ns].includes(leafKey)) {
        console.log(`\n  MISSING PLACEHOLDERS: ${key}`);
        console.log(`    EN has: ${enPh.join(', ')}`);
        console.log(`    ${locale.toUpperCase()}: (none)`);
        phMismatches++;
      }
      continue;
    }
    if (JSON.stringify(enPh) !== JSON.stringify(locPh)) {
      console.log(`\n  PLACEHOLDER MISMATCH: ${key}`);
      console.log(`    EN: ${enPh.join(', ')}`);
      console.log(`    ${locale.toUpperCase()}: ${locPh.join(', ')}`);
      phMismatches++;
    }
  }

  const totalEnKeys = Object.values(enKeys).reduce((s, a) => s + a.length, 0);

  console.log(`\n  ── Summary ──`);
  console.log(`  EN total keys:      ${totalEnKeys}`);
  console.log(`  Present:            ${totalPresent}`);
  console.log(`  Missing:            ${totalMissing}`);
  console.log(`  Extra:              ${totalExtra}`);
  console.log(`  Placeholder issues: ${phMismatches}`);
  console.log(`  Coverage:           ${((totalPresent / totalEnKeys) * 100).toFixed(1)}%`);

  return { totalMissing, totalExtra, phMismatches, totalPresent, totalEnKeys };
}

// ── main ─────────────────────────────────────────────────────────────────────

const targetLocales = process.argv[2] ? [process.argv[2]] : ['es', 'nl', 'zh'];

const enDir = join(I18N, 'en');
const enKeys = loadNamespaceKeys(enDir);
const enPlaceholders = loadNamespacePlaceholders(enDir);

const totalEnKeys = Object.values(enKeys).reduce((s, a) => s + a.length, 0);
console.log(`EN source: ${Object.keys(enKeys).length} namespaces, ${totalEnKeys} total keys`);

for (const locale of targetLocales) {
  auditLocale(locale, enKeys, enPlaceholders);
}
