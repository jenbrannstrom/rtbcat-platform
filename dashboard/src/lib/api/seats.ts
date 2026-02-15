/**
 * Seats API module.
 * Handles buyer seats, discovery, sync, and data collection.
 */

import { fetchApi } from "./core";
import type {
  BuyerSeat,
  DiscoverSeatsRequest,
  DiscoverSeatsResponse,
  SyncSeatResponse,
  CollectRequest,
  CollectResponse,
} from "@/types/api";

// =============================================================================
// Buyer Seats CRUD
// =============================================================================

export async function getSeats(params?: {
  bidder_id?: string;
  active_only?: boolean;
}): Promise<BuyerSeat[]> {
  const searchParams = new URLSearchParams();
  if (params?.bidder_id) searchParams.set("bidder_id", params.bidder_id);
  if (params?.active_only !== undefined) {
    searchParams.set("active_only", String(params.active_only));
  }

  const query = searchParams.toString();
  return fetchApi<BuyerSeat[]>(`/seats${query ? `?${query}` : ""}`);
}

export async function getSeat(buyerId: string): Promise<BuyerSeat> {
  return fetchApi<BuyerSeat>(`/seats/${encodeURIComponent(buyerId)}`);
}

export async function updateSeat(
  buyerId: string,
  updates: { display_name?: string }
): Promise<BuyerSeat> {
  return fetchApi<BuyerSeat>(`/seats/${encodeURIComponent(buyerId)}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function populateSeatsFromCreatives(): Promise<{
  status: string;
  seats_created: number;
}> {
  return fetchApi<{ status: string; seats_created: number }>("/seats/populate", {
    method: "POST",
  });
}

// =============================================================================
// Discovery & Sync
// =============================================================================

export async function discoverSeats(
  request: DiscoverSeatsRequest
): Promise<DiscoverSeatsResponse> {
  return fetchApi<DiscoverSeatsResponse>("/seats/discover", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function syncSeat(
  buyerId: string,
  filterQuery?: string
): Promise<SyncSeatResponse> {
  const searchParams = new URLSearchParams();
  if (filterQuery) searchParams.set("filter_query", filterQuery);
  const query = searchParams.toString();

  return fetchApi<SyncSeatResponse>(
    `/seats/${encodeURIComponent(buyerId)}/sync${query ? `?${query}` : ""}`,
    { method: "POST" }
  );
}

export interface SyncAllResponse {
  status: string;
  creatives_synced: number;
  seats_synced: number;
  endpoints_synced: number;
  pretargeting_synced: number;
  message: string;
  last_synced: string | null;
  errors?: string[];
}

export async function syncAllData(): Promise<SyncAllResponse> {
  return fetchApi<SyncAllResponse>("/seats/sync-all", {
    method: "POST",
  });
}

// =============================================================================
// Data Collection
// =============================================================================

export async function collectCreatives(
  request: CollectRequest
): Promise<CollectResponse> {
  return fetchApi<CollectResponse>("/collect", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function collectCreativesSync(
  request: CollectRequest
): Promise<CollectResponse> {
  return fetchApi<CollectResponse>("/collect/sync", {
    method: "POST",
    body: JSON.stringify(request),
  });
}
