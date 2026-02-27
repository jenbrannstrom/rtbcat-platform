/**
 * Feature gating utilities for restricting specific users to limited views.
 */

interface UserLike {
  email: string;
}

/** Emails restricted to home-only view (lowercase). */
const RESTRICTED_EMAILS = new Set(["dea@rtb.cat"]);

/** Paths allowed for restricted users (exact match on pathWithoutBuyer). */
const RESTRICTED_ALLOWED_PATHS = new Set(["/"]);

/** Returns true if the user should see only the restricted (home-only) view. */
export function isRestrictedUser(user: UserLike | null | undefined): boolean {
  if (!user?.email) return false;
  return RESTRICTED_EMAILS.has(user.email.toLowerCase());
}

/** Returns true if the given pathWithoutBuyer is accessible to restricted users. */
export function isAllowedForRestrictedUser(pathWithoutBuyer: string): boolean {
  return RESTRICTED_ALLOWED_PATHS.has(pathWithoutBuyer);
}
