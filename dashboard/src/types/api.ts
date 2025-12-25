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
  // Preview data
  video: VideoPreview | null;
  html: HtmlPreview | null;
  native: NativePreview | null;
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
}

export interface BatchPerformanceResponse {
  performance: Record<string, CreativePerformanceSummary>;
  period: string;
  count: number;
}

export type PerformancePeriod = "yesterday" | "7d" | "30d" | "all_time";
