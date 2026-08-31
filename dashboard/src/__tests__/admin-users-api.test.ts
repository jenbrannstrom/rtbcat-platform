import { beforeEach, describe, expect, it, vi } from "vitest";

import { deleteAdminUser } from "@/lib/api/admin";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

describe("admin user API client", () => {
  it("permanently deletes an encoded user id with explicit confirmation", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "success", message: "User permanently deleted" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    await deleteAdminUser("user/id");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/admin/users/user%2Fid?confirm=true",
      expect.objectContaining({ method: "DELETE", credentials: "include" })
    );
  });
});
