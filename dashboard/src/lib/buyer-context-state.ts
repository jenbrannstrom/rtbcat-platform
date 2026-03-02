import type { BuyerSeat } from "@/types/api";

/**
 * Unambiguous buyer-context validity states for operator-facing UI.
 *
 * - `loading`                 – seats are still being fetched.
 * - `no_active_seats`         – seats loaded but the list is empty.
 * - `selected_buyer_invalid`  – seats loaded, at least one exists, but
 *                               the currently selected buyer is not among them.
 * - `selected_buyer_valid`    – seats loaded and the selected buyer is a
 *                               valid active seat.
 */
export type BuyerContextValidity =
  | "loading"
  | "no_active_seats"
  | "selected_buyer_invalid"
  | "selected_buyer_valid";

export interface BuyerContextState {
  validity: BuyerContextValidity;
  /** Short operator-facing explanation suitable for a banner. */
  message: string;
  /** Whether buyer-scoped data queries should be enabled. */
  canQuery: boolean;
}

export function deriveBuyerContextState(
  selectedBuyerId: string | null,
  seats: BuyerSeat[] | undefined,
  seatsLoading: boolean,
): BuyerContextState {
  if (seatsLoading || seats === undefined) {
    return {
      validity: "loading",
      message: "Loading buyer seats\u2026",
      canQuery: false,
    };
  }

  if (seats.length === 0) {
    return {
      validity: "no_active_seats",
      message:
        "No active buyer seats found. Add and activate at least one buyer seat in Accounts before proceeding.",
      canQuery: false,
    };
  }

  if (
    !selectedBuyerId ||
    !seats.some((s) => s.buyer_id === selectedBuyerId)
  ) {
    return {
      validity: "selected_buyer_invalid",
      message:
        "The selected buyer is not an active seat. Choose a valid buyer from the header dropdown, or activate the seat in Accounts.",
      canQuery: false,
    };
  }

  return {
    validity: "selected_buyer_valid",
    message: `Buyer ${selectedBuyerId} is active and selected.`,
    canQuery: true,
  };
}
