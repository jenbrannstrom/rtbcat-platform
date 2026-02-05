export type ReportType =
  | "quality"
  | "bidsinauction"
  | "pipeline-geo"
  | "pipeline-publisher"
  | "bid-filtering"
  | "unknown";

const normalizeColumnName = (name: string) =>
  name.replace(/^#/, "").trim().toLowerCase();

const REQUIRED_COLUMNS: Record<ReportType, string[]> = {
  quality: [
    "Buyer account ID",
    "Billing ID",
    "Creative ID",
    "Creative size",
    "Day",
    "Country",
    "Reached queries",
    "Impressions",
  ],
  bidsinauction: [
    "Buyer account ID",
    "Country",
    "Creative ID",
    "Day",
    "Hour",
    "Bids in auction",
    "Auctions won",
    "Bids",
  ],
  "pipeline-geo": [
    "Buyer account ID",
    "Country",
    "Day",
    "Hour",
    "Bid requests",
  ],
  "pipeline-publisher": [
    "Buyer account ID",
    "Country",
    "Publisher ID",
    "Day",
    "Hour",
    "Bid requests",
  ],
  "bid-filtering": [
    "Buyer account ID",
    "Country",
    "Creative ID",
    "Bid filtering reason",
    "Day",
    "Hour",
    "Bids",
  ],
  unknown: [],
};

export const detectReportType = (
  headers: string[],
  filename?: string | null
): ReportType => {
  const normalized = new Set(headers.map(normalizeColumnName));
  const name = (filename || "").toLowerCase();

  if (normalized.has("bid filtering reason") || name.includes("bid-filtering")) {
    return "bid-filtering";
  }

  if (normalized.has("bid requests") || name.includes("pipeline")) {
    if (normalized.has("publisher id") || name.includes("rtb-pipeline")) {
      return "pipeline-publisher";
    }
    return "pipeline-geo";
  }

  if (normalized.has("billing id") && normalized.has("creative id")) {
    return "quality";
  }

  if (normalized.has("bids in auction") && normalized.has("creative id")) {
    return "bidsinauction";
  }

  return "unknown";
};

const hasSeatIdInFilename = (filename?: string | null): boolean => {
  if (!filename) return false;
  const lower = filename.toLowerCase();
  if (!lower.includes("catscan-")) return false;
  return /-\d{6,}-/.test(lower);
};

export const getRequiredColumns = (reportType: ReportType): string[] =>
  REQUIRED_COLUMNS[reportType] || [];

export const getMissingRequiredColumns = (
  headers: string[],
  reportType: ReportType,
  filename?: string | null
): string[] => {
  const required = getRequiredColumns(reportType);
  if (required.length === 0) return [];

  const normalized = new Set(headers.map(normalizeColumnName));
  return required.filter((column) => {
    if (normalizeColumnName(column) === "buyer account id" && hasSeatIdInFilename(filename)) {
      return false;
    }
    return !normalized.has(normalizeColumnName(column));
  });
};
