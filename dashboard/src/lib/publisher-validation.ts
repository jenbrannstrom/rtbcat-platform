/**
 * Shared publisher ID validation and type detection utilities.
 * Used by config-breakdown-panel.tsx (Home) and pretargeting-settings-editor.tsx (Full Editor).
 */

/** Validates a publisher ID: must contain a dot, alphanumeric with dots/hyphens/underscores. */
export function isValidPublisherId(value: string): boolean {
  if (!value.includes('.')) return false;
  return /^[a-zA-Z0-9][a-zA-Z0-9._-]*\.[a-zA-Z0-9._-]+$/.test(value);
}

/** Detects whether a publisher ID looks like an app bundle ID or a web domain. */
export function detectPublisherType(value: string): 'App' | 'Web' {
  const parts = value.toLowerCase().split('.');
  const appPrefixes = new Set(['com', 'net', 'org', 'io', 'co', 'app']);
  if (parts.length >= 3 && appPrefixes.has(parts[0])) {
    return 'App';
  }
  return 'Web';
}
