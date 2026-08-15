import {
  AGENT_TOKEN_SCOPES,
  type AgentTokenScope,
} from "@/lib/api/agent-tokens";

export interface AgentTokenMintValues {
  name: string;
  userId: string;
  targetUserRole: string | null;
  buyerId: string;
  allGrantedBuyers: boolean;
  grantedBuyerIds: string[];
  scopes: AgentTokenScope[];
  expiresInDays: number;
}

export type AgentTokenMintErrors = Partial<
  Record<"name" | "userId" | "buyerScope" | "scopes" | "expiresInDays", string>
>;

/** Mirrors the API's mint constraints without retaining any token material. */
export function validateAgentTokenMint(
  values: AgentTokenMintValues
): AgentTokenMintErrors {
  const errors: AgentTokenMintErrors = {};
  const normalizedName = values.name.trim();

  if (normalizedName.length < 3 || normalizedName.length > 120) {
    errors.name = "Name must be between 3 and 120 characters.";
  }

  if (!values.userId) {
    errors.userId = "Select a target user.";
  }

  if (!Number.isInteger(values.expiresInDays) || values.expiresInDays < 1 || values.expiresInDays > 366) {
    errors.expiresInDays = "Expiry must be a whole number between 1 and 366 days.";
  }

  const supportedScopes = new Set<string>(AGENT_TOKEN_SCOPES);
  if (values.scopes.length === 0 || values.scopes.some((scope) => !supportedScopes.has(scope))) {
    errors.scopes = "Select at least one supported scope.";
  }

  if (values.targetUserRole === "sudo") {
    if (values.allGrantedBuyers) {
      errors.buyerScope = "Sudo users must use a single buyer scope.";
    } else if (!values.buyerId) {
      errors.buyerScope = "Select a buyer for this sudo user.";
    }
  } else if (values.userId) {
    if (values.grantedBuyerIds.length === 0) {
      errors.buyerScope = "The target user has no buyer seat grants.";
    } else if (values.allGrantedBuyers && values.buyerId) {
      errors.buyerScope = "Choose either one buyer or all granted buyers.";
    } else if (!values.allGrantedBuyers && !values.buyerId) {
      errors.buyerScope = "Select one buyer or enable all granted buyers.";
    } else if (values.buyerId && !values.grantedBuyerIds.includes(values.buyerId)) {
      errors.buyerScope = "The target user does not have access to that buyer.";
    }
  }

  return errors;
}
