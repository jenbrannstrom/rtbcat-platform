import type {
  PerformanceRow,
  ValidationError,
  ValidationResult,
  Anomaly,
  Warning,
  AnomalyType,
} from "@/lib/types/import";
import type { ParseResult } from "@/lib/csv-parser";

export interface ExtendedValidationResult extends ValidationResult {
  detectedColumns?: ParseResult["detectedColumns"];
  hasHourlyData?: boolean;
  aggregatedFromRows?: number;
}

/**
 * Forgiving CSV validator - imports all data, flags anomalies
 *
 * Philosophy: The only thing that should block import is a completely unparseable file.
 * Clicks > impressions? That's a FRAUD SIGNAL - we want that data!
 */
export function validatePerformanceCSV(parseResult: ParseResult): ExtendedValidationResult {
  const errors: ValidationError[] = [];
  const warnings: Warning[] = [];
  const anomalies: Anomaly[] = [];
  const { data, detectedColumns, hasHourlyData, originalRowCount } = parseResult;

  // Only truly fatal error: no data at all due to missing columns
  if (data.length === 0) {
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
      warnings,
      anomalies,
      rowCount: 0,
      data: [],
      detectedColumns,
      hasHourlyData,
    };
  }

  // Process each row - NEVER reject, only flag anomalies
  const validData: PerformanceRow[] = [];

  data.forEach((row, index) => {
    const rowNum = index + 2; // +2 for header and 0-based index

    // ============================================
    // AUTO-FIX: Fix negative values silently
    // ============================================
    if (row.impressions < 0) {
      warnings.push({
        row: rowNum,
        field: "impressions",
        message: `Negative impressions (${row.impressions}) set to 0`,
        severity: "info",
      });
      row.impressions = 0;
    }

    if (row.clicks < 0) {
      warnings.push({
        row: rowNum,
        field: "clicks",
        message: `Negative clicks (${row.clicks}) set to 0`,
        severity: "info",
      });
      row.clicks = 0;
    }

    if (row.spend < 0) {
      warnings.push({
        row: rowNum,
        field: "spend",
        message: `Negative spend (${row.spend}) set to 0`,
        severity: "info",
      });
      row.spend = 0;
    }

    // ============================================
    // FRAUD SIGNALS - Flag but NEVER block
    // ============================================

    // Clicks > Impressions = FRAUD SIGNAL (click injection, fake clicks)
    if (row.clicks > row.impressions) {
      anomalies.push({
        row: rowNum,
        type: "clicks_exceed_impressions",
        details: {
          clicks: row.clicks,
          impressions: row.impressions,
          app_name: row.app_name,
          app_id: row.app_id,
          creative_id: row.creative_id,
        },
      });
      warnings.push({
        row: rowNum,
        field: "clicks",
        message: `Clicks (${row.clicks}) > Impressions (${row.impressions}) - possible click fraud`,
        severity: "warning",
      });
    }

    // Extremely high CTR (>10%) is suspicious
    if (row.impressions > 0 && row.clicks / row.impressions > 0.10) {
      anomalies.push({
        row: rowNum,
        type: "extremely_high_ctr",
        details: {
          ctr: (row.clicks / row.impressions * 100).toFixed(1) + "%",
          clicks: row.clicks,
          impressions: row.impressions,
          app_name: row.app_name,
          creative_id: row.creative_id,
        },
      });
    }

    // Spend with zero impressions?
    if (row.spend > 0 && row.impressions === 0) {
      anomalies.push({
        row: rowNum,
        type: "zero_impressions_with_spend",
        details: {
          spend: row.spend,
          app_name: row.app_name,
          creative_id: row.creative_id,
        },
      });
      warnings.push({
        row: rowNum,
        field: "spend",
        message: `Spend ($${row.spend.toFixed(2)}) with zero impressions`,
        severity: "warning",
      });
    }

    // ============================================
    // DATA QUALITY WARNINGS - Inform but don't block
    // ============================================

    // Invalid creative_id - use 0 as placeholder
    if (!Number.isInteger(row.creative_id) || row.creative_id <= 0) {
      warnings.push({
        row: rowNum,
        field: "creative_id",
        message: `Invalid creative_id (${row.creative_id}) - row will be skipped`,
        severity: "warning",
      });
      // Skip this row - we can't import without a valid creative_id
      return;
    }

    // Check date format - skip if truly invalid
    if (!/^\d{4}-\d{2}-\d{2}$/.test(row.date)) {
      warnings.push({
        row: rowNum,
        field: "date",
        message: `Invalid date format (${row.date}) - row will be skipped`,
        severity: "warning",
      });
      return;
    }

    // Future date - flag but import
    const date = new Date(row.date);
    const today = new Date();
    today.setHours(23, 59, 59, 999);
    if (date > today) {
      anomalies.push({
        row: rowNum,
        type: "future_date",
        details: {
          date: row.date,
          creative_id: row.creative_id,
        },
      });
      warnings.push({
        row: rowNum,
        field: "date",
        message: `Future date (${row.date}) - data imported anyway`,
        severity: "info",
      });
    }

    // Very old date (> 1 year) - flag but import
    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
    if (date < oneYearAgo) {
      anomalies.push({
        row: rowNum,
        type: "very_old_date",
        details: {
          date: row.date,
          creative_id: row.creative_id,
        },
      });
    }

    // Row is valid - add to import data
    validData.push(row);
  });

  // ============================================
  // ALWAYS VALID (unless no columns detected)
  // ============================================
  return {
    valid: true, // Forgiving: always allow import
    errors: [], // No blocking errors
    warnings,
    anomalies,
    rowCount: data.length,
    data: validData,
    detectedColumns,
    hasHourlyData,
    aggregatedFromRows: hasHourlyData ? originalRowCount : undefined,
  };
}

/**
 * Group anomalies by type for display
 */
export function groupAnomaliesByType(anomalies: Anomaly[]): Record<AnomalyType, Anomaly[]> {
  const grouped: Partial<Record<AnomalyType, Anomaly[]>> = {};

  for (const anomaly of anomalies) {
    if (!grouped[anomaly.type]) {
      grouped[anomaly.type] = [];
    }
    grouped[anomaly.type]!.push(anomaly);
  }

  return grouped as Record<AnomalyType, Anomaly[]>;
}

/**
 * Get top apps with anomalies
 */
export function getTopAnomalyApps(anomalies: Anomaly[], limit = 10): { app_name: string; app_id?: string; count: number }[] {
  const appCounts = new Map<string, { app_name: string; app_id?: string; count: number }>();

  for (const anomaly of anomalies) {
    const appName = (anomaly.details.app_name as string) || "Unknown";
    const appId = anomaly.details.app_id as string | undefined;
    const key = appId || appName;

    if (!appCounts.has(key)) {
      appCounts.set(key, { app_name: appName, app_id: appId, count: 0 });
    }
    appCounts.get(key)!.count++;
  }

  return Array.from(appCounts.values())
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}

/**
 * Format anomaly type for display
 */
export function formatAnomalyType(type: AnomalyType): string {
  const labels: Record<AnomalyType, string> = {
    clicks_exceed_impressions: "Clicks > Impressions (click fraud)",
    extremely_high_ctr: "CTR > 10% (suspicious)",
    zero_impressions_with_spend: "Spend with no impressions",
    negative_values: "Negative values (corrected)",
    future_date: "Future date",
    very_old_date: "Very old date (>1 year)",
  };
  return labels[type] || type;
}
