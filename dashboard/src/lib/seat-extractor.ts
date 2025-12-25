/**
 * Seat Extractor for CSV Import
 *
 * Extracts seat/billing account information from CSV data rows.
 * This info is used to associate all imported data with a seat.
 */

export interface SeatInfo {
  billingId: string;
  accountName: string;
  accountId: string;
}

/**
 * Normalize column name for matching
 */
function normalizeColumnName(name: string): string {
  return name
    .replace(/^#/, "")
    .replace(/\s+/g, "_")
    .replace(/[()]/g, "")
    .toLowerCase()
    .trim();
}

/**
 * Create a normalized lookup map from row keys
 */
function normalizeRow(
  row: Record<string, string>
): Record<string, string> {
  const normalized: Record<string, string> = {};
  for (const [key, value] of Object.entries(row)) {
    normalized[normalizeColumnName(key)] = value;
  }
  return normalized;
}

/**
 * Column name variations for seat fields
 */
const SEAT_COLUMN_VARIATIONS: Record<keyof SeatInfo, string[]> = {
  billingId: [
    "billing_id",
    "billingid",
    "billing",
    "buyer_account_id",
    "buyeraccountid",
  ],
  accountName: [
    "buyer_account_name",
    "buyeraccountname",
    "account_name",
    "accountname",
    "buyer_name",
  ],
  accountId: [
    "buyer_account_id",
    "buyeraccountid",
    "account_id",
    "accountid",
    "buyer_id",
  ],
};

/**
 * Extract seat information from a CSV row.
 *
 * Uses the first row to identify the seat/billing account.
 * These columns are typically constant across the entire CSV file.
 *
 * @param row - First data row from CSV
 * @returns SeatInfo with billing/account details
 */
export function extractSeatInfo(row: Record<string, string>): SeatInfo {
  const normalized = normalizeRow(row);

  const findValue = (variations: string[]): string => {
    for (const variation of variations) {
      if (normalized[variation]) {
        return normalized[variation];
      }
    }
    return "";
  };

  return {
    billingId: findValue(SEAT_COLUMN_VARIATIONS.billingId),
    accountName: findValue(SEAT_COLUMN_VARIATIONS.accountName),
    accountId: findValue(SEAT_COLUMN_VARIATIONS.accountId),
  };
}

/**
 * Check if seat info is valid (has at least billing ID)
 */
export function isValidSeatInfo(info: SeatInfo): boolean {
  return Boolean(info.billingId);
}

/**
 * Format seat info for display
 */
export function formatSeatInfo(info: SeatInfo): string {
  if (info.accountName) {
    return `${info.accountName} (${info.billingId})`;
  }
  return info.billingId || "Unknown Seat";
}

/**
 * Extract seat info from CSV preview data
 */
export function extractSeatFromPreview(
  rows: Record<string, string>[]
): SeatInfo | null {
  if (!rows || rows.length === 0) {
    return null;
  }

  // Use first row to extract seat info
  const info = extractSeatInfo(rows[0]);

  if (!isValidSeatInfo(info)) {
    return null;
  }

  return info;
}
