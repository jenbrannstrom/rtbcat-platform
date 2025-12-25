import Papa from "papaparse";
import type { PerformanceRow } from "@/lib/types/import";

// Normalize column name: remove #, spaces, parens, lowercase
function normalizeColumnName(name: string): string {
  return name
    .replace(/^#/, "") // Remove # prefix
    .replace(/\s+/g, "_") // Spaces to underscores
    .replace(/[()]/g, "") // Remove parentheses
    .toLowerCase()
    .trim();
}

// Find column value by matching possible names
function findColumn(row: Record<string, string>, possibleNames: string[]): string | undefined {
  for (const name of possibleNames) {
    if (row[name] !== undefined) {
      return row[name];
    }
  }
  return undefined;
}

// Parse date from various formats (MM/DD/YY, YYYY-MM-DD, etc.)
function parseDate(dateStr: string): string {
  if (!dateStr) return "";

  // Already in YYYY-MM-DD format
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    return dateStr;
  }

  // MM/DD/YY or MM/DD/YYYY format
  if (dateStr.includes("/")) {
    const parts = dateStr.split("/");
    if (parts.length === 3) {
      const [month, day, year] = parts;
      const fullYear = year.length === 2 ? `20${year}` : year;
      return `${fullYear}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
    }
  }

  // Try to parse as Date object
  const parsed = new Date(dateStr);
  if (!isNaN(parsed.getTime())) {
    return parsed.toISOString().split("T")[0];
  }

  return dateStr;
}

// Parse spend value (remove $, commas, etc.)
function parseSpend(value: string | number | undefined): number {
  if (value === undefined || value === null || value === "") return 0;
  const str = String(value).replace(/[$,]/g, "").trim();
  const num = parseFloat(str);
  return isNaN(num) ? 0 : num;
}

// Parse integer value
function parseIntValue(value: string | number | undefined): number {
  if (value === undefined || value === null || value === "") return 0;
  const str = String(value).replace(/,/g, "").trim();
  const num = parseInt(str, 10);
  return isNaN(num) ? 0 : num;
}

// Aggregate hourly data to daily
export function aggregateByDay(data: PerformanceRow[]): PerformanceRow[] {
  const aggregated = new Map<string, PerformanceRow>();

  data.forEach((row) => {
    // Skip rows with invalid creative_id
    if (!row.creative_id || isNaN(row.creative_id)) return;

    // Create key: creative_id + date + geography
    const key = `${row.creative_id}|${row.date}|${row.geography || "NONE"}`;

    if (aggregated.has(key)) {
      // Add to existing
      const existing = aggregated.get(key)!;
      existing.impressions += row.impressions;
      existing.clicks += row.clicks;
      existing.spend += row.spend;
    } else {
      // Create new
      aggregated.set(key, { ...row });
    }
  });

  return Array.from(aggregated.values());
}

export interface ParseResult {
  data: PerformanceRow[];
  detectedColumns: {
    creative_id?: string;
    date?: string;
    impressions?: string;
    clicks?: string;
    spend?: string;
    geography?: string;
  };
  hasHourlyData: boolean;
  originalRowCount: number;
}

export function parseCSV(file: File): Promise<ParseResult> {
  return new Promise((resolve, reject) => {
    Papa.parse<Record<string, string>>(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        try {
          if (results.data.length === 0) {
            resolve({
              data: [],
              detectedColumns: {},
              hasHourlyData: false,
              originalRowCount: 0,
            });
            return;
          }

          // Get original headers and create normalized mapping
          const originalHeaders = results.meta.fields || [];
          const normalizedHeaders: Record<string, string> = {};

          originalHeaders.forEach((header) => {
            normalizedHeaders[normalizeColumnName(header)] = header;
          });

          // Detect columns
          const detectedColumns: ParseResult["detectedColumns"] = {};

          // Creative ID variations
          const creativeIdCols = ["creative_id", "creativeid", "creative"];
          for (const col of creativeIdCols) {
            if (normalizedHeaders[col]) {
              detectedColumns.creative_id = normalizedHeaders[col];
              break;
            }
          }

          // Date variations
          const dateCols = ["date", "day"];
          for (const col of dateCols) {
            if (normalizedHeaders[col]) {
              detectedColumns.date = normalizedHeaders[col];
              break;
            }
          }

          // Impressions
          if (normalizedHeaders["impressions"]) {
            detectedColumns.impressions = normalizedHeaders["impressions"];
          }

          // Clicks
          if (normalizedHeaders["clicks"]) {
            detectedColumns.clicks = normalizedHeaders["clicks"];
          }

          // Spend variations
          const spendCols = ["spend", "spend_buyer_currency"];
          for (const col of spendCols) {
            if (normalizedHeaders[col]) {
              detectedColumns.spend = normalizedHeaders[col];
              break;
            }
          }

          // Geography variations
          const geoCols = ["geography", "country"];
          for (const col of geoCols) {
            if (normalizedHeaders[col]) {
              detectedColumns.geography = normalizedHeaders[col];
              break;
            }
          }

          // Check for hourly data
          const hasHourlyData = normalizedHeaders["hour"] !== undefined;

          // Parse data
          const data: PerformanceRow[] = results.data.map((row) => {
            // Normalize all keys in the row
            const normalizedRow: Record<string, string> = {};
            Object.keys(row).forEach((key) => {
              normalizedRow[normalizeColumnName(key)] = row[key];
            });

            // Map to PerformanceRow
            const creativeIdValue = findColumn(normalizedRow, creativeIdCols);
            const dateValue = findColumn(normalizedRow, dateCols);
            const spendValue = findColumn(normalizedRow, spendCols);
            const geoValue = findColumn(normalizedRow, geoCols);

            return {
              creative_id: parseIntValue(creativeIdValue),
              date: parseDate(dateValue || ""),
              impressions: parseIntValue(normalizedRow["impressions"]),
              clicks: parseIntValue(normalizedRow["clicks"]),
              spend: parseSpend(spendValue),
              geography: geoValue?.toUpperCase() || undefined,
            };
          });

          // Filter out invalid rows (no creative_id or no date)
          const validData = data.filter(
            (row) => row.creative_id > 0 && row.date
          );

          // Aggregate if hourly data detected
          const finalData = hasHourlyData ? aggregateByDay(validData) : validData;

          resolve({
            data: finalData,
            detectedColumns,
            hasHourlyData,
            originalRowCount: results.data.length,
          });
        } catch (error) {
          reject(error);
        }
      },
      error: (error) => {
        reject(error);
      },
    });
  });
}
