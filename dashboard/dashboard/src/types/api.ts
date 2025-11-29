export interface VideoPreview {
  video_url: string | null;
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
