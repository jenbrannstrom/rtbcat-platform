import { describe, expect, it } from "vitest";

import {
  validateAgentTokenMint,
  type AgentTokenMintValues,
} from "@/lib/agent-token-validation";

const validValues: AgentTokenMintValues = {
  name: "Daily reporting agent",
  userId: "user-1",
  targetUserRole: "read",
  buyerId: "buyer-1",
  allGrantedBuyers: false,
  grantedBuyerIds: ["buyer-1", "buyer-2"],
  scopes: ["agent:stats:read"],
  expiresInDays: 90,
};

describe("validateAgentTokenMint", () => {
  it("accepts single-buyer and all-granted non-sudo tokens", () => {
    expect(validateAgentTokenMint(validValues)).toEqual({});
    expect(
      validateAgentTokenMint({
        ...validValues,
        buyerId: "",
        allGrantedBuyers: true,
      })
    ).toEqual({});
  });

  it("validates name, target, expiry, and scopes", () => {
    const errors = validateAgentTokenMint({
      ...validValues,
      name: "  ",
      userId: "",
      scopes: [],
      expiresInDays: 367,
    });

    expect(errors).toEqual({
      name: "Name must be between 3 and 120 characters.",
      userId: "Select a target user.",
      expiresInDays: "Expiry must be a whole number between 1 and 366 days.",
      scopes: "Select at least one supported scope.",
    });
  });

  it("requires a granted buyer scope for non-sudo users", () => {
    expect(
      validateAgentTokenMint({ ...validValues, buyerId: "buyer-3" }).buyerScope
    ).toBe("The target user does not have access to that buyer.");
    expect(
      validateAgentTokenMint({ ...validValues, buyerId: "" }).buyerScope
    ).toBe("Select one buyer or enable all granted buyers.");
    expect(
      validateAgentTokenMint({ ...validValues, buyerId: "", grantedBuyerIds: [] }).buyerScope
    ).toBe("The target user has no buyer seat grants.");
    expect(
      validateAgentTokenMint({ ...validValues, allGrantedBuyers: true }).buyerScope
    ).toBe("Choose either one buyer or all granted buyers.");
  });

  it("forces sudo targets to an explicit buyer scope", () => {
    expect(
      validateAgentTokenMint({
        ...validValues,
        targetUserRole: "sudo",
        buyerId: "",
        allGrantedBuyers: true,
      }).buyerScope
    ).toBe("Sudo users must use one buyer or selected buyers.");
    expect(
      validateAgentTokenMint({
        ...validValues,
        targetUserRole: "sudo",
        buyerId: "",
      }).buyerScope
    ).toBe("Select a buyer for this sudo user.");
  });

  it("accepts selected buyers for sudo and non-sudo targets", () => {
    const selected = { ...validValues, buyerId: "", buyerIds: ["buyer-1", "buyer-2"] };
    expect(validateAgentTokenMint(selected)).toEqual({});
    expect(
      validateAgentTokenMint({
        ...selected,
        targetUserRole: "sudo",
        buyerIds: ["1487810529", "6574658621", "6634662463", "7942355670", "8087233591"],
        grantedBuyerIds: [],
      })
    ).toEqual({});
  });

  it("rejects selected buyers outside the grants, mixed with another option, or over 50", () => {
    expect(
      validateAgentTokenMint({ ...validValues, buyerId: "", buyerIds: ["buyer-1", "buyer-3"] })
        .buyerScope
    ).toBe("The target user does not have access to every selected buyer.");
    expect(
      validateAgentTokenMint({ ...validValues, buyerIds: ["buyer-2"] }).buyerScope
    ).toBe("Choose only one buyer scope option.");
    expect(
      validateAgentTokenMint({
        ...validValues,
        buyerId: "",
        buyerIds: ["buyer-1"],
        allGrantedBuyers: true,
      }).buyerScope
    ).toBe("Choose only one buyer scope option.");
    expect(
      validateAgentTokenMint({
        ...validValues,
        targetUserRole: "sudo",
        buyerId: "",
        buyerIds: Array.from({ length: 51 }, (_, index) => `buyer-${index}`),
      }).buyerScope
    ).toBe("Select at most 50 buyers.");
  });
});
