import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createAgentToken,
  getAgentTokens,
  revokeAgentToken,
  type CreateAgentTokenRequest,
} from "@/lib/api/agent-tokens";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

describe("agent token API client", () => {
  it("lists safe token records", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ tokens: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    await expect(getAgentTokens()).resolves.toEqual({ tokens: [] });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/agent/v1/tokens",
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("mints with the contract request body", async () => {
    const request: CreateAgentTokenRequest = {
      name: "Reporting agent",
      user_id: "user-1",
      all_granted_buyers: true,
      scopes: ["agent:stats:read"],
      expires_in_days: 90,
    };
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ token: "test-token", token_type: "Bearer", token_record: {} }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    await createAgentToken(request);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/agent/v1/tokens",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify(request),
      })
    );
  });

  it("URL-encodes the token id when revoking", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "revoked", token_id: "token/id" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    await revokeAgentToken("token/id");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/agent/v1/tokens/token%2Fid",
      expect.objectContaining({ method: "DELETE", credentials: "include" })
    );
  });

  it("surfaces the API detail message verbatim", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Agent user has no buyer read grants." }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      })
    );

    await expect(getAgentTokens()).rejects.toThrow("Agent user has no buyer read grants.");
  });
});
