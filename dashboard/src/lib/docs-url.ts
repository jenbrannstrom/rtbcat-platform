const DEFAULT_DOCS_BASE_URL = "https://docs.rtb.cat";

function normalizeBase(url: string): string {
  return (url || DEFAULT_DOCS_BASE_URL).replace(/\/+$/, "");
}

function normalizePath(path: string): string {
  return (path || "").replace(/^\/+/, "");
}

export function getDocsBaseUrl(): string {
  return normalizeBase(process.env.NEXT_PUBLIC_DOCS_SITE_URL || DEFAULT_DOCS_BASE_URL);
}

export function getDocsHomeUrl(): string {
  return getDocsBaseUrl();
}

export function getDocsChapterUrl(chapter: string): string {
  return `${getDocsBaseUrl()}/${normalizePath(chapter)}`;
}
