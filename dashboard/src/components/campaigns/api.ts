/**
 * API functions for campaigns page.
 */

import type { Campaign, CampaignCreative, AutoClusterResponse } from './types';

export async function fetchCampaigns(): Promise<Campaign[]> {
  const res = await fetch('/api/campaigns');
  if (!res.ok) throw new Error('Failed to fetch campaigns');
  return res.json();
}

export async function fetchUnclustered(buyerId?: string | null): Promise<{ creative_ids: string[]; count: number }> {
  const params = new URLSearchParams();
  if (buyerId) params.set('buyer_id', buyerId);
  const query = params.toString();
  const res = await fetch(`/api/campaigns/unclustered${query ? `?${query}` : ''}`);
  if (!res.ok) throw new Error('Failed to fetch unclustered');
  return res.json();
}

export async function fetchAllCreatives(buyerId?: string | null): Promise<CampaignCreative[]> {
  const params = new URLSearchParams({ limit: '1000' });
  if (buyerId) params.set('buyer_id', buyerId);
  const res = await fetch(`/api/creatives?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch creatives');
  const data = await res.json();
  // API returns list directly, not { creatives: [...] }
  return Array.isArray(data) ? data : (data.creatives || []);
}

export async function autoCluster(buyerId?: string | null): Promise<AutoClusterResponse> {
  const res = await fetch('/api/campaigns/auto-cluster', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ by_url: true, buyer_id: buyerId ?? undefined }),
  });
  if (!res.ok) throw new Error('Failed to auto-cluster');
  return res.json();
}

export async function createCampaign(data: { name: string; creative_ids: string[] }): Promise<Campaign> {
  const res = await fetch('/api/campaigns', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create campaign');
  return res.json();
}

export async function updateCampaign(
  id: string,
  data: { name?: string; add_creative_ids?: string[]; remove_creative_ids?: string[] }
): Promise<Campaign> {
  const res = await fetch(`/api/campaigns/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update campaign');
  return res.json();
}

export async function deleteCampaign(id: string): Promise<void> {
  const res = await fetch(`/api/campaigns/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete campaign');
}
