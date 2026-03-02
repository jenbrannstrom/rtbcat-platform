import type { BuyerSeat } from "@/types/api";

export interface CanonicalBuyerResolutionInput {
  buyerIdInPath: string | null;
  selectedBuyerId: string | null;
  seats: BuyerSeat[] | undefined;
}

export interface CanonicalBuyerResolution {
  canonicalBuyerId: string | null;
  buyerInPathValid: boolean;
  selectedBuyerValid: boolean;
  seatsLoaded: boolean;
}

function hasSeat(seats: BuyerSeat[], buyerId: string | null): boolean {
  if (!buyerId) return false;
  return seats.some((seat) => seat.buyer_id === buyerId);
}

/**
 * Resolve one deterministic buyer context from URL, local state, and known seats.
 * URL buyer is preferred only when it is a valid active seat.
 */
export function resolveCanonicalBuyerId({
  buyerIdInPath,
  selectedBuyerId,
  seats,
}: CanonicalBuyerResolutionInput): CanonicalBuyerResolution {
  if (!seats) {
    return {
      canonicalBuyerId: buyerIdInPath ?? selectedBuyerId ?? null,
      buyerInPathValid: !!buyerIdInPath,
      selectedBuyerValid: !!selectedBuyerId,
      seatsLoaded: false,
    };
  }

  const buyerInPathValid = hasSeat(seats, buyerIdInPath);
  const selectedBuyerValid = hasSeat(seats, selectedBuyerId);
  const fallbackBuyerId = seats.length > 0 ? seats[0].buyer_id : null;

  const canonicalBuyerId = buyerInPathValid
    ? buyerIdInPath
    : selectedBuyerValid
      ? selectedBuyerId
      : fallbackBuyerId;

  return {
    canonicalBuyerId,
    buyerInPathValid,
    selectedBuyerValid,
    seatsLoaded: true,
  };
}
