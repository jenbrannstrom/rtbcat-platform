"use client";

import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertTriangle,
  Check,
  Copy,
  KeyRound,
  Plus,
  RefreshCw,
  ShieldAlert,
  X,
} from "lucide-react";

import { withAdminAuth } from "@/contexts/auth-context";
import { useTranslation } from "@/contexts/i18n-context";
import {
  AGENT_TOKEN_SCOPES,
  createAgentToken,
  getAdminUsers,
  getAgentTokens,
  getSeats,
  getUserSeatPermissions,
  revokeAgentToken,
  type AdminUser,
  type AgentTokenRecord,
  type AgentTokenScope,
} from "@/lib/api";
import {
  validateAgentTokenMint,
  type AgentTokenMintErrors,
} from "@/lib/agent-token-validation";
import { cn } from "@/lib/utils";

const SCOPE_LABELS: Record<AgentTokenScope, string> = {
  "agent:stats:read": "Stats summaries and daily spend",
  "agent:creatives:read": "Creative search and details",
  "agent:creative-performance:read": "Batch creative performance",
  "agent:assets:read": "Creative asset references",
};

const DEFAULT_SCOPE: AgentTokenScope = "agent:stats:read";

function getTokenStatus(token: AgentTokenRecord): "active" | "revoked" | "expired" {
  if (!token.is_active || token.revoked_at) return "revoked";
  if (Date.parse(token.expires_at) <= Date.now()) return "expired";
  return "active";
}

function AgentTokensPage() {
  const queryClient = useQueryClient();
  const { language } = useTranslation();
  const [showMintDialog, setShowMintDialog] = useState(false);
  const [name, setName] = useState("");
  const [targetUserId, setTargetUserId] = useState("");
  const [buyerId, setBuyerId] = useState("");
  const [allGrantedBuyers, setAllGrantedBuyers] = useState(false);
  const [scopes, setScopes] = useState<AgentTokenScope[]>([DEFAULT_SCOPE]);
  const [expiresInDays, setExpiresInDays] = useState("90");
  const [formErrors, setFormErrors] = useState<AgentTokenMintErrors>({});
  const [mintError, setMintError] = useState<string | null>(null);
  const [isMinting, setIsMinting] = useState(false);
  const [revealedToken, setRevealedToken] = useState<string | null>(null);
  const [copiedValue, setCopiedValue] = useState<"token" | "config" | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<AgentTokenRecord | null>(null);

  const {
    data: tokenResponse,
    isLoading: tokensLoading,
    isError: tokensFailed,
    error: tokensError,
    refetch: refetchTokens,
  } = useQuery({
    queryKey: ["agent-tokens"],
    queryFn: getAgentTokens,
  });

  const {
    data: users = [],
    isLoading: usersLoading,
    isError: usersFailed,
    error: usersError,
  } = useQuery({
    queryKey: ["admin-users", { activeOnly: true }],
    queryFn: () => getAdminUsers({ active_only: true }),
    enabled: showMintDialog,
  });

  const {
    data: seats = [],
    isLoading: seatsLoading,
    isError: seatsFailed,
    error: seatsError,
  } = useQuery({
    queryKey: ["buyer-seats", { activeOnly: true }],
    queryFn: () => getSeats({ active_only: true }),
    enabled: showMintDialog,
  });

  const selectedUser = users.find((user) => user.id === targetUserId) ?? null;

  const {
    data: seatPermissions = [],
    isLoading: seatPermissionsLoading,
    isError: seatPermissionsFailed,
    error: seatPermissionsError,
  } = useQuery({
    queryKey: ["user-seat-permissions", targetUserId],
    queryFn: () => getUserSeatPermissions(targetUserId),
    enabled: showMintDialog && Boolean(targetUserId) && selectedUser?.role !== "sudo",
  });

  const grantedSeatPermissions = seatPermissions.filter((permission) => permission.active !== false);
  const availableBuyerIds = selectedUser?.role === "sudo"
    ? seats.map((seat) => seat.buyer_id)
    : grantedSeatPermissions.map((permission) => permission.buyer_id);
  const nonSudoUsers = users.filter((user) => user.role !== "sudo");
  const sudoUsers = users.filter((user) => user.role === "sudo");

  const revokeMutation = useMutation({
    mutationFn: revokeAgentToken,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["agent-tokens"], refetchType: "none" });
      await queryClient.refetchQueries({ queryKey: ["agent-tokens"], type: "active" });
      setRevokeTarget(null);
    },
  });

  const resetMintForm = () => {
    setShowMintDialog(false);
    setName("");
    setTargetUserId("");
    setBuyerId("");
    setAllGrantedBuyers(false);
    setScopes([DEFAULT_SCOPE]);
    setExpiresInDays("90");
    setFormErrors({});
    setMintError(null);
    setIsMinting(false);
  };

  const openMintDialog = () => {
    resetMintForm();
    setShowMintDialog(true);
  };

  const handleTargetUserChange = (userId: string) => {
    setTargetUserId(userId);
    setBuyerId("");
    setAllGrantedBuyers(false);
    setFormErrors((current) => ({ ...current, userId: undefined, buyerScope: undefined }));
    setMintError(null);
  };

  const handleScopeChange = (scope: AgentTokenScope, checked: boolean) => {
    setScopes((current) =>
      checked ? [...current, scope] : current.filter((currentScope) => currentScope !== scope)
    );
    setFormErrors((current) => ({ ...current, scopes: undefined }));
  };

  const getBuyerLabel = (optionBuyerId: string) => {
    const seat = seats.find((candidate) => candidate.buyer_id === optionBuyerId);
    const permission = grantedSeatPermissions.find(
      (candidate) => candidate.buyer_id === optionBuyerId
    );
    const displayName = seat?.display_name || permission?.buyer_display_name;
    return displayName ? `${displayName} (${optionBuyerId})` : optionBuyerId;
  };

  const handleMint = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMintError(null);

    const parsedExpiry = Number(expiresInDays);
    const errors = validateAgentTokenMint({
      name,
      userId: targetUserId,
      targetUserRole: selectedUser?.role ?? null,
      buyerId,
      allGrantedBuyers,
      grantedBuyerIds: availableBuyerIds,
      scopes,
      expiresInDays: parsedExpiry,
    });
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setIsMinting(true);
    try {
      // Do not use a react-query mutation here: its cache must never retain plaintext.
      const created = await createAgentToken({
        name: name.trim(),
        user_id: targetUserId,
        ...(allGrantedBuyers
          ? { all_granted_buyers: true }
          : { buyer_id: buyerId }),
        scopes,
        expires_in_days: parsedExpiry,
      });
      setRevealedToken(created.token);
      resetMintForm();
      void queryClient.invalidateQueries({ queryKey: ["agent-tokens"] });
    } catch (error) {
      setMintError(error instanceof Error ? error.message : "Failed to mint agent token.");
      setIsMinting(false);
    }
  };

  const copyToClipboard = async (value: string, kind: "token" | "config") => {
    setCopyError(null);
    try {
      await navigator.clipboard.writeText(value);
      setCopiedValue(kind);
    } catch {
      setCopyError("Copy failed. Select the text and copy it manually.");
    }
  };

  const formatDate = (date: string | null) => {
    if (!date) return "Never";
    return new Date(date).toLocaleString(language, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const tokenConfig = revealedToken
    ? JSON.stringify(
        {
          mcpServers: {
            rtbcat: {
              type: "streamable-http",
              url: "https://mcp.rtb.cat/mcp",
              headers: { Authorization: `Bearer ${revealedToken}` },
            },
          },
        },
        null,
        2
      )
    : "";

  const tokens = tokenResponse?.tokens ?? [];

  return (
    <div className="p-6 max-w-[96rem] mx-auto">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <KeyRound className="h-6 w-6 text-primary-600" />
            Agent tokens
          </h1>
          <p className="mt-1 text-gray-600">
            Mint and revoke bearer tokens for outside agents. Plaintext is shown only once.
          </p>
        </div>
        <button
          type="button"
          onClick={openMintDialog}
          className="inline-flex items-center justify-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <Plus className="h-5 w-5 mr-2" />
          Mint token
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        {tokensLoading ? (
          <div className="p-12 text-center">
            <div className="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="mt-4 text-gray-600">Loading agent tokens...</p>
          </div>
        ) : tokensFailed ? (
          <div className="p-12 text-center">
            <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
            <p className="font-medium text-gray-900">Unable to load agent tokens</p>
            <p className="mt-1 text-sm text-red-700">
              {tokensError instanceof Error ? tokensError.message : "Unknown error"}
            </p>
            <button
              type="button"
              onClick={() => refetchTokens()}
              className="mt-4 inline-flex items-center px-3 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </button>
          </div>
        ) : tokens.length === 0 ? (
          <div className="p-12 text-center">
            <KeyRound className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="font-medium text-gray-900">No agent tokens</p>
            <p className="mt-1 text-sm text-gray-600">
              Mint a token to connect an outside reporting agent.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  {[
                    "Name",
                    "Token prefix",
                    "Identity",
                    "Buyer scope",
                    "Scopes",
                    "Created",
                    "Expires",
                    "Last used",
                    "Status",
                    "Action",
                  ].map((heading) => (
                    <th
                      key={heading}
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap"
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {tokens.map((token) => {
                  const status = getTokenStatus(token);
                  const isRevoked = status === "revoked";
                  return (
                    <tr
                      key={token.id}
                      className={cn(
                        "hover:bg-gray-50",
                        status !== "active" && "bg-gray-50/70 text-gray-500 opacity-70"
                      )}
                    >
                      <td className="px-4 py-4 text-sm font-medium text-gray-900 max-w-48">
                        <span className="break-words">{token.name}</span>
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-600 font-mono whitespace-nowrap">
                        {token.token_prefix}
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-600 max-w-56">
                        <span className="break-all">{token.user_email || token.user_id}</span>
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-600 whitespace-nowrap">
                        {token.buyer_id || "All granted seats"}
                      </td>
                      <td className="px-4 py-4 text-xs text-gray-600 min-w-56">
                        <div className="flex flex-wrap gap-1">
                          {token.scopes.map((scope) => (
                            <span key={scope} className="px-2 py-1 rounded bg-gray-100 font-mono">
                              {scope}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-600 whitespace-nowrap">
                        {formatDate(token.created_at)}
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-600 whitespace-nowrap">
                        {formatDate(token.expires_at)}
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-600 whitespace-nowrap">
                        {formatDate(token.last_used_at)}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <span
                          className={cn(
                            "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize",
                            status === "active" && "bg-green-100 text-green-800",
                            status === "revoked" && "bg-red-100 text-red-800",
                            status === "expired" && "bg-amber-100 text-amber-800"
                          )}
                        >
                          {status}
                        </span>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <button
                          type="button"
                          disabled={isRevoked}
                          onClick={() => {
                            revokeMutation.reset();
                            setRevokeTarget(token);
                          }}
                          className="text-sm font-medium text-red-600 hover:text-red-800 disabled:text-gray-400 disabled:cursor-not-allowed"
                        >
                          Revoke
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showMintDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="mint-token-title"
            className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] flex flex-col"
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <div>
                <h2 id="mint-token-title" className="text-xl font-semibold text-gray-900">
                  Mint agent token
                </h2>
                <p className="mt-1 text-sm text-gray-600">
                  Bind the token to an active user and their permitted buyer seats.
                </p>
              </div>
              <button
                type="button"
                onClick={resetMintForm}
                disabled={isMinting}
                aria-label="Close mint token dialog"
                className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 disabled:opacity-50"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleMint} className="flex min-h-0 flex-1 flex-col">
              <div className="overflow-y-auto px-6 py-5 space-y-5">
                {mintError && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
                    <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-red-700">{mintError}</p>
                  </div>
                )}

                <div>
                  <label htmlFor="agent-token-name" className="block text-sm font-medium text-gray-700 mb-1">
                    Name
                  </label>
                  <input
                    id="agent-token-name"
                    type="text"
                    value={name}
                    onChange={(event) => {
                      setName(event.target.value);
                      setFormErrors((current) => ({ ...current, name: undefined }));
                    }}
                    minLength={3}
                    maxLength={120}
                    required
                    aria-invalid={Boolean(formErrors.name)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    placeholder="Daily reporting agent"
                  />
                  <div className="mt-1 flex justify-between gap-3 text-xs">
                    <span className={formErrors.name ? "text-red-600" : "text-gray-500"}>
                      {formErrors.name || "A recognizable name, 3–120 characters."}
                    </span>
                    <span className="text-gray-400">{name.length}/120</span>
                  </div>
                </div>

                <div>
                  <label htmlFor="agent-token-user" className="block text-sm font-medium text-gray-700 mb-1">
                    Target user
                  </label>
                  <select
                    id="agent-token-user"
                    value={targetUserId}
                    onChange={(event) => handleTargetUserChange(event.target.value)}
                    disabled={usersLoading || usersFailed}
                    required
                    aria-invalid={Boolean(formErrors.userId)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:bg-gray-100"
                  >
                    <option value="">{usersLoading ? "Loading users..." : "Select a user"}</option>
                    {nonSudoUsers.length > 0 && (
                      <optgroup label="Non-sudo users">
                        {nonSudoUsers.map((user) => (
                          <UserOption key={user.id} user={user} />
                        ))}
                      </optgroup>
                    )}
                    {sudoUsers.length > 0 && (
                      <optgroup label="Sudo users (single buyer only)">
                        {sudoUsers.map((user) => (
                          <UserOption key={user.id} user={user} />
                        ))}
                      </optgroup>
                    )}
                  </select>
                  {usersFailed ? (
                    <p className="mt-1 text-xs text-red-600">
                      {usersError instanceof Error ? usersError.message : "Unable to load users."}
                    </p>
                  ) : (
                    <p className={cn("mt-1 text-xs", formErrors.userId ? "text-red-600" : "text-gray-500")}>
                      {formErrors.userId || "Active non-sudo users are recommended for least privilege."}
                    </p>
                  )}
                </div>

                <fieldset disabled={!selectedUser || seatsFailed || seatPermissionsFailed}>
                  <legend className="block text-sm font-medium text-gray-700 mb-2">Buyer scope</legend>
                  <label
                    className={cn(
                      "flex items-start gap-3 rounded-lg border p-3",
                      selectedUser?.role === "sudo"
                        ? "border-gray-200 bg-gray-50 text-gray-400"
                        : "border-gray-300 cursor-pointer hover:bg-gray-50"
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={allGrantedBuyers}
                      disabled={!selectedUser || selectedUser.role === "sudo" || availableBuyerIds.length === 0}
                      onChange={(event) => {
                        setAllGrantedBuyers(event.target.checked);
                        if (event.target.checked) setBuyerId("");
                        setFormErrors((current) => ({ ...current, buyerScope: undefined }));
                      }}
                      className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    <span>
                      <span className="block text-sm font-medium">All granted buyers</span>
                      <span className="block text-xs mt-0.5">
                        The user&apos;s current seat grants bound every request. Not available to sudo users.
                      </span>
                    </span>
                  </label>

                  <div className="relative my-3 text-center text-xs text-gray-400 before:absolute before:left-0 before:right-0 before:top-1/2 before:border-t before:border-gray-200">
                    <span className="relative bg-white px-2">or choose one buyer</span>
                  </div>

                  <select
                    value={buyerId}
                    onChange={(event) => {
                      setBuyerId(event.target.value);
                      if (event.target.value) setAllGrantedBuyers(false);
                      setFormErrors((current) => ({ ...current, buyerScope: undefined }));
                    }}
                    disabled={!selectedUser || allGrantedBuyers || seatsLoading || seatPermissionsLoading}
                    aria-label="Single buyer scope"
                    aria-invalid={Boolean(formErrors.buyerScope)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:bg-gray-100"
                  >
                    <option value="">
                      {seatsLoading || seatPermissionsLoading ? "Loading buyer grants..." : "Select a buyer"}
                    </option>
                    {availableBuyerIds.map((optionBuyerId) => (
                      <option key={optionBuyerId} value={optionBuyerId}>
                        {getBuyerLabel(optionBuyerId)}
                      </option>
                    ))}
                  </select>
                  {seatsFailed || seatPermissionsFailed ? (
                    <p className="mt-1 text-xs text-red-600">
                      {seatPermissionsError instanceof Error
                        ? seatPermissionsError.message
                        : seatsError instanceof Error
                          ? seatsError.message
                          : "Unable to load buyer grants."}
                    </p>
                  ) : (
                    <p className={cn("mt-1 text-xs", formErrors.buyerScope ? "text-red-600" : "text-gray-500")}>
                      {formErrors.buyerScope || (
                        selectedUser?.role === "sudo"
                          ? "Sudo users are forced to one active buyer."
                          : "Single-buyer options come from this user's seat grants."
                      )}
                    </p>
                  )}
                </fieldset>

                <fieldset>
                  <legend className="block text-sm font-medium text-gray-700 mb-2">Scopes</legend>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {AGENT_TOKEN_SCOPES.map((scope) => (
                      <label key={scope} className="flex items-start gap-3 rounded-lg border border-gray-200 p-3 hover:bg-gray-50 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={scopes.includes(scope)}
                          onChange={(event) => handleScopeChange(scope, event.target.checked)}
                          className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                        />
                        <span className="min-w-0">
                          <span className="block text-xs font-mono text-gray-900 break-all">{scope}</span>
                          <span className="block text-xs text-gray-500 mt-1">{SCOPE_LABELS[scope]}</span>
                        </span>
                      </label>
                    ))}
                  </div>
                  {formErrors.scopes && <p className="mt-1 text-xs text-red-600">{formErrors.scopes}</p>}
                </fieldset>

                <div>
                  <label htmlFor="agent-token-expiry" className="block text-sm font-medium text-gray-700 mb-1">
                    Expiry in days
                  </label>
                  <input
                    id="agent-token-expiry"
                    type="number"
                    min={1}
                    max={366}
                    step={1}
                    value={expiresInDays}
                    onChange={(event) => {
                      setExpiresInDays(event.target.value);
                      setFormErrors((current) => ({ ...current, expiresInDays: undefined }));
                    }}
                    required
                    aria-invalid={Boolean(formErrors.expiresInDays)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                  <p className={cn("mt-1 text-xs", formErrors.expiresInDays ? "text-red-600" : "text-gray-500")}>
                    {formErrors.expiresInDays || "1–366 days. Default: 90."}
                  </p>
                </div>
              </div>

              <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200">
                <button
                  type="button"
                  onClick={resetMintForm}
                  disabled={isMinting}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isMinting || usersFailed || seatsFailed || seatPermissionsFailed}
                  className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <KeyRound className="h-4 w-4 mr-2" />
                  {isMinting ? "Minting..." : "Mint token"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {revealedToken && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="token-reveal-title"
            className="bg-white rounded-xl shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6"
          >
            <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
              <AlertTriangle className="h-6 w-6 text-amber-600 flex-shrink-0" />
              <div>
                <h2 id="token-reveal-title" className="text-xl font-semibold text-amber-900">
                  Store this token now
                </h2>
                <p className="mt-1 text-sm text-amber-800">
                  This plaintext token is shown exactly once and cannot be retrieved again.
                </p>
              </div>
            </div>

            <div className="mt-5">
              <div className="flex items-center justify-between gap-3 mb-2">
                <h3 className="text-sm font-medium text-gray-900">Bearer token</h3>
                <button
                  type="button"
                  onClick={() => copyToClipboard(revealedToken, "token")}
                  className="inline-flex items-center px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  {copiedValue === "token" ? <Check className="h-4 w-4 mr-2 text-green-600" /> : <Copy className="h-4 w-4 mr-2" />}
                  {copiedValue === "token" ? "Copied" : "Copy token"}
                </button>
              </div>
              <pre className="p-4 bg-gray-950 text-green-300 rounded-lg text-sm whitespace-pre-wrap break-all select-all">
                {revealedToken}
              </pre>
            </div>

            <div className="mt-5">
              <div className="flex items-center justify-between gap-3 mb-2">
                <div>
                  <h3 className="text-sm font-medium text-gray-900">MCP client configuration</h3>
                  <p className="text-xs text-gray-500">Paste into your MCP client configuration.</p>
                </div>
                <button
                  type="button"
                  onClick={() => copyToClipboard(tokenConfig, "config")}
                  className="inline-flex items-center px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  {copiedValue === "config" ? <Check className="h-4 w-4 mr-2 text-green-600" /> : <Copy className="h-4 w-4 mr-2" />}
                  {copiedValue === "config" ? "Copied" : "Copy config"}
                </button>
              </div>
              <pre className="p-4 bg-gray-950 text-gray-100 rounded-lg text-sm overflow-x-auto select-all">
                {tokenConfig}
              </pre>
            </div>

            {copyError && <p className="mt-3 text-sm text-red-600">{copyError}</p>}

            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  setRevealedToken(null);
                  setCopiedValue(null);
                  setCopyError(null);
                }}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
              >
                I have stored the token
              </button>
            </div>
          </div>
        </div>
      )}

      {revokeTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="revoke-token-title"
            className="bg-white rounded-xl shadow-xl max-w-md w-full p-6"
          >
            <div className="flex items-start gap-3">
              <div className="rounded-full bg-red-100 p-2">
                <ShieldAlert className="h-6 w-6 text-red-600" />
              </div>
              <div>
                <h2 id="revoke-token-title" className="text-lg font-semibold text-gray-900">
                  Revoke agent token?
                </h2>
                <p className="mt-2 text-sm text-gray-600">
                  <span className="font-medium text-gray-900">{revokeTarget.name}</span> will stop
                  working on its next use. This action cannot be undone.
                </p>
              </div>
            </div>

            {revokeMutation.isError && (
              <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {revokeMutation.error instanceof Error
                  ? revokeMutation.error.message
                  : "Failed to revoke agent token."}
              </div>
            )}

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                disabled={revokeMutation.isPending}
                onClick={() => {
                  revokeMutation.reset();
                  setRevokeTarget(null);
                }}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={revokeMutation.isPending}
                onClick={() => revokeMutation.mutate(revokeTarget.id)}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {revokeMutation.isPending ? "Revoking..." : "Revoke token"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function UserOption({ user }: { user: AdminUser }) {
  return <option value={user.id}>{`${user.email} — ${user.role}`}</option>;
}

export default withAdminAuth(AgentTokensPage);
