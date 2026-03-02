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
  resolved_destination_url?: string | null;
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

export interface CreativeDestinationCandidate {
  source: string;
  url: string;
  eligible: boolean;
  reason: string | null;
}

export interface CreativeDestinationDiagnostics {
  creative_id: string;
  buyer_id: string | null;
  resolved_destination_url: string | null;
  candidate_count: number;
  eligible_count: number;
  candidates: CreativeDestinationCandidate[];
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

export interface DataHealthTableState {
  rows: number;
  max_metric_date: string | null;
}

export interface DataHealthSourceFreshness {
  rtb_daily: DataHealthTableState;
  rtb_geo_daily: DataHealthTableState;
}

export interface DataHealthServingFreshness {
  home_geo_daily: DataHealthTableState;
  config_geo_daily: DataHealthTableState;
  config_publisher_daily: DataHealthTableState;
}

export interface DataCoverageSummary {
  total_rows: number;
  country_missing_pct: number;
  publisher_missing_pct: number;
  billing_missing_pct: number;
  availability_state: string;
}

export interface IngestionRunsSummary {
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  last_started_at: string | null;
  last_finished_at: string | null;
}

export interface ReportTableCompletenessState {
  rows: number;
  active_days: number;
  expected_days: number;
  coverage_pct: number;
  max_metric_date: string | null;
  availability_state: string;
}

export interface ReportCompletenessSummary {
  expected_report_types: number;
  available_report_types: number;
  coverage_pct: number;
  missing_report_types: string[];
  availability_state: string;
  tables: Record<string, ReportTableCompletenessState>;
}

export interface QualityFreshnessSummary {
  rows: number;
  max_metric_date: string | null;
  age_days: number | null;
  fresh_within_days: number;
  availability_state: string;
}

export interface BidstreamDimensionCoverageSummary {
  total_rows: number;
  platform_missing_pct: number;
  environment_missing_pct: number;
  transaction_type_missing_pct: number;
  availability_state: string;
}

export interface SeatDayCompletenessRow {
  metric_date: string | null;
  buyer_account_id: string;
  has_rtb_daily: boolean;
  has_rtb_bidstream: boolean;
  has_rtb_bid_filtering: boolean;
  has_rtb_quality: boolean;
  has_web_domain_daily: boolean;
  available_report_types: number;
  expected_report_types: number;
  completeness_pct: number;
  availability_state: string;
  refreshed_at: string | null;
}

export interface SeatDayCompletenessSummary {
  total_seat_days: number;
  healthy_seat_days: number;
  degraded_seat_days: number;
  unavailable_seat_days: number;
  avg_completeness_pct: number;
  min_completeness_pct: number;
  max_completeness_pct: number;
}

export interface SeatDayCompletenessPayload {
  rows: SeatDayCompletenessRow[];
  summary: SeatDayCompletenessSummary;
  availability_state: string;
  refreshed_at: string | null;
}

export interface OptimizerReadinessSummary {
  report_completeness: ReportCompletenessSummary;
  rtb_quality_freshness: QualityFreshnessSummary;
  bidstream_dimension_coverage: BidstreamDimensionCoverageSummary;
  seat_day_completeness: SeatDayCompletenessPayload;
}

export interface DataHealthResponse {
  checked_at: string;
  days: number;
  buyer_id: string | null;
  state: string;
  source_freshness: DataHealthSourceFreshness;
  serving_freshness: DataHealthServingFreshness;
  coverage: DataCoverageSummary;
  ingestion_runs: IngestionRunsSummary;
  optimizer_readiness: OptimizerReadinessSummary;
}

export interface PaginationMeta {
  timeframe_days?: number | null;
  total: number;
  returned: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface PaginatedCreativesResponse {
  data: Creative[];
  meta: PaginationMeta;
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

export interface GeoLinguisticFinding {
  category: string;
  severity: string;
  description: string;
  evidence: string;
}

export interface GeoLinguisticEvidenceSummary {
  text_length: number;
  image_count: number;
  ocr_texts_count: number;
  video_frames_count: number;
  has_screenshot: boolean;
  currencies_detected: string[];
  cta_phrases: string[];
}

export interface GeoLinguisticEvidence {
  id: string;
  run_id: string;
  evidence_type: string;
  file_path: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface GeoLinguisticReport {
  status: string;
  run_id: string | null;
  creative_id: string;
  decision: string;
  risk_score: number;
  confidence: number;
  primary_languages: string[];
  secondary_languages: string[];
  detected_currencies: string[];
  findings: GeoLinguisticFinding[];
  serving_countries: string[];
  evidence_summary: GeoLinguisticEvidenceSummary | null;
  evidence: GeoLinguisticEvidence[];
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
}
