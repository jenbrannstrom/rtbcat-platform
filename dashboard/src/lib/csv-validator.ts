import type { PerformanceRow, ValidationError, ValidationResult } from "@/lib/types/import";
import type { ParseResult } from "@/lib/csv-parser";

export interface ExtendedValidationResult extends ValidationResult {
  detectedColumns?: ParseResult["detectedColumns"];
  hasHourlyData?: boolean;
  aggregatedFromRows?: number;
}

export function validatePerformanceCSV(parseResult: ParseResult): ExtendedValidationResult {
  const errors: ValidationError[] = [];
  const { data, detectedColumns, hasHourlyData, originalRowCount } = parseResult;

  if (data.length === 0) {
    // Check if it's a column detection issue
    const missingCols: string[] = [];
    if (!detectedColumns.creative_id) missingCols.push("creative_id");
    if (!detectedColumns.date) missingCols.push("date");
    if (!detectedColumns.impressions) missingCols.push("impressions");
    if (!detectedColumns.clicks) missingCols.push("clicks");
    if (!detectedColumns.spend) missingCols.push("spend");

    if (missingCols.length > 0) {
      errors.push({
        row: 0,
        field: "columns",
        error: `Could not detect required columns: ${missingCols.join(", ")}. Found columns: ${Object.values(detectedColumns).filter(Boolean).join(", ") || "none"}`,
        value: null,
      });
    } else {
      errors.push({
        row: 0,
        field: "file",
        error: "CSV file is empty or contains no valid data rows",
        value: null,
      });
    }

    return {
      valid: false,
      errors,
      rowCount: 0,
      data: [],
      detectedColumns,
      hasHourlyData,
    };
  }

  // Validate each row
  const validData: PerformanceRow[] = [];

  data.forEach((row, index) => {
    const rowNum = index + 2; // +2 for header and 0-based index
    let rowValid = true;

    // creative_id: positive integer
    if (!Number.isInteger(row.creative_id) || row.creative_id <= 0) {
      errors.push({
        row: rowNum,
        field: "creative_id",
        error: "Must be a positive integer",
        value: row.creative_id,
      });
      rowValid = false;
    }

    // date: valid YYYY-MM-DD (already normalized by parser)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(row.date)) {
      errors.push({
        row: rowNum,
        field: "date",
        error: "Invalid date format (expected YYYY-MM-DD)",
        value: row.date,
      });
      rowValid = false;
    } else {
      // date: not in future
      const date = new Date(row.date);
      const today = new Date();
      today.setHours(23, 59, 59, 999);
      if (date > today) {
        errors.push({
          row: rowNum,
          field: "date",
          error: "Date cannot be in the future",
          value: row.date,
        });
        rowValid = false;
      }
    }

    // impressions: non-negative integer
    if (!Number.isInteger(row.impressions) || row.impressions < 0) {
      errors.push({
        row: rowNum,
        field: "impressions",
        error: "Must be a non-negative integer",
        value: row.impressions,
      });
      rowValid = false;
    }

    // clicks: non-negative integer
    if (!Number.isInteger(row.clicks) || row.clicks < 0) {
      errors.push({
        row: rowNum,
        field: "clicks",
        error: "Must be a non-negative integer",
        value: row.clicks,
      });
      rowValid = false;
    }

    // clicks <= impressions
    if (row.clicks > row.impressions) {
      errors.push({
        row: rowNum,
        field: "clicks",
        error: "Clicks cannot exceed impressions",
        value: `${row.clicks} clicks > ${row.impressions} impressions`,
      });
      rowValid = false;
    }

    // spend: non-negative decimal
    if (isNaN(row.spend) || row.spend < 0) {
      errors.push({
        row: rowNum,
        field: "spend",
        error: "Must be a non-negative number",
        value: row.spend,
      });
      rowValid = false;
    }

    // geography: allow full country names or 2-letter codes (if present)
    // Relaxed validation - just check it exists if provided
    if (row.geography && row.geography.length === 0) {
      errors.push({
        row: rowNum,
        field: "geography",
        error: "Geography cannot be empty string",
        value: row.geography,
      });
      rowValid = false;
    }

    if (rowValid) {
      validData.push(row);
    }
  });

  return {
    valid: errors.length === 0,
    errors,
    rowCount: data.length,
    data: errors.length === 0 ? validData : [],
    detectedColumns,
    hasHourlyData,
    aggregatedFromRows: hasHourlyData ? originalRowCount : undefined,
  };
}
