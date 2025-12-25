export interface PerformanceRow {
  creative_id: number;
  date: string; // YYYY-MM-DD
  impressions: number;
  clicks: number;
  spend: number;
  geography?: string; // 2-letter code or country name
  app_id?: string;
  app_name?: string;
}

export interface ValidationError {
  row: number;
  field: string;
  error: string;
  value: unknown;
}

// Anomaly types for fraud detection
export type AnomalyType =
  | "clicks_exceed_impressions" // Fraud signal!
  | "extremely_high_ctr" // CTR > 10% is suspicious
  | "zero_impressions_with_spend" // Paid for nothing?
  | "negative_values" // Data corruption
  | "future_date" // Date in the future
  | "very_old_date"; // Date > 1 year ago

export interface Anomaly {
  row: number;
  type: AnomalyType;
  details: Record<string, unknown>;
}

export interface Warning {
  row: number;
  field: string;
  message: string;
  severity: "info" | "warning";
}

export interface ValidationResult {
  valid: boolean; // Now always true for forgiving validator (except unparseable files)
  errors: ValidationError[]; // Only truly fatal errors (missing columns)
  warnings: Warning[]; // Informational messages
  anomalies: Anomaly[]; // Fraud signals - data is imported but flagged
  rowCount: number;
  data: PerformanceRow[];
}

export interface ImportResponse {
  success: boolean;
  imported?: number;
  duplicates?: number;
  errors?: number;
  error_details?: ValidationError[];
  anomalies?: Anomaly[];
  date_range?: {
    start: string;
    end: string;
  };
  total_spend?: number;
  error?: string;
  // Column mapping info from backend
  columns_imported?: string[];
  columns_found?: string[];
  columns_mapped?: Record<string, string>;
  required_missing?: string[];
  fix_instructions?: string;
  // Additional stats
  rows_read?: number;
  rows_skipped?: number;
  unique_creatives?: number;
  unique_sizes?: number;
  unique_countries?: number;
  billing_ids?: string[];
  total_reached?: number;
  total_impressions?: number;
}
