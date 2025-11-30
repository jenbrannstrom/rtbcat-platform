export interface PerformanceRow {
  creative_id: number;
  date: string; // YYYY-MM-DD
  impressions: number;
  clicks: number;
  spend: number;
  geography?: string; // 2-letter code
}

export interface ValidationError {
  row: number;
  field: string;
  error: string;
  value: unknown;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  rowCount: number;
  data: PerformanceRow[];
}

export interface ImportResponse {
  success: boolean;
  imported: number;
  duplicates?: number;
  errors?: number;
  error_details?: ValidationError[];
  date_range?: {
    start: string;
    end: string;
  };
  total_spend?: number;
  error?: string;
}
