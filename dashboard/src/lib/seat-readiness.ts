export interface BuyerSeatLike {
  buyer_id: string;
}

export function isSeatReadyForAnalytics(
  selectedBuyerId: string | null,
  seats: BuyerSeatLike[] | null | undefined,
): boolean {
  if (!selectedBuyerId) return false;
  if (!Array.isArray(seats) || seats.length === 0) return false;
  return seats.some((seat) => seat.buyer_id === selectedBuyerId);
}
