/**
 * Type definitions for campaigns page.
 */

export interface Campaign {
  id: string;
  name: string;
  creative_ids: string[];
  created_at: string | null;
  updated_at: string | null;
  // Phase 29: Disapproval tracking
  disapproved_count?: number;
  has_disapproved?: boolean;
}

export interface CampaignCreative {
  id: string;
  format: string;
  country?: string;  // Phase 22: Country from performance data
  created_at?: string;  // Phase 24: Date Added sort
  final_url?: string;
  video?: { thumbnail_url?: string };
  native?: { logo?: { url?: string }; image?: { url?: string } };
  html?: { thumbnail_url?: string };  // Phase 22: HTML thumbnail
  performance?: {
    total_spend_micros?: number;
    total_impressions?: number;
    total_clicks?: number;
  };
  waste_flags?: { broken_video?: boolean; zero_engagement?: boolean };
  // Phase 29: App info and disapproval tracking
  app_id?: string;
  app_name?: string;
  is_disapproved?: boolean;
  disapproval_reasons?: Array<{ reason: string; details?: string }>;
  serving_restrictions?: Array<{ restriction: string; contexts?: string[] }>;
}

export interface ClusterSuggestion {
  suggested_name: string;
  creative_ids: string[];
  domain: string | null;
}

export interface AutoClusterResponse {
  suggestions: ClusterSuggestion[];
  unclustered_count: number;
}

export type ViewMode = 'grid' | 'list';

export type SortField = 'spend' | 'impressions' | 'clicks' | 'creatives' | 'name';
export type SortDirection = 'asc' | 'desc';
