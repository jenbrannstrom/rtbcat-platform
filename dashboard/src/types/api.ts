export interface VideoPreview {
  video_url: string | null;
  thumbnail_url: string | null;
  vast_xml: string | null;
  duration: string | null;
}

export interface HtmlPreview {
  snippet: string | null;
  width: number | null;
  height: number | null;
  thumbnail_url: string | null;
}

export interface ImagePreview {
  url: string | null;
  width: number | null;
  height: number | null;
}

export interface NativePreview {
  headline: string | null;
  body: string | null;
  call_to_action: string | null;
  click_link_url: string | null;
  image: ImagePreview | null;
  logo: ImagePreview | null;
}

export interface Creative {
  id: string;
  name: string;
  format: string;
  account_id: string | null;
  buyer_id: string | null;
  approval_status: string | null;
  width: number | null;
  height: number | null;
  final_url: string | null;
  display_url: string | null;
  utm_source: string | null;
  utm_medium: string | null;
  utm_campaign: string | null;
  utm_content: string | null;
  utm_term: string | null;
  advertiser_name: string | null;
  campaign_id: string | null;
  cluster_id: string | null;
  seat_name: string | null;
  country: string | null;
  // Preview data
  video: VideoPreview | null;
  html: HtmlPreview | null;
  native: NativePreview | null;
  // Language detection (Creative geo display)
  detected_language: string | null;
  detected_language_code: string | null;
  language_confidence: number | null;
  language_source: string | null;
  language_analyzed_at: string | null;
  language_analysis_error: string | null;
  // Approval details
  is_disapproved?: boolean;
  disapproval_reasons?: Array<{ reason: string; details?: string }> | null;
  serving_restrictions?: Array<{ status: string; contexts?: unknown[]; disapproval_reasons?: unknown[] }> | null;
  data_source?: {
    source: "live" | "cache" | string;
    cached_at: string | null;
    fetched_at: string | null;
    stale_threshold_hours: number | null;
    stale_age_hours: number | null;
    is_stale: boolean;
    fallback_reason: string | null;
  } | null;
}

export interface CreativeLiveResponse {
  creative: Creative;
  source: "live" | "cache";
  fetched_at: string;
  message: string | null;
}

export interface Campaign {
  id: string;
  name: string;
  source: string;
  creative_count: number;
  metadata: Record<string, unknown>;
}

export interface Stats {
  creative_count: number;
  campaign_count: number;
  cluster_count: number;
  formats: Record<string, number>;
  db_path: string;
}

export interface Health {
  status: string;
  version: string;
  configured: boolean;
}

export interface CollectRequest {
  account_id: string;
  filter_query?: string;
}

export interface CollectResponse {
  status: string;
  account_id: string;
  filter_query: string | null;
  message: string;
  creatives_collected: number | null;
}

export interface SizesResponse {
  sizes: string[];
}

export interface BuyerSeat {
  buyer_id: string;
  bidder_id: string;
  display_name: string | null;
  active: boolean;
  creative_count: number;
  last_synced: string | null;
  created_at: string | null;
}

export interface DiscoverSeatsRequest {
  bidder_id: string;
}

export interface DiscoverSeatsResponse {
  status: string;
  bidder_id: string;
  seats_discovered: number;
  seats: BuyerSeat[];
  sync_result?: {
    creatives_synced: number;
    endpoints_synced: number;
    pretargeting_synced: number;
  };
}

export interface SyncSeatResponse {
  status: string;
  buyer_id: string;
  creatives_synced: number;
  message: string;
}

// Waste Analysis Types

export interface SizeGap {
  canonical_size: string;
  request_count: number;
  creative_count: number;
  estimated_qps: number;
  estimated_waste_pct: number;
  recommendation: string;
  recommendation_detail: string;
  potential_savings_usd: number | null;
  closest_iab_size: string | null;
}

export interface SizeCoverage {
  canonical_size: string;
  creative_count: number;
  request_count: number;
  coverage_status: "good" | "low" | "none" | "excess" | "unknown";
  formats: Record<string, number>;
}

export interface WasteReport {
  buyer_id: string | null;
  total_requests: number;
  total_waste_requests: number;
  waste_percentage: number;
  size_gaps: SizeGap[];
  size_coverage: SizeCoverage[];
  potential_savings_qps: number;
  potential_savings_usd: number | null;
  qps_basis: "avg_daily";
  analysis_period_days: number;
  generated_at: string;
  recommendations_summary: {
    block: number;
    add_creative: number;
    use_flexible: number;
    monitor: number;
    top_savings_size: string | null;
    top_savings_qps: number;
  };
}

export interface ImportTrafficResponse {
  status: string;
  records_imported: number;
  message: string;
}

// Performance Metrics Types

export interface CreativePerformanceSummary {
  creative_id: string;
  total_impressions: number;
  total_clicks: number;
  total_spend_micros: number;
  avg_cpm_micros: number | null;
  avg_cpc_micros: number | null;
  ctr_percent: number | null;
  days_with_data: number;
  has_data: boolean;
  // Data provenance metadata
  metric_source?: string | null; // "rtb_daily" | "pretarg_creative_daily"
  clicks_available?: boolean; // true if source has real clicks data
}

export interface BatchPerformanceResponse {
  performance: Record<string, CreativePerformanceSummary>;
  period: string;
  count: number;
}

export type PerformancePeriod = "yesterday" | "7d" | "14d" | "30d" | "all_time";

// Country Breakdown Types

export interface CreativeCountryMetrics {
  country_code: string;
  country_name: string;
  country_iso3?: string;
  spend_micros: number;
  impressions: number;
  clicks: number;
  spend_percent: number;
}

export interface CreativeCountryBreakdown {
  creative_id: string;
  countries: CreativeCountryMetrics[];
  total_countries: number;
  period_days: number;
}

// Language Detection Types

export interface LanguageDetectionResponse {
  creative_id: string;
  detected_language: string | null;
  detected_language_code: string | null;
  language_confidence: number | null;
  language_source: string | null;
  language_analyzed_at: string | null;
  language_analysis_error: string | null;
  success: boolean;
}

export interface GeoMismatchAlert {
  severity: string;
  language: string;
  language_code: string;
  mismatched_countries: string[];
  expected_countries: string[];
  message: string;
}

export interface GeoMismatchResponse {
  creative_id: string;
  has_mismatch: boolean;
  alert: GeoMismatchAlert | null;
  serving_countries: string[];
}

export interface ManualLanguageUpdate {
  detected_language: string;
  detected_language_code: string;
}
