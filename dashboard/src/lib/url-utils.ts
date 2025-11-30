/**
 * URL Intelligence Utilities
 * Smart parsing and categorization of ad destination URLs
 */

export interface ParsedUrl {
  url: string;
  type: UrlType;
  label: string;
  domain: string;
  isPrimary: boolean;
  packageId?: string; // For app store URLs
  tooltip?: string;
}

export type UrlType =
  | "play_store"
  | "app_store"
  | "appsflyer"
  | "adjust"
  | "branch"
  | "kochava"
  | "attribution"
  | "doubleclick"
  | "tracking_pixel"
  | "landing_page"
  | "unknown";

const URL_PATTERNS: Array<{
  pattern: RegExp;
  type: UrlType;
  label: string;
  tooltip: string;
}> = [
  {
    pattern: /play\.google\.com\/store\/apps/i,
    type: "play_store",
    label: "Google Play Store",
    tooltip: "Final destination where user installs the app.",
  },
  {
    pattern: /apps\.apple\.com/i,
    type: "app_store",
    label: "Apple App Store",
    tooltip: "Final destination where user installs the app.",
  },
  {
    pattern: /app\.appsflyer\.com/i,
    type: "appsflyer",
    label: "AppsFlyer Link",
    tooltip: "Mobile attribution platform. Tracks which ad drove the install and provides deep linking.",
  },
  {
    pattern: /app\.adjust\.com/i,
    type: "adjust",
    label: "Adjust Link",
    tooltip: "Mobile attribution platform. Tracks which ad drove the install and provides deep linking.",
  },
  {
    pattern: /app\.branch\.io/i,
    type: "branch",
    label: "Branch Link",
    tooltip: "Mobile attribution platform. Tracks which ad drove the install and provides deep linking.",
  },
  {
    pattern: /app\.kochava\.com|control\.kochava\.com/i,
    type: "kochava",
    label: "Kochava Link",
    tooltip: "Mobile attribution platform. Tracks which ad drove the install and provides deep linking.",
  },
  {
    pattern: /googleads\.g\.doubleclick\.net|pagead\/aclk/i,
    type: "doubleclick",
    label: "DoubleClick Tracker",
    tooltip: "Google's ad click tracker for billing and reporting purposes.",
  },
  {
    pattern: /1x1\.gif|pixel|\.gif\?|track\..*\/pixel|impression|beacon/i,
    type: "tracking_pixel",
    label: "Tracking Pixel",
    tooltip: "Impression or click tracking pixel for analytics.",
  },
];

// Common ad server macros to clean from URLs
const MACRO_PATTERNS = [
  /%%[A-Z_]+%%/g, // %%CLICK_URL_UNESC%%
  /\{[a-z_]+\}/gi, // {adxcode}, {bundle}
  /\$\{[^}]+\}/g, // ${MACRO}
  /\[\[.*?\]\]/g, // [[MACRO]]
  /__DFA_.*?__/g, // __DFA_CLICK__
];

/**
 * Remove ad server macros from URL
 */
export function cleanUrlMacros(url: string): string {
  let cleaned = url;
  for (const pattern of MACRO_PATTERNS) {
    cleaned = cleaned.replace(pattern, "");
  }
  // Remove any double slashes that aren't part of http://
  cleaned = cleaned.replace(/([^:])\/\//g, "$1/");
  return cleaned;
}

/**
 * URL decode a string, handling nested encoding
 */
export function fullyDecodeUrl(url: string): string {
  let decoded = url;
  let prev = "";
  // Keep decoding until no more changes (handles double/triple encoding)
  let iterations = 0;
  while (decoded !== prev && iterations < 5) {
    prev = decoded;
    try {
      decoded = decodeURIComponent(decoded);
    } catch {
      // If decoding fails, return what we have
      break;
    }
    iterations++;
  }
  return decoded;
}

/**
 * Extract all URLs from a potentially chained/encoded URL string
 */
export function extractUrlsFromChain(rawUrl: string): string[] {
  if (!rawUrl) return [];

  // First, fully decode the URL
  let decoded = fullyDecodeUrl(rawUrl);

  // Clean macros
  decoded = cleanUrlMacros(decoded);

  // Find all URLs in the string (with protocol)
  const urlRegex = /https?:\/\/[^\s"'<>]+/gi;
  const matches = decoded.match(urlRegex) || [];

  // Clean up each URL
  let urls = matches.map((url) => {
    // Remove trailing garbage characters
    return url.replace(/[,;)}\]]+$/, "").replace(/&amp;/g, "&");
  });

  // If no URLs found with protocol, check if the entire string is a domain
  if (urls.length === 0 && decoded.trim()) {
    // Check if it looks like a domain (contains a dot, no spaces, not just numbers)
    const trimmed = decoded.trim();
    if (trimmed.includes(".") && !trimmed.includes(" ") && !/^\d+$/.test(trimmed)) {
      // Add https:// prefix
      urls = [`https://${trimmed}`];
    }
  }

  // Deduplicate while preserving order
  const seen = new Set<string>();
  return urls.filter((url) => {
    const normalized = url.toLowerCase();
    if (seen.has(normalized)) return false;
    seen.add(normalized);
    return true;
  });
}

/**
 * Extract domain from URL
 */
export function extractDomain(url: string): string {
  try {
    const urlObj = new URL(url);
    return urlObj.hostname;
  } catch {
    // Try to extract domain with regex
    const match = url.match(/https?:\/\/([^/?#]+)/i);
    return match ? match[1] : url;
  }
}

/**
 * Extract app package ID from Play Store URL
 */
export function extractAppPackageId(url: string): string | undefined {
  const match = url.match(/[?&]id=([^&]+)/i);
  return match ? match[1] : undefined;
}

/**
 * Extract app ID from App Store URL
 */
export function extractAppStoreId(url: string): string | undefined {
  const match = url.match(/\/id(\d+)/i);
  return match ? match[1] : undefined;
}

/**
 * Extract app package ID from AppsFlyer URL path (e.g., app.appsflyer.com/com.drop.frenzy.bubbly)
 */
export function extractAppsFlyerPackageId(url: string): string | undefined {
  try {
    const urlObj = new URL(url);
    // Path is like /com.drop.frenzy.bubbly
    const pathMatch = urlObj.pathname.match(/^\/([a-z][a-z0-9_.]+)/i);
    if (pathMatch && pathMatch[1].includes(".")) {
      return pathMatch[1];
    }
  } catch {
    // Fallback regex
    const match = url.match(/app\.appsflyer\.com\/([a-z][a-z0-9_.]+)/i);
    return match ? match[1] : undefined;
  }
  return undefined;
}

/**
 * Generate Play Store URL from package ID
 */
export function getPlayStoreUrl(packageId: string): string {
  return `https://play.google.com/store/apps/details?id=${packageId}`;
}

/**
 * Categorize a single URL
 */
export function categorizeUrl(url: string): Omit<ParsedUrl, "isPrimary"> {
  const domain = extractDomain(url);

  for (const { pattern, type, label, tooltip } of URL_PATTERNS) {
    if (pattern.test(url)) {
      const result: Omit<ParsedUrl, "isPrimary"> = {
        url,
        type,
        label,
        domain,
        tooltip,
      };

      // Extract package ID for app stores
      if (type === "play_store") {
        result.packageId = extractAppPackageId(url);
      } else if (type === "app_store") {
        result.packageId = extractAppStoreId(url);
      } else if (type === "appsflyer") {
        // Extract package ID from AppsFlyer URL path
        result.packageId = extractAppsFlyerPackageId(url);
      }

      return result;
    }
  }

  // Default to landing page for any HTTP URL
  return {
    url,
    type: "landing_page",
    label: "Landing Page",
    domain,
    tooltip: "Website where user is directed after clicking the ad.",
  };
}

/**
 * Determine the primary destination from a list of parsed URLs
 */
function findPrimaryDestination(urls: Omit<ParsedUrl, "isPrimary">[]): number {
  // Priority: App Store > Play Store > Landing Page > First URL
  const priorities: UrlType[] = ["play_store", "app_store", "landing_page"];

  for (const type of priorities) {
    const index = urls.findIndex((u) => u.type === type);
    if (index !== -1) return index;
  }

  return 0; // Default to first URL
}

/**
 * Add numbering to duplicate labels
 */
function numberDuplicateLabels(urls: ParsedUrl[]): ParsedUrl[] {
  const labelCounts: Record<string, number> = {};
  const labelTotals: Record<string, number> = {};

  // First pass: count totals
  for (const url of urls) {
    labelTotals[url.label] = (labelTotals[url.label] || 0) + 1;
  }

  // Second pass: add numbers
  return urls.map((url) => {
    if (labelTotals[url.label] > 1) {
      labelCounts[url.label] = (labelCounts[url.label] || 0) + 1;
      return {
        ...url,
        label: `${url.label} ${labelCounts[url.label]}`,
      };
    }
    return url;
  });
}

/**
 * Main function: Parse and categorize destination URLs
 */
export function parseDestinationUrls(rawUrl: string | null | undefined): ParsedUrl[] {
  if (!rawUrl) return [];

  const extractedUrls = extractUrlsFromChain(rawUrl);
  if (extractedUrls.length === 0) return [];

  // Categorize each URL
  let categorized = extractedUrls.map((url) => categorizeUrl(url));

  // Filter out tracking pixels and simple domain landing pages if we have better URLs
  let displayUrls = categorized.filter((u) => u.type !== "tracking_pixel");

  // Check if we have an AppsFlyer link with a package ID but no Play Store URL
  const hasPlayStore = displayUrls.some((u) => u.type === "play_store");
  if (!hasPlayStore) {
    const appsFlyerWithPackage = displayUrls.find(
      (u) => u.type === "appsflyer" && u.packageId
    );
    if (appsFlyerWithPackage?.packageId) {
      // Generate a Play Store URL and add it as the first item
      const playStoreUrl = getPlayStoreUrl(appsFlyerWithPackage.packageId);
      displayUrls.unshift({
        url: playStoreUrl,
        type: "play_store",
        label: "Google Play Store",
        domain: "play.google.com",
        packageId: appsFlyerWithPackage.packageId,
        tooltip: "Final destination where user installs the app.",
      });
    }
  }

  // Filter out bare domain landing pages if we have attribution/store links
  const hasAttributionOrStore = displayUrls.some(
    (u) => ["play_store", "app_store", "appsflyer", "adjust", "branch", "kochava"].includes(u.type)
  );
  if (hasAttributionOrStore) {
    displayUrls = displayUrls.filter((u) => {
      // Keep everything except bare domain landing pages
      if (u.type === "landing_page") {
        // Check if it's just a domain without path
        try {
          const urlObj = new URL(u.url);
          return urlObj.pathname !== "/" || urlObj.search !== "";
        } catch {
          return false;
        }
      }
      return true;
    });
  }

  if (displayUrls.length === 0) {
    // If only tracking pixels, show them anyway
    displayUrls.push(...categorized);
  }

  // Find primary destination
  const primaryIndex = findPrimaryDestination(displayUrls);

  // Mark primary and convert to ParsedUrl
  let result: ParsedUrl[] = displayUrls.map((url, index) => ({
    ...url,
    isPrimary: index === primaryIndex,
  }));

  // Add numbering to duplicates
  result = numberDuplicateLabels(result);

  return result;
}

/**
 * Generate Google Authorized Buyers URL
 */
export function getGoogleAuthBuyersUrl(buyerId: string, creativeId: string): string {
  return `https://realtimebidding.google.com/${buyerId}#/troubleshooting/creatives?ai=${buyerId}&ci=${creativeId}`;
}

/**
 * Extract buyer ID from creative name (e.g., "buyers/299038253/creatives/79783")
 */
export function extractBuyerIdFromName(name: string | null | undefined): string | null {
  if (!name) return null;
  const match = name.match(/buyers\/(\d+)/);
  return match ? match[1] : null;
}

/**
 * Validate URL is safe to render (basic XSS prevention)
 */
export function isValidUrl(url: string): boolean {
  try {
    const urlObj = new URL(url);
    // Only allow http and https protocols
    return ["http:", "https:"].includes(urlObj.protocol);
  } catch {
    return false;
  }
}

/**
 * Get display text for a URL (domain or package ID)
 */
export function getUrlDisplayText(parsedUrl: ParsedUrl): string {
  if (parsedUrl.packageId) {
    return parsedUrl.packageId;
  }
  return parsedUrl.domain;
}
