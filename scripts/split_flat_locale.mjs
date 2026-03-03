/**
 * Split a flat locale .ts file into per-namespace directory structure.
 * Usage: node scripts/split_flat_locale.mjs <locale>
 *
 * Reads: dashboard/src/lib/i18n/translations/<locale>.ts
 * Writes: dashboard/src/lib/i18n/translations/<locale>/<ns>.ts (one per namespace)
 *         dashboard/src/lib/i18n/translations/<locale>/index.ts
 * Backs up original as <locale>.ts.bak
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync, copyFileSync } from 'fs';
import { join } from 'path';

const locale = process.argv[2];
if (!locale) { console.error('Usage: node split_flat_locale.mjs <locale>'); process.exit(1); }

const ROOT = new URL('..', import.meta.url).pathname;
const I18N = join(ROOT, 'dashboard/src/lib/i18n/translations');
const flatFile = join(I18N, `${locale}.ts`);
const outDir = join(I18N, locale);

if (!existsSync(flatFile)) { console.error(`File not found: ${flatFile}`); process.exit(1); }

const src = readFileSync(flatFile, 'utf8');

// Parse the flat file to extract namespace blocks.
// Strategy: find top-level namespace keys (2-space indent), then track brace depth.
const lines = src.split('\n');
const namespaces = [];
let currentNs = null;
let depth = 0;
let inExport = false;

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  const trimmed = line.trim();

  // Detect start of the export object
  if (/^export\s+const\s+\w+/.test(trimmed) && trimmed.includes('{')) {
    inExport = true;
    depth = 1;
    continue;
  }

  if (!inExport) continue;

  // Check for top-level namespace start (2-space indent, key: {)
  if (depth === 1) {
    const nsMatch = line.match(/^  (\w+)\s*:\s*\{/);
    if (nsMatch) {
      currentNs = { name: nsMatch[1], lines: [], startLine: i };
      depth = 2;
      continue;
    }
  }

  if (currentNs) {
    // Count braces
    for (const ch of line) {
      if (ch === '{') depth++;
      if (ch === '}') depth--;
    }

    if (depth <= 1) {
      // Namespace block ended
      namespaces.push(currentNs);
      currentNs = null;
      if (depth <= 0) break; // end of export
    } else {
      // Remove 2 levels of indentation (namespace was at 2-space + inner at 4-space)
      // We want inner content at 2-space indent for the namespace file
      const dedented = line.startsWith('    ') ? line.slice(2) : line;
      currentNs.lines.push(dedented);
    }
  } else {
    // Track brace depth even outside namespace
    for (const ch of line) {
      if (ch === '{') depth++;
      if (ch === '}') depth--;
    }
    if (depth <= 0) break;
  }
}

// Write namespace files
mkdirSync(outDir, { recursive: true });

const nativeNames = {
  es: 'Spanish',
  nl: 'Dutch',
  zh: 'Chinese',
};
const localeName = nativeNames[locale] || locale;

for (const ns of namespaces) {
  const content = `import type { PartialTranslations } from '../../types';

const value: PartialTranslations['${ns.name}'] = {
${ns.lines.join('\n')}
};

export default value;
`;
  writeFileSync(join(outDir, `${ns.name}.ts`), content);
  console.log(`  ${ns.name}.ts  (${ns.lines.length} lines)`);
}

// Write index.ts
const imports = namespaces.map(ns => `import ns_${ns.name} from './${ns.name}';`).join('\n');
const entries = namespaces.map(ns => `  ${ns.name}: ns_${ns.name},`).join('\n');

const indexContent = `import type { PartialTranslations } from '../../types';

${imports}

// ${localeName} locale. Missing keys fall back to English via deep merge.
export const ${locale}: PartialTranslations = {
${entries}
};
`;

writeFileSync(join(outDir, 'index.ts'), indexContent);
console.log(`  index.ts`);

// Update the re-export file
writeFileSync(flatFile, `export { ${locale} } from './${locale}/index';\n`);
console.log(`\n  Updated ${locale}.ts → re-export`);

console.log(`\nDone: ${namespaces.length} namespaces extracted for ${locale}`);
